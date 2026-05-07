"""Tool Registry — 工具注册、发现与执行。

每个 Tool 用 @tool 装饰器注册，Agent 通过 function calling 调用。
扩展方式：在 tools/ 目录下新建文件，用 @tool 装饰即可自动注册。
"""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Awaitable[dict]]


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

    async def execute(self, name: str, arguments: dict[str, Any]) -> dict:
        """执行指定工具，返回结果 dict。"""
        defn = self._tools.get(name)
        if not defn:
            return {"error": f"Unknown tool: {name}"}
        try:
            result = await defn.handler(**arguments)
            return result
        except Exception as e:
            return {"error": f"Tool '{name}' failed: {str(e)}"}


# Global registry
_registry = ToolRegistry()


def tool(name: str, description: str, parameters: dict[str, Any] | None = None):
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
