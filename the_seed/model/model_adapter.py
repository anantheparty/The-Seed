from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

from openai import OpenAI

from ..config.schema import ModelConfig
from ..utils import LogManager

logger = LogManager.get_logger()


@dataclass
class ModelResponse:
    """Model response object."""

    text: str
    raw: Dict[str, Any]

class ModelFactory:
    @staticmethod
    def build(node: str, cfg: ModelConfig) -> ModelAdapter:
        if cfg.request_type == "openai":
            return _OpenAIClient(node, cfg)
        else:
            raise ValueError(f"Unsupported request type: {cfg.request_type}")

class ModelAdapter:
    """
    Base Model adapter.
    """

    def __init__(self, node: str, cfg: ModelConfig):
        raise NotImplementedError

    def complete(self, *, system: str, user: str, metadata: Optional[Dict[str, Any]] = None) -> ModelResponse:
        raise NotImplementedError

class _OpenAIClient(ModelAdapter):
    def __init__(self, node: str, cfg: ModelConfig):
        self.name = node
        self.api_key = cfg.api_key
        self.base_url = cfg.base_url
        self.model = cfg.model
        self.temperature = cfg.temperature
        self.top_p = cfg.top_p
        self.timeout = 30

        self._client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def complete(self, *, system: str, user: str, metadata: Optional[Dict[str, Any]] = None) -> ModelResponse:
        messages = self._build_messages(system, user)
        client = self._client.with_options(timeout=self.timeout)

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            **self._chat_kwargs(),
        )

        data = response.model_dump()
        text = self._extract_text(data)
        return ModelResponse(text=text, raw=data)

    def _chat_kwargs(self) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {}
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if self.top_p is not None:
            kwargs["top_p"] = self.top_p
        return kwargs

    @staticmethod
    def _build_messages(system: str, user: str) -> list[Dict[str, str]]:
        messages: list[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        if user:
            messages.append({"role": "user", "content": user})
        return messages

    @staticmethod
    def _extract_text(data: Dict[str, Any]) -> str:
        if "choices" in data:
            choice = data["choices"][0]
            message = choice.get("message") or {}
            return (message.get("content") or "").strip()

        output_blocks = data.get("output") or []
        collected: list[str] = []
        for block in output_blocks:
            for item in block.get("content", []):
                if item.get("type") == "output_text":
                    collected.append(item.get("text", ""))
        if collected:
            return "\n".join(collected).strip()

        text_items = data.get("output_text")
        if isinstance(text_items, list) and text_items:
            return "\n".join(text_items).strip()

        return str(data)


