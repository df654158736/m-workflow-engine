"""统一 HTTP 客户端 — 封装 zhice-paas web-app REST API 调用。

所有 data-first Tools 通过此模块调用真实 API。
认证使用 dev-mock-token，无需登录。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import yaml

_CONFIG_DIR = Path(__file__).parent.parent.parent.parent
_CONFIG_LOCAL = _CONFIG_DIR / "config.local.yaml"
_CONFIG_PATH = _CONFIG_LOCAL if _CONFIG_LOCAL.exists() else _CONFIG_DIR / "config.yaml"

_client: httpx.AsyncClient | None = None
_config: dict[str, Any] = {}


def _load_webapp_config() -> dict[str, Any]:
    global _config
    if _config:
        return _config
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH) as f:
            cfg = yaml.safe_load(f) or {}
        _config = cfg.get("web_app", {})
    return _config


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        cfg = _load_webapp_config()
        base_url = cfg.get("base_url", "http://192.168.2.60:6682")
        token = cfg.get("auth_token", "admin-mock-token")
        project_id = cfg.get("project_id", "")
        world_id = cfg.get("world_id", "")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        if project_id:
            headers["X-Project-Id"] = project_id
        if world_id:
            headers["X-World-Id"] = world_id

        _client = httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            timeout=30.0,
            proxy=None,
        )
    return _client


def get_project_id() -> str:
    cfg = _load_webapp_config()
    return cfg.get("project_id", "")


class ApiError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        super().__init__(f"API error {code}: {message}")


async def api_get(path: str, params: dict[str, Any] | None = None) -> Any:
    """GET 请求，自动解包 {code, data} 响应。"""
    client = get_client()
    resp = await client.get(path, params=params)
    resp.raise_for_status()
    body = resp.json()
    if body.get("code") != 200:
        raise ApiError(body.get("code", -1), body.get("message", "unknown"))
    return body.get("data")


async def api_post(path: str, json_data: dict[str, Any] | None = None) -> Any:
    """POST 请求，自动解包 {code, data} 响应。"""
    client = get_client()
    resp = await client.post(path, json=json_data)
    resp.raise_for_status()
    body = resp.json()
    if body.get("code") != 200:
        raise ApiError(body.get("code", -1), body.get("message", "unknown"))
    return body.get("data")


async def api_put(path: str, json_data: dict[str, Any] | None = None) -> Any:
    """PUT 请求，自动解包 {code, data} 响应。gRPC mid-frame 偶发异常自动重试一次。"""
    import asyncio
    last_err: ApiError | None = None
    for attempt in range(2):
        client = get_client()
        resp = await client.put(path, json=json_data)
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") == 200:
            return body.get("data")
        msg = body.get("message", "")
        if attempt == 0 and ("end-of-stream" in msg.lower() or "mid-frame" in msg.lower()):
            last_err = ApiError(body.get("code", -1), msg)
            await asyncio.sleep(0.3)
            continue
        raise ApiError(body.get("code", -1), msg)
    raise last_err  # type: ignore[misc]


async def api_delete(path: str) -> Any:
    """DELETE 请求，自动解包 {code, data} 响应。"""
    client = get_client()
    resp = await client.delete(path)
    resp.raise_for_status()
    body = resp.json()
    if body.get("code") != 200:
        raise ApiError(body.get("code", -1), body.get("message", "unknown"))
    return body.get("data")
