"""LLM Node Executor — 真实调用 LLM (Qwen via OpenAI-compatible API)."""

from __future__ import annotations

import os
import time
from typing import Any

import structlog
from openai import AsyncOpenAI

from backend.models import Determinism, NodeResult, NodeType, Runtime, StepStatus
from backend.spi import NodeExecutor

logger = structlog.get_logger()

QWEN_API_KEY = os.environ.get("QWEN_API_KEY", "sk-12fe39821ded4857be52466717c1fcc8")
QWEN_BASE_URL = os.environ.get("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QWEN_MODEL = os.environ.get("QWEN_MODEL", "qwen-plus")


class LLMExecutor(NodeExecutor):
    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=QWEN_API_KEY,
            base_url=QWEN_BASE_URL,
        )

    @property
    def node_type(self) -> NodeType:
        return NodeType.LLM

    @property
    def runtime(self) -> Runtime:
        return Runtime.PLANE_E

    @property
    def determinism(self) -> Determinism:
        return Determinism.NONDETERMINISTIC_CACHEABLE

    async def execute(
        self, node_id: str, config: dict[str, Any], inputs: dict[str, Any]
    ) -> NodeResult:
        prompt = config.get("prompt", "Analyze the input data")
        model = config.get("model", QWEN_MODEL)
        system_prompt = config.get("system_prompt", "你是一个智能分析助手，请用中文简洁回答。")

        # 将上游节点的输出作为上下文注入 prompt
        context_parts = []
        for key, value in inputs.items():
            context_parts.append(f"[{key}]: {value}")

        full_prompt = prompt
        if context_parts:
            full_prompt = f"{prompt}\n\n上下文信息:\n" + "\n".join(context_parts)

        logger.info(
            "[Plane E] LLM calling real API",
            node_id=node_id,
            model=model,
            prompt_preview=full_prompt[:80],
        )

        start_time = time.time()
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": full_prompt},
                ],
                temperature=config.get("temperature", 0.7),
                max_tokens=config.get("max_tokens", 1024),
            )

            duration_ms = int((time.time() - start_time) * 1000)
            text = response.choices[0].message.content or ""
            usage = response.usage

            logger.info(
                "[Plane E] LLM response received",
                node_id=node_id,
                duration_ms=duration_ms,
                tokens=usage.total_tokens if usage else 0,
            )

            return NodeResult(
                node_id=node_id,
                status=StepStatus.COMPLETED,
                outputs={
                    "text": text,
                    "tokens_used": usage.total_tokens if usage else 0,
                    "model": model,
                    "prompt": full_prompt,
                    "duration_ms": duration_ms,
                },
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error("[Plane E] LLM call failed", node_id=node_id, error=str(e))
            return NodeResult(
                node_id=node_id,
                status=StepStatus.FAILED,
                outputs={"error": str(e), "model": model, "prompt": full_prompt},
                error=str(e),
            )
