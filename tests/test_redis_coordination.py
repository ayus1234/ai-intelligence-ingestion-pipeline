"""Tests for RedisWorkCoordinator, heartbeat lease renewal, and dead-worker recovery."""

import asyncio
import time

import pytest

from ai_intel.storage.redis_queue import HeartbeatTask, RedisWorkCoordinator


@pytest.mark.asyncio
async def test_redis_work_coordinator_claiming_and_renewal() -> None:
    coord = RedisWorkCoordinator()
    t_id = "target-101"
    w1 = "worker-1"
    w2 = "worker-2"

    # Worker 1 claims lease
    token1 = await coord.claim_target(t_id, w1, lease_ttl=2)
    assert token1 is not None
    assert token1.target_id == t_id
    assert token1.worker_id == w1

    # Worker 2 tries to claim same target -> fails
    token2 = await coord.claim_target(t_id, w2, lease_ttl=2)
    assert token2 is None

    # Worker 1 renews lease
    renewed = await coord.renew_lease(t_id, w1, lease_ttl=5)
    assert renewed is True

    # Worker 2 tries to renew lease -> fails
    renewed2 = await coord.renew_lease(t_id, w2, lease_ttl=5)
    assert renewed2 is False

    # Worker 1 releases lease
    released = await coord.release_target(t_id, w1)
    assert released is True

    # Worker 2 can now claim target
    token3 = await coord.claim_target(t_id, w2, lease_ttl=2)
    assert token3 is not None


@pytest.mark.asyncio
async def test_dead_worker_recovery() -> None:
    coord = RedisWorkCoordinator()
    t_id = "target-stale"
    w_dead = "worker-dead"

    # Worker claims lease with short 1 second TTL
    token = await coord.claim_target(t_id, w_dead, lease_ttl=1)
    assert token is not None

    # Wait for TTL to expire
    await asyncio.sleep(1.05)

    # Recover dead worker leases
    recovered = await coord.recover_dead_workers()
    assert recovered == 1

    # New worker can claim target
    token_new = await coord.claim_target(t_id, "worker-alive", lease_ttl=60)
    assert token_new is not None


@pytest.mark.asyncio
async def test_heartbeat_task() -> None:
    coord = RedisWorkCoordinator()
    t_id = "target-hb"
    w_id = "worker-hb"

    token = await coord.claim_target(t_id, w_id, lease_ttl=5)
    assert token is not None

    hb = HeartbeatTask(coord, t_id, w_id, interval_seconds=0.05, lease_ttl=5)
    await hb.start()
    await asyncio.sleep(0.12)
    await hb.stop()

    assert await coord.release_target(t_id, w_id) is True
