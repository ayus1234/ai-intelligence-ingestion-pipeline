"""LLM provider fallback orchestration with circuit breaker, chunk replay protection, exponential backoff + jitter, and retry metrics."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ValidationError

from ai_intel.logging import get_logger
from ai_intel.llm.base import LLMError, LLMProvider, LLMProviderResult, RetryMetrics
from ai_intel.llm.cache import ExtractionCache
from ai_intel.llm.circuit_breaker import CircuitBreaker
from ai_intel.llm.chunker import SemanticChunker

logger = get_logger(__name__)


class LLMOrchestrator:
    def __init__(
        self,
        providers: Sequence[LLMProvider],
        max_retries: int = 3,
        base_delay_seconds: float = 0.5,
        max_delay_seconds: float = 5.0,
        cache: ExtractionCache | None = None,
        chunker: SemanticChunker | None = None,
        prompt_version: str = "v1",
    ) -> None:
        if not providers:
            raise ValueError("at least one LLM provider is required")
        self.providers = list(providers)
        self.max_retries = max_retries
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.cache = cache or ExtractionCache()
        self.chunker = chunker or SemanticChunker(max_tokens_per_chunk=4000)
        self.prompt_version = prompt_version
        self.circuit_breakers: dict[str, CircuitBreaker] = {
            p.name: CircuitBreaker(provider_name=p.name, failure_threshold=3, cooldown_seconds=60.0)
            for p in self.providers
        }

    async def extract(
        self,
        schema_name: str,
        text: str,
        source_url: str,
        output_model: type[BaseModel] | None = None,
        use_cache: bool = True,
    ) -> LLMProviderResult | BaseModel:
        cache_key = ExtractionCache.compute_key(text, schema_name, self.prompt_version)
        if use_cache:
            cached_payload = self.cache.get(cache_key)
            if cached_payload is not None:
                logger.info("llm_extraction_cache_hit", extra={"schema": schema_name, "cache_key": cache_key})
                res = LLMProviderResult(
                    provider_name="cache",
                    model="cached-payload",
                    payload=cached_payload,
                    confidence_score=1.0,
                    cache_hit=True,
                    retry_metrics=RetryMetrics(provider="cache", attempts=1),
                )
                if output_model is not None:
                    return output_model.model_validate(cached_payload)
                return res

        chunks = self.chunker.chunk(text)
        chunk_count = len(chunks)

        # Chunk Replay Protection: Store successful chunk extraction payloads
        extracted_chunk_payloads: list[dict[str, Any]] = []

        failures: list[str] = []
        fallback_triggered = False
        last_successful_provider: LLMProvider | None = None

        for chunk_idx, chunk_text in enumerate(chunks):
            chunk_cache_key = ExtractionCache.compute_key(chunk_text, schema_name, f"{self.prompt_version}-chunk-{chunk_idx}")
            chunk_payload = self.cache.get(chunk_cache_key) if use_cache else None

            if chunk_payload is not None:
                extracted_chunk_payloads.append(chunk_payload)
                continue

            chunk_success = False
            for p_idx, provider in enumerate(self.providers):
                if p_idx > 0:
                    fallback_triggered = True

                cb = self.circuit_breakers[provider.name]
                if not cb.can_execute():
                    failures.append(f"{provider.name}:circuit_open")
                    continue

                attempts = 0
                total_wait_time = 0.0
                retry_after_used = False

                for attempt in range(1, self.max_retries + 1):
                    attempts = attempt
                    try:
                        res = await provider.extract(schema_name, chunk_text, source_url)
                        cb.record_success()
                        chunk_payload = res.payload
                        chunk_success = True

                        last_successful_provider = provider
                        if use_cache and chunk_payload:
                            self.cache.set(chunk_cache_key, chunk_payload)

                        extracted_chunk_payloads.append(chunk_payload)
                        metrics = RetryMetrics(
                            provider=provider.name,
                            attempts=attempts,
                            total_wait_time=total_wait_time,
                            retry_after_used=retry_after_used,
                            fallback_triggered=fallback_triggered,
                        )
                        break
                    except Exception as exc:
                        cb.record_failure()
                        retryable = getattr(exc, "retryable", False)
                        retry_after = getattr(exc, "retry_after_seconds", None)

                        if attempt < self.max_retries and retryable:
                            if retry_after is not None and retry_after > 0:
                                sleep_time = retry_after
                                retry_after_used = True
                            else:
                                # Exponential backoff with full jitter
                                sleep_time = random.uniform(
                                    0, min(self.max_delay_seconds, self.base_delay_seconds * (2 ** (attempt - 1)))
                                )
                            total_wait_time += sleep_time
                            await asyncio.sleep(sleep_time)
                        else:
                            failures.append(f"{provider.name}:{exc}")
                            break

                if chunk_success:
                    break

            if not chunk_success:
                raise LLMError(f"all LLM providers failed for chunk {chunk_idx + 1}/{chunk_count}: " + " | ".join(failures))

        # Merge extracted chunk payloads
        merged_payload = self._merge_chunk_payloads(extracted_chunk_payloads)

        validation_status = "STRICT_SUCCESS"
        validated_model = None
        if output_model is not None:
            try:
                validated_model = output_model.model_validate(merged_payload)
            except ValidationError:
                validation_status = "VALIDATION_FAILED"

        successful_provider = last_successful_provider or (self.providers[0] if self.providers else None)
        provider_name = successful_provider.name if successful_provider else "unknown"
        provider_model = successful_provider.model if successful_provider else "unknown"
        provider_tier = getattr(successful_provider, "tier", 1)

        confidence_score = self._compute_confidence_score(
            provider_tier=provider_tier,
            retries=0,
            chunk_count=chunk_count,
            validation_status=validation_status,
        )

        final_res = LLMProviderResult(
            provider_name=provider_name,
            model=provider_model,
            payload=merged_payload,
            confidence_score=confidence_score,
            chunk_count=chunk_count,
            retries=0,
            cache_hit=False,
            validation_status=validation_status,
            retry_metrics=RetryMetrics(
                provider=provider_name,
                attempts=1,
                fallback_triggered=fallback_triggered,
            ),
        )

        if use_cache and merged_payload:
            self.cache.set(cache_key, merged_payload)

        if validated_model is not None:
            return validated_model
        return final_res

    async def extract_dict(self, schema_name: str, text: str, source_url: str) -> dict[str, Any]:
        result = await self.extract(schema_name=schema_name, text=text, source_url=source_url)
        if isinstance(result, LLMProviderResult):
            return result.payload
        return result.model_dump(mode="json")

    @staticmethod
    def _merge_chunk_payloads(payloads: list[dict[str, Any]]) -> dict[str, Any]:
        """Merge list of chunk payloads into single payload."""
        if not payloads:
            return {}
        if len(payloads) == 1:
            return payloads[0]

        merged: dict[str, Any] = {}
        for p in payloads:
            for k, v in p.items():
                if k not in merged:
                    merged[k] = v
                elif isinstance(v, list) and isinstance(merged[k], list):
                    merged[k].extend([item for item in v if item not in merged[k]])
                elif isinstance(v, dict) and isinstance(merged[k], dict):
                    merged[k].update(v)
        return merged

    @staticmethod
    def _compute_confidence_score(
        provider_tier: int,
        retries: int,
        chunk_count: int,
        validation_status: str,
    ) -> float:
        tier_base = {1: 1.0, 2: 0.85, 3: 0.70, 4: 0.50}.get(provider_tier, 0.50)
        retry_penalty = retries * 0.05
        chunk_penalty = max(0, (chunk_count - 1)) * 0.02
        val_penalty = 0.0 if validation_status == "STRICT_SUCCESS" else 0.20
        score = tier_base - retry_penalty - chunk_penalty - val_penalty
        return max(0.0, min(1.0, round(score, 2)))
