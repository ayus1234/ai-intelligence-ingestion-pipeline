"""Distributed work coordinator with lease claiming, heartbeat renewal, and dead-worker recovery."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from ai_intel.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RedisLockToken:
    target_id: str
    worker_id: str
    ttl_seconds: int
    claimed_at: float


class RedisWorkCoordinator:
    def __init__(self, redis_client: Any | None = None) -> None:
        self.redis = redis_client
        self._in_memory_locks: dict[str, tuple[str, float, int]] = {}  # target_id -> (worker_id, claimed_at, ttl)

    async def claim_target(self, target_id: str, worker_id: str, lease_ttl: int = 60) -> RedisLockToken | None:
        """Attempt to claim a target using an atomic lease with TTL."""
        now = time.time()
        lock_key = f"lock:target:{target_id}"

        if self.redis is not None:
            try:
                acquired = await self.redis.set(lock_key, worker_id, nx=True, ex=lease_ttl)
                if acquired:
                    return RedisLockToken(target_id=target_id, worker_id=worker_id, ttl_seconds=lease_ttl, claimed_at=now)
                return None
            except Exception as exc:
                logger.warning("redis_claim_failed_falling_back", extra={"target_id": target_id, "error": str(exc)})

        # In-memory fallback
        if lock_key in self._in_memory_locks:
            owner, claimed_at, ttl = self._in_memory_locks[lock_key]
            if now - claimed_at < ttl:
                return None  # Still locked by active worker

        self._in_memory_locks[lock_key] = (worker_id, now, lease_ttl)
        return RedisLockToken(target_id=target_id, worker_id=worker_id, ttl_seconds=lease_ttl, claimed_at=now)

    async def renew_lease(self, target_id: str, worker_id: str, lease_ttl: int = 60) -> bool:
        """Renew an existing work lease (heartbeat renewal)."""
        now = time.time()
        lock_key = f"lock:target:{target_id}"

        if self.redis is not None:
            try:
                current_owner = await self.redis.get(lock_key)
                if current_owner and (current_owner == worker_id or current_owner.decode("utf-8") == worker_id):
                    await self.redis.expire(lock_key, lease_ttl)
                    return True
                return False
            except Exception as exc:
                logger.warning("redis_renew_failed", extra={"target_id": target_id, "error": str(exc)})

        # In-memory fallback
        if lock_key in self._in_memory_locks:
            owner, _, _ = self._in_memory_locks[lock_key]
            if owner == worker_id:
                self._in_memory_locks[lock_key] = (worker_id, now, lease_ttl)
                return True
        return False

    async def release_target(self, target_id: str, worker_id: str) -> bool:
        """Release a target lease idempotently."""
        lock_key = f"lock:target:{target_id}"

        if self.redis is not None:
            try:
                current_owner = await self.redis.get(lock_key)
                if current_owner and (current_owner == worker_id or current_owner.decode("utf-8") == worker_id):
                    await self.redis.delete(lock_key)
                    return True
                return False
            except Exception as exc:
                logger.warning("redis_release_failed", extra={"target_id": target_id, "error": str(exc)})

        # In-memory fallback
        if lock_key in self._in_memory_locks:
            owner, _, _ = self._in_memory_locks[lock_key]
            if owner == worker_id:
                del self._in_memory_locks[lock_key]
                return True
        return False

    async def recover_dead_workers(self) -> int:
        """Recover expired leases from crashed or unresponsive workers."""
        now = time.time()
        recovered_count = 0

        if self.redis is not None:
            # Redis handles TTL expiration automatically
            return 0

        stale_keys = [k for k, (w, claimed_at, ttl) in self._in_memory_locks.items() if now - claimed_at >= ttl]
        for key in stale_keys:
            del self._in_memory_locks[key]
            recovered_count += 1

        if recovered_count > 0:
            logger.info("dead_worker_leases_recovered", extra={"recovered_count": recovered_count})
        return recovered_count


class HeartbeatTask:
    """Background heartbeat task for periodic lease renewal."""

    def __init__(
        self,
        coordinator: RedisWorkCoordinator,
        target_id: str,
        worker_id: str,
        interval_seconds: float = 15.0,
        lease_ttl: int = 60,
    ) -> None:
        self.coordinator = coordinator
        self.target_id = target_id
        self.worker_id = worker_id
        self.interval_seconds = interval_seconds
        self.lease_ttl = lease_ttl
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._run_heartbeat())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_heartbeat(self) -> None:
        while self._running:
            await asyncio.sleep(self.interval_seconds)
            if not self._running:
                break
            renewed = await self.coordinator.renew_lease(self.target_id, self.worker_id, self.lease_ttl)
            if not renewed:
                logger.warning("heartbeat_renewal_failed", extra={"target_id": self.target_id, "worker_id": self.worker_id})
                break
