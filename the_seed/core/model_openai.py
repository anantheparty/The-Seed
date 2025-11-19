from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

from openai import OpenAI

try:
    from openai import OpenAIError  # type: ignore
except ImportError:  # pragma: no cover - 防御性兜底
    OpenAIError = Exception  # type: ignore

from .model import ModelAdapter
from ..utils.log_manager import LogManager
from .errors import ModelInvocationError

logger = LogManager.get_logger()


@dataclass
class OpenAIModelConfig:
    model: str = "gpt-4o-mini"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    organization: Optional[str] = None
    use_responses_api: bool = False
    reasoning: bool = False
    reasoning_effort: Literal["low", "medium", "high"] = "medium"
    max_output_tokens: int = 1024
    temperature: float = 0.4
    top_p: float = 0.9
    response_format: Literal["json_schema", "json_object"] = "json_schema"
    json_schema_name: str = "AgentDecision"
    request_timeout: float = 60.0


class OpenAIModelAdapter(ModelAdapter):
    """OpenAI 通用适配器：支持 responses（含思考模型）与 chat/completions。"""

    def __init__(self, cfg: OpenAIModelConfig):
        self.cfg = cfg
        self.client = self._build_client()

    def complete(self, prompt: str, *, tools_schema: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
        tools_schema = tools_schema or []
        logger.info(
            "调用 OpenAI 模型：model=%s, mode=%s, reasoning=%s",
            self.cfg.model,
            "responses" if self.cfg.use_responses_api else "chat",
            self.cfg.reasoning,
        )
        try:
            if self.cfg.use_responses_api:
                raw = self._complete_via_responses(prompt, tools_schema)
            else:
                raw = self._complete_via_chat(prompt)
            logger.debug("OpenAI 原始输出=%s", raw)
        except ModelInvocationError:
            raise
        except Exception as exc:  # noqa: BLE001
            error = self._convert_exception(exc)
            logger.error(error.summary)
            if error.detail:
                logger.debug("OpenAI 模型错误详情：%s", error.detail)
            raise error

        result = self._ensure_output(raw)
        if not result.get("tool_calls"):
            result["tool_calls"] = []
        result.setdefault("thoughts", "")
        logger.debug("OpenAI 模型标准化输出=%s", result)
        return result

    # —— internal helpers ——
    def _build_client(self) -> OpenAI:
        api_key = self.cfg.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("缺少 OPENAI_API_KEY，无法初始化 OpenAIModelAdapter")
        params: Dict[str, Any] = {"api_key": api_key}
        if self.cfg.base_url:
            params["base_url"] = self.cfg.base_url
        if self.cfg.organization:
            params["organization"] = self.cfg.organization
        logger.info("初始化 OpenAI 客户端：base_url=%s, org=%s", self.cfg.base_url, self.cfg.organization)
        return OpenAI(**params)

    def _complete_via_chat(self, prompt: str) -> Any:
        messages = [
            {"role": "system", "content": "You must answer strictly in JSON."},
            {"role": "user", "content": prompt},
        ]
        kwargs: Dict[str, Any] = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": self.cfg.temperature,
            "top_p": self.cfg.top_p,
        }
        if self.cfg.response_format == "json_object":
            kwargs["response_format"] = {"type": "json_object"}
        logger.debug("chat.completions 请求：messages=%s kwargs=%s", messages, {k: v for k, v in kwargs.items() if k != "messages"})
        completion = self.client.chat.completions.create(**kwargs)
        message = completion.choices[0].message
        logger.debug("chat.completions 返回=%s", message)
        return getattr(message, "content", None) or "{}"

    def _complete_via_responses(self, prompt: str, tools_schema: List[Dict[str, Any]]) -> Any:
        inputs = [
            {
                "role": "system",
                "content": [{"type": "text", "text": "You must output JSON with keys thoughts/tool_calls."}],
            },
            {"role": "user", "content": [{"type": "text", "text": prompt}]},
        ]
        kwargs: Dict[str, Any] = {
            "model": self.cfg.model,
            "input": inputs,
            "temperature": self.cfg.temperature,
            "top_p": self.cfg.top_p,
            "max_output_tokens": self.cfg.max_output_tokens,
        }
        if self.cfg.response_format == "json_schema":
            kwargs["response_format"] = self._build_response_format_schema(tools_schema)
        if self.cfg.reasoning:
            kwargs["reasoning"] = {"effort": self.cfg.reasoning_effort}
        logger.debug("responses.create 请求：inputs=%s kwargs=%s", inputs, {k: v for k, v in kwargs.items() if k != "input"})
        response = self.client.responses.create(**kwargs)
        logger.debug("responses.create 返回=%s", response)
        return self._parse_responses_output(response)

    def _parse_responses_output(self, response: Any) -> Any:
        data = response.model_dump() if hasattr(response, "model_dump") else response
        output_items = data.get("output", []) if isinstance(data, dict) else []
        text_chunks: List[str] = []
        tool_calls: List[Dict[str, Any]] = []
        for item in output_items:
            for content in item.get("content", []):
                ctype = content.get("type")
                if ctype in {"output_text", "text"}:
                    text = content.get("text")
                    if isinstance(text, dict):
                        text_chunks.append(text.get("value", ""))
                    elif isinstance(text, str):
                        text_chunks.append(text)
                elif ctype == "tool_call":
                    tool_calls.append({
                        "name": content.get("name", ""),
                        "arguments": content.get("arguments", {}) or {},
                    })
        merged_text = "".join(text_chunks).strip()
        result = self._ensure_output(merged_text)
        if tool_calls and not result.get("tool_calls"):
            result["tool_calls"] = tool_calls
        return result

    def _ensure_output(self, payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            result = payload
        else:
            try:
                result = json.loads(payload)
            except (TypeError, json.JSONDecodeError):
                logger.warning("模型输出非 JSON，fallback 为 thoughts 文本")
                result = {"thoughts": str(payload or ""), "tool_calls": []}
        result.setdefault("tool_calls", [])
        result.setdefault("thoughts", "")
        return result

    def _build_response_format_schema(self, tools_schema: List[Dict[str, Any]]) -> Dict[str, Any]:
        if tools_schema:
            tool_items = {
                "oneOf": [
                    {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "const": spec["name"]},
                            "arguments": spec.get("parameters", {"type": "object"}),
                        },
                        "required": ["name", "arguments"],
                        "additionalProperties": False,
                    }
                    for spec in tools_schema
                ]
            }
        else:
            tool_items = {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "arguments": {"type": "object"},
                },
                "required": ["name", "arguments"],
                "additionalProperties": False,
            }
        schema = {
            "type": "object",
            "properties": {
                "thoughts": {"type": "string"},
                "tool_calls": {
                    "type": "array",
                    "items": tool_items,
                    "default": [],
                },
            },
            "required": ["tool_calls"],
            "additionalProperties": False,
        }
        return {
            "type": "json_schema",
            "json_schema": {
                "name": self.cfg.json_schema_name,
                "schema": schema,
            },
        }

    def _convert_exception(self, exc: Exception) -> ModelInvocationError:
        summary_parts = [f"模型 {self.cfg.model} 调用失败"]
        detail_payload: Any | None = None

        if isinstance(exc, OpenAIError) and hasattr(exc, "response"):
            response = getattr(exc, "response", None)
            if response is not None:
                detail_payload = _safe_response_json(response)

        if detail_payload:
            error_message = _extract_error_message(detail_payload)
            detail_text = json.dumps(detail_payload, ensure_ascii=False)
        else:
            error_message = str(exc)
            detail_text = repr(exc)

        if error_message:
            summary_parts.append(f"原因：{error_message}")

        summary = "；".join(summary_parts)
        return ModelInvocationError(summary=summary, detail=detail_text)


def _safe_response_json(response: Any) -> Any:
    try:
        if hasattr(response, "json"):
            return response.json()
        if hasattr(response, "text"):
            return response.text
    except Exception:  # pragma: no cover - 仅用于日志
        return None
    return None


def _extract_error_message(payload: Any) -> str:
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            if error.get("message"):
                return str(error["message"])
            if error.get("type"):
                return str(error["type"])
        if payload.get("message"):
            return str(payload["message"])
    if isinstance(payload, str):
        return payload
    return ""

