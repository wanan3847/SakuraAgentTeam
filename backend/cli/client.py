"""HTTP 客户端 — 调用后端 REST + 消费 SSE 流。"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx

from .config import Config


class SakuraAPIError(RuntimeError):
    """后端 API 错误，包含 HTTP 状态码与消息。"""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API {status_code}: {detail}")


class SakuraClient:
    def __init__(self, config: Config, timeout: float = 30.0):
        self._config = config
        self._client = httpx.Client(
            base_url=config.api_url.rstrip("/"),
            timeout=timeout,
            headers=self._auth_headers(),
        )

    def _auth_headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self._config.api_token:
            h["Authorization"] = f"Bearer {self._config.api_token}"
        return h

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> SakuraClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            r = self._client.request(method, path, **kwargs)
        except httpx.ConnectError as e:
            raise SakuraAPIError(0, f"无法连接后端 {self._config.api_url}：{e}") from e
        except httpx.HTTPError as e:
            raise SakuraAPIError(0, f"HTTP 错误：{e}") from e

        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except Exception:
                detail = r.text
            raise SakuraAPIError(r.status_code, detail)
        if not r.content:
            return {"success": True, "data": None}
        return r.json()

    # ---------- Sessions ----------

    def list_sessions(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/sessions")["data"]

    def get_session(self, session_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/sessions/{session_id}")["data"]

    def get_artifacts(self, session_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/api/v1/sessions/{session_id}/artifacts")["data"]

    def create_session(
        self,
        requirement: str,
        project_id: str | None = None,
        workflow: str | None = None,
        auto_start: bool = True,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"requirement": requirement, "auto_start": auto_start}
        if project_id:
            body["project_id"] = project_id
        if workflow:
            body["workflow"] = workflow
        return self._request("POST", "/api/v1/sessions", json=body)["data"]

    def cancel_session(self, session_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/sessions/{session_id}/cancel")["data"]

    def execute_session(self, session_id: str, workflow: str | None = None) -> dict[str, Any]:
        body = {"workflow": workflow} if workflow else {}
        return self._request(
            "POST", f"/api/v1/sessions/{session_id}/execute", json=body
        )["data"]

    # ---------- Projects ----------

    def list_projects(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/projects")["data"]

    # ---------- Health ----------

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    # ---------- SSE Stream ----------

    def stream_events(self, session_id: str) -> Iterator[dict[str, Any]]:
        """消费 SSE 流，逐条 yield 解析后的事件。

        每条形如 {"event": "agent_completed", "data": {...}, "timestamp": ...}
        """
        with self._client.stream("GET", f"/api/v1/sessions/{session_id}/stream") as r:
            r.raise_for_status()
            event_type = "message"
            data_buf: list[str] = []
            for line in r.iter_lines():
                if line.startswith("event: "):
                    event_type = line[len("event: ") :].strip()
                elif line.startswith("data: "):
                    data_buf.append(line[len("data: ") :])
                elif line == "":
                    # 一个事件结束
                    if data_buf:
                        raw = "\n".join(data_buf)
                        try:
                            data_obj = json.loads(raw)
                        except json.JSONDecodeError:
                            data_obj = {"raw": raw}
                        yield {"event": event_type, "data": data_obj}
                    event_type = "message"
                    data_buf = []
