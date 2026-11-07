"""OpenAI 兼容对话接口（只用标准库，无第三方依赖）。

设计要点
--------
- 接口形状按 OpenAI ``/v1/chat/completions``；Base URL 可指向任何兼容服务
  （DeepSeek、vLLM、Ollama 的 OpenAI 兼容层等）。
- **密钥永不入日志**：异常信息只带 ``cfg.to_dict(redact=True)`` 的脱敏字段。
- 重试只针对 408/409/425/429/5xx 与网络超时；4xx（除 429）直接失败，
  避免把「Key 错了」重试成「Key 被封」。
- ``transport`` 可注入，测试时用本地假 server/monkeypatch，不需要真实联网。
"""
from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable

from .config import ModelConfig
from .errors import ConfigError, ModelAPIError

#: 值得重试的 HTTP 状态
RETRY_STATUS = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
#: 重试退避基数（秒）
BACKOFF_BASE = 1.5
#: 单次内容上限（防止误把整本书塞给模型）
MAX_MESSAGES_CHARS = 200_000


@dataclass
class LLMResponse:
    """一次补全的结果。"""

    text: str
    model: str = ""
    usage: dict = field(default_factory=dict)
    latency_s: float = 0.0
    finish_reason: str = ""
    attempts: int = 1
    tool_calls: list = field(default_factory=list)  # 标准模式：模型要求的工具调用
    raw: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "model": self.model,
            "usage": self.usage,
            "latency_s": round(self.latency_s, 3),
            "finish_reason": self.finish_reason,
            "attempts": self.attempts,
            "tool_calls": len(self.tool_calls),
        }


Transport = Callable[[str, str, dict, bytes, float], tuple[int, str]]


def _urllib_transport(method: str, url: str, headers: dict, body: bytes,
                      timeout: float) -> tuple[int, str]:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - 用户自配 URL
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


class LLMClient:
    """OpenAI 兼容的最小客户端。"""

    def __init__(self, cfg: ModelConfig, *, transport: Transport | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        self.cfg = cfg
        self._transport = transport or _urllib_transport
        self._sleep = sleep

    # -------------------------------------------------------------- 基础信息
    @property
    def available(self) -> bool:
        return bool(self.cfg.api_key.strip() and self.cfg.base_url.strip())

    @property
    def endpoint(self) -> str:
        base = self.cfg.base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        safe = self.cfg.to_dict(redact=True) if hasattr(self.cfg, "to_dict") else {}
        return f"LLMClient(model={self.cfg.model!r}, cfg={safe})"

    # ------------------------------------------------------------------ 调用
    def chat(self, messages: list[dict], *, temperature: float | None = None,
             max_tokens: int | None = None, timeout: float | None = None,
             json_mode: bool = False, tools: list[dict] | None = None,
             tool_choice: str | None = None) -> LLMResponse:
        """发一次对话补全；失败按策略重试后抛 :class:`ModelAPIError`。"""
        if not self.available:
            raise ConfigError(
                "未配置模型 API（base_url 或 api_key 为空）",
                hint="运行 `inksoul config --init` 生成配置文件，填入 api_key；"
                     "离线分析可加 `--offline`",
            )
        self._validate_messages(messages)
        payload: dict = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": self.cfg.temperature if temperature is None else temperature,
            "top_p": self.cfg.top_p,
            "max_tokens": self.cfg.max_tokens if max_tokens is None else max_tokens,
        }
        if self.cfg.presence_penalty:
            payload["presence_penalty"] = self.cfg.presence_penalty
        if self.cfg.frequency_penalty:
            payload["frequency_penalty"] = self.cfg.frequency_penalty
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if tools:
            payload["tools"] = tools
            if tool_choice:
                payload["tool_choice"] = tool_choice

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.cfg.api_key.strip()}",
        }
        timeout = float(self.cfg.timeout if timeout is None else timeout)
        attempts = max(1, int(self.cfg.max_retries) + 1)
        last_error = ""

        for attempt in range(1, attempts + 1):
            started = time.time()
            try:
                status, text = self._transport("POST", self.endpoint, headers, body, timeout)
            except (socket.timeout, TimeoutError) as exc:
                last_error = f"请求超时（{timeout:g}s）：{exc}"
                status, text = 0, ""
            except urllib.error.URLError as exc:
                last_error = f"网络错误：{exc.reason}"
                status, text = 0, ""
            else:
                last_error = ""

            latency = time.time() - started
            if status == 200:
                return self._parse(text, latency_s=latency, attempts=attempt)
            if status == 0 or status in RETRY_STATUS:
                last_error = last_error or f"HTTP {status}：{self._short(text)}"
                if attempt < attempts:
                    self._sleep(BACKOFF_BASE ** attempt)
                    continue
                raise ModelAPIError(
                    f"模型接口调用失败（已重试 {attempts} 次）：{last_error}",
                    hint="检查 base_url / model 是否可用；限流时降低频率或稍后再试",
                    detail={"status": status, "model": self.cfg.model},
                )
            # 非重试类 4xx：立刻失败
            raise ModelAPIError(
                f"模型接口拒绝请求（HTTP {status}）：{self._short(text)}",
                hint="401/403 多为 api_key 无效；400 多为 model 名或参数不被支持",
                detail={"status": status, "model": self.cfg.model},
            )

        raise ModelAPIError(f"模型接口调用失败：{last_error or '未知原因'}",
                            hint="检查网络与配置后重试",
                            detail={"model": self.cfg.model})

    # ------------------------------------------------------------------ 内部
    @staticmethod
    def _validate_messages(messages: list[dict]) -> None:
        if not messages:
            raise ConfigError("messages 为空", hint="至少给一条 system 或 user 消息")
        total = sum(len(str(m.get("content", ""))) for m in messages)
        if total > MAX_MESSAGES_CHARS:
            raise ConfigError(
                f"单次请求内容 {total} 字，超过上限 {MAX_MESSAGES_CHARS} 字",
                hint="把长文拆成分段修订，不要一次把整篇稿子发给模型",
            )

    @staticmethod
    def _short(text: str, limit: int = 300) -> str:
        text = (text or "").strip().replace("\n", " ")
        return text[:limit] + ("…" if len(text) > limit else "")

    def _parse(self, text: str, *, latency_s: float, attempts: int) -> LLMResponse:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ModelAPIError(
                f"模型返回不是合法 JSON：{self._short(text)}",
                hint="确认 base_url 指向的是 OpenAI 兼容接口，而不是网页首页",
            ) from exc
        choices = data.get("choices") or []
        if not choices:
            raise ModelAPIError(
                "模型返回里没有 choices",
                hint="检查 model 名是否正确、是否被服务端内容过滤",
                detail={"raw_keys": list(data)[:8]},
            )
        message = choices[0].get("message") or {}
        content = message.get("content") or ""
        if isinstance(content, list):  # 某些服务返回分段内容
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return LLMResponse(
            text=content.strip(),
            tool_calls=list(message.get("tool_calls") or []),
            model=data.get("model", self.cfg.model),
            usage=data.get("usage") or {},
            latency_s=latency_s,
            finish_reason=choices[0].get("finish_reason", ""),
            attempts=attempts,
            raw=data,
        )
