from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from string import Template
from typing import Any, Dict, Optional

from ..config.command_dict import COMMAND_DICT, ENTITY_ALIASES
from ..utils import LogManager

logger = LogManager.get_logger()


@dataclass(frozen=True)
class RouteResult:
    matched: bool
    intent: Optional[str] = None
    score: float = 0.0
    code: str = ""
    reason: str = ""
    entities: Optional[Dict[str, Any]] = None


class CommandRouter:
    """Lightweight rule-based command router with optional similarity matching."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        similarity_threshold: float = 0.72,
        command_dict: Optional[Dict[str, Dict[str, Any]]] = None,
        dict_path: Optional[str] = None,
        entity_aliases: Optional[Dict[str, list[str]]] = None,
    ) -> None:
        self.enabled = enabled
        self.similarity_threshold = similarity_threshold
        self.command_dict = command_dict or self._load_dict(dict_path) or COMMAND_DICT
        self.entity_aliases = entity_aliases or ENTITY_ALIASES

    def route(self, command: str) -> RouteResult:
        if not self.enabled:
            return RouteResult(matched=False, reason="disabled")

        normalized = self._normalize(command)
        if not normalized:
            return RouteResult(matched=False, reason="empty_command")

        intent, score = self._match_intent(normalized)
        if not intent:
            return RouteResult(matched=False, reason="no_intent")
        if score < self.similarity_threshold:
            return RouteResult(matched=False, intent=intent, score=score, reason="low_confidence")

        entities = self._extract_entities(normalized)
        template = self.command_dict[intent].get("template", "")
        if intent == "produce":
            unit = entities.get("unit") if entities else None
            count = entities.get("count") if entities else None
            if not unit:
                return RouteResult(
                    matched=False,
                    intent=intent,
                    score=score,
                    reason="missing_unit",
                    entities=entities,
                )
            code = Template(template).safe_substitute(unit=unit, count=count or 1)
        else:
            code = template

        if not code.strip():
            return RouteResult(
                matched=False,
                intent=intent,
                score=score,
                reason="empty_template",
                entities=entities,
            )

        return RouteResult(
            matched=True,
            intent=intent,
            score=score,
            code=code,
            reason="matched",
            entities=entities,
        )

    def _load_dict(self, dict_path: Optional[str]) -> Optional[Dict[str, Dict[str, Any]]]:
        if not dict_path:
            return None
        try:
            path = Path(dict_path)
            if not path.exists():
                logger.warning("CommandRouter: dict_path not found: %s", dict_path)
                return None
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception as e:
            logger.warning("CommandRouter: failed to load dict: %s", e)
        return None

    def _normalize(self, text: str) -> str:
        text = (text or "").strip().lower()
        text = re.sub(r"\s+", "", text)
        return text

    def _match_intent(self, command: str) -> tuple[Optional[str], float]:
        best_intent: Optional[str] = None
        best_score = 0.0

        for intent, rule in self.command_dict.items():
            synonyms = rule.get("synonyms", [])
            for s in synonyms:
                s_norm = self._normalize(s)
                if not s_norm:
                    continue
                if s_norm in command:
                    score = 1.0
                else:
                    score = SequenceMatcher(None, command, s_norm).ratio()
                if score > best_score:
                    best_score = score
                    best_intent = intent

        return best_intent, best_score

    def _extract_entities(self, command: str) -> Dict[str, Any]:
        entities: Dict[str, Any] = {}

        # unit/building names
        for canonical, aliases in self.entity_aliases.items():
            for alias in aliases:
                alias_norm = self._normalize(alias)
                if alias_norm and alias_norm in command:
                    entities["unit"] = canonical
                    break
            if "unit" in entities:
                break

        # count
        count = self._extract_count(command)
        if count:
            entities["count"] = count
        else:
            entities["count"] = 1

        return entities

    def _extract_count(self, command: str) -> Optional[int]:
        digit_match = re.search(r"(\d+)", command)
        if digit_match:
            try:
                return int(digit_match.group(1))
            except ValueError:
                pass

        chinese_match = re.search(r"([一二三四五六七八九十两]+)", command)
        if not chinese_match:
            return None

        return self._parse_chinese_number(chinese_match.group(1))

    def _parse_chinese_number(self, text: str) -> Optional[int]:
        mapping = {
            "零": 0,
            "一": 1,
            "二": 2,
            "两": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
        }
        if text == "十":
            return 10
        if "十" in text:
            left, _, right = text.partition("十")
            tens = mapping.get(left, 1 if left == "" else 0)
            ones = mapping.get(right, 0) if right else 0
            if tens == 0 and left != "":
                return None
            return tens * 10 + ones
        return mapping.get(text)
