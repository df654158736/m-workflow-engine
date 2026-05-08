"""Tool Registry — 工具注册、发现与执行。

每个 Tool 用 @tool 装饰器注册，Agent 通过 function calling 调用。
扩展方式：在 tools/ 目录下新建文件，用 @tool 装饰即可自动注册。
"""

from __future__ import annotations

import asyncio
import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from pydantic import BaseModel, ValidationError

_TOOL_TIMEOUT_SECONDS = 60


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Awaitable[dict]]
    requires_confirmation: bool = False
    args_model: type[BaseModel] | None = None


class ToolRegistry:
    """管理所有可用的 Agent 工具。"""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, defn: ToolDefinition) -> None:
        self._tools[defn.name] = defn

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def schemas(self, only: set[str] | None = None) -> list[dict]:
        """返回 OpenAI function calling 格式的 tools schema。

        only: 若提供，只返回指定名称的 Tool schema。
        """
        result = []
        for t in self._tools.values():
            if only and t.name not in only:
                continue
            result.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            })
        return result

    async def execute(
        self, name: str, arguments: dict[str, Any], confirmed: bool = False,
    ) -> dict:
        """执行指定工具，返回结果 dict。"""
        defn = self._tools.get(name)
        if not defn:
            return {"error": f"Unknown tool: {name}"}
        if defn.args_model:
            try:
                validated = defn.args_model.model_validate(arguments)
                arguments = validated.model_dump()
            except ValidationError as e:
                errors = [f"{err['loc']}: {err['msg']}" for err in e.errors()]
                return {
                    "error": f"参数校验失败: {'; '.join(errors)}",
                    "hint": f"请检查 '{name}' 的参数格式后重新调用。",
                }
        if defn.requires_confirmation and not confirmed:
            return {
                "requires_confirmation": True,
                "tool": name,
                "args": arguments,
                "message": f"工具 '{name}' 是写操作，需要用户确认后才能执行。",
            }
        try:
            result = await asyncio.wait_for(
                defn.handler(**arguments),
                timeout=_TOOL_TIMEOUT_SECONDS,
            )
            return result
        except asyncio.TimeoutError:
            return {"error": f"工具 '{name}' 执行超时（{_TOOL_TIMEOUT_SECONDS}s），请稍后重试或检查下游服务。"}
        except Exception as e:
            return {"error": f"Tool '{name}' failed: {str(e)}"}


# Global registry
_registry = ToolRegistry()


def tool(
    name: str,
    description: str,
    parameters: dict[str, Any] | None = None,
    requires_confirmation: bool = False,
    args_model: type[BaseModel] | None = None,
):
    """装饰器：注册一个 Agent Tool。

    Usage:
        @tool(name="validate_dag", description="...", parameters={...})
        async def validate_dag(yaml_text: str) -> dict:
            ...
    """
    def decorator(fn: Callable) -> Callable:
        params = parameters
        if params is None:
            params = _infer_parameters(fn)
        _registry.register(ToolDefinition(
            name=name,
            description=description,
            parameters=params,
            handler=fn,
            requires_confirmation=requires_confirmation,
            args_model=args_model,
        ))
        return fn
    return decorator


def get_registry() -> ToolRegistry:
    return _registry


def _infer_parameters(fn: Callable) -> dict:
    """从函数签名推断 JSON Schema parameters。"""
    sig = inspect.signature(fn)
    properties = {}
    required = []
    for pname, param in sig.parameters.items():
        if pname == "self":
            continue
        ptype = "string"
        annotation = param.annotation
        if annotation == int:
            ptype = "integer"
        elif annotation == bool:
            ptype = "boolean"
        elif annotation == float:
            ptype = "number"
        elif annotation == dict:
            ptype = "object"
        elif annotation == list:
            ptype = "array"
        properties[pname] = {"type": ptype}
        if param.default is inspect.Parameter.empty:
            required.append(pname)
    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }
