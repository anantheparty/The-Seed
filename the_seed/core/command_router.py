from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from string import Template
from typing import Any, Dict, Optional

from ..config.command_dict import (
    COMMAND_DICT,
    DIRECTION_ALIASES,
    ENTITY_ALIASES,
    FACTION_ALIASES,
    RANGE_ALIASES,
)
from ..utils import LogManager

logger = LogManager.get_logger()

try:
    from flashtext import KeywordProcessor
except Exception:  # pragma: no cover - optional dependency
    KeywordProcessor = None

try:
    from rapidfuzz import fuzz
except Exception:  # pragma: no cover - optional dependency
    fuzz = None


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
        direction_aliases: Optional[Dict[str, list[str]]] = None,
        faction_aliases: Optional[Dict[str, list[str]]] = None,
        range_aliases: Optional[Dict[str, list[str]]] = None,
    ) -> None:
        self.enabled = enabled
        self.similarity_threshold = similarity_threshold
        self.command_dict = command_dict or self._load_dict(dict_path) or COMMAND_DICT
        self.entity_aliases = entity_aliases or ENTITY_ALIASES
        self.direction_aliases = direction_aliases or DIRECTION_ALIASES
        self.faction_aliases = faction_aliases or FACTION_ALIASES
        self.range_aliases = range_aliases or RANGE_ALIASES

        self._entity_alias_map = self._build_alias_map(self.entity_aliases)
        self._direction_alias_map = self._build_alias_map(self.direction_aliases)
        self._faction_alias_map = self._build_alias_map(self.faction_aliases)
        self._range_alias_map = self._build_alias_map(self.range_aliases)

        self._entity_kp = self._build_keyword_processor(self.entity_aliases)
        self._direction_kp = self._build_keyword_processor(self.direction_aliases)
        self._faction_kp = self._build_keyword_processor(self.faction_aliases)
        self._range_kp = self._build_keyword_processor(self.range_aliases)

    def route(self, command: str) -> RouteResult:
        if not self.enabled:
            return RouteResult(matched=False, reason="disabled")

        normalized = self._normalize(command)
        if not normalized:
            return RouteResult(matched=False, reason="empty_command")

        entities_hint = self._extract_common_entities(normalized)

        intent, score = self._match_intent(normalized)
        intent, score = self._apply_entity_heuristics(intent, score, entities_hint)
        if not intent:
            return RouteResult(matched=False, reason="no_intent", entities=entities_hint)
        threshold = self._adaptive_threshold(normalized, score)
        if score < threshold:
            return RouteResult(
                matched=False,
                intent=intent,
                score=score,
                reason="low_confidence",
                entities=entities_hint,
            )

        entities = self._extract_entities(normalized, intent)
        template = self.command_dict[intent].get("template", "")
        code = self._render_template(intent, template, entities)
        if not code:
            return RouteResult(
                matched=False,
                intent=intent,
                score=score,
                reason="render_failed",
                entities=entities,
            )

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
        return self._strip_fillers(text)

    @staticmethod
    def _strip_fillers(text: str) -> str:
        fillers = [
            "来个",
            "来一个",
            "来一辆",
            "给我",
            "帮我",
            "一下",
            "帮忙",
            "请",
        ]
        for filler in fillers:
            text = text.replace(filler, "")
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
                    score = self._similarity(command, s_norm)
                if score > best_score:
                    best_score = score
                    best_intent = intent

        return best_intent, best_score

    def _apply_entity_heuristics(
        self,
        intent: Optional[str],
        score: float,
        entities: Dict[str, Any],
    ) -> tuple[Optional[str], float]:
        unit = entities.get("unit")
        count = entities.get("count")

        if unit and intent is None:
            return "produce", max(score, 0.7)

        if intent == "produce" and unit:
            bonus = 0.2
            if count and count > 1:
                bonus += 0.05
            return intent, min(1.0, score + bonus)

        return intent, score

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        if fuzz is not None:
            return fuzz.token_set_ratio(a, b) / 100.0
        return SequenceMatcher(None, a, b).ratio()

    @staticmethod
    def _adaptive_threshold(command: str, score: float) -> float:
        if len(command) <= 4 and score >= 0.5:
            return 0.5
        if len(command) <= 6 and score >= 0.6:
            return 0.6
        return 0.72

    @staticmethod
    def _build_alias_map(alias_groups: Dict[str, list[str]]) -> Dict[str, str]:
        alias_map: Dict[str, str] = {}
        for canonical, aliases in alias_groups.items():
            for alias in aliases:
                alias_map[alias.lower()] = canonical
        return alias_map

    def _extract_entities(self, command: str, intent: str) -> Dict[str, Any]:
        if intent == "attack":
            return self._extract_attack_entities(command)
        return self._extract_common_entities(command)

    def _extract_common_entities(self, command: str) -> Dict[str, Any]:
        entities: Dict[str, Any] = {}

        unit = self._match_alias(command, self._entity_alias_map, self._entity_kp)
        if unit:
            entities["unit"] = unit

        faction = self._match_alias(command, self._faction_alias_map, self._faction_kp)
        if faction:
            entities["faction"] = faction

        range_ = self._match_alias(command, self._range_alias_map, self._range_kp)
        if range_:
            entities["range"] = range_

        direction = self._match_alias(command, self._direction_alias_map, self._direction_kp)
        if direction:
            entities["direction"] = direction

        group_id = self._extract_group_id(command)
        if group_id is not None:
            entities["group_id"] = group_id

        actor_id = self._extract_actor_id(command)
        if actor_id is not None:
            entities["actor_id"] = actor_id

        # count
        count = self._extract_count(command)
        if count:
            entities["count"] = count
        else:
            entities["count"] = 1

        return entities

    def _extract_attack_entities(self, command: str) -> Dict[str, Any]:
        entities = self._extract_common_entities(command)

        attacker_segment, target_segment = self._split_attack_segments(command)
        attacker_type = self._match_alias(attacker_segment, self._entity_alias_map, self._entity_kp)
        target_type = self._match_alias(target_segment, self._entity_alias_map, self._entity_kp)

        if attacker_type:
            entities["attacker_type"] = attacker_type
        if target_type:
            entities["target_type"] = target_type

        if "敌" in command and "target_faction" not in entities:
            entities["target_faction"] = "敌方"

        return entities

    def _split_attack_segments(self, command: str) -> tuple[str, str]:
        patterns = [
            r"用(?P<attacker>.+?)攻击(?P<target>.+)",
            r"用(?P<attacker>.+?)打(?P<target>.+)",
            r"让(?P<attacker>.+?)攻击(?P<target>.+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                return match.group("attacker"), match.group("target")
        return command, command

    def _match_alias(
        self,
        command: str,
        alias_map: Dict[str, str],
        processor: Optional["KeywordProcessor"],
    ) -> Optional[str]:
        if processor is not None:
            matches = processor.extract_keywords(command)
            if matches:
                return matches[0]

        best_alias = ""
        best_canonical: Optional[str] = None
        for alias, canonical in alias_map.items():
            if alias and alias in command and len(alias) > len(best_alias):
                best_alias = alias
                best_canonical = canonical
        return best_canonical

    @staticmethod
    def _build_keyword_processor(alias_groups: Dict[str, list[str]]):
        if KeywordProcessor is None:
            return None
        processor = KeywordProcessor(case_sensitive=False)
        for canonical, aliases in alias_groups.items():
            for alias in aliases:
                processor.add_keyword(alias, canonical)
        return processor

    def _extract_group_id(self, command: str) -> Optional[int]:
        match = re.search(r"编组\s*(\d+)", command)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    def _extract_actor_id(self, command: str) -> Optional[int]:
        match = re.search(r"(?:id|ID)\s*(\d+)", command)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

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

    def _render_template(self, intent: str, template: str, entities: Dict[str, Any]) -> Optional[str]:
        if not template:
            return None

        if intent == "produce":
            unit = entities.get("unit")
            count = entities.get("count")
            if not unit:
                return None
            return Template(template).safe_substitute(unit=unit, count=count or 1).strip()

        if intent == "attack":
            attackers = self._build_targets_expr(
                type_list=self._list_or_none(entities.get("attacker_type")),
                faction="己方",
                range_=entities.get("range") or "selected",
            )
            targets = self._build_targets_expr(
                type_list=self._list_or_none(entities.get("target_type") or entities.get("unit")),
                faction=entities.get("target_faction") or entities.get("faction") or "敌方",
                range_=entities.get("range") or "screen",
            )
            return Template(template).safe_substitute(attackers=attackers, targets=targets).strip()

        if intent == "explore":
            units = self._build_targets_expr(
                type_list=self._list_or_none(entities.get("unit")),
                faction=entities.get("faction") or "己方",
                range_=entities.get("range") or "selected",
            )
            return Template(template).safe_substitute(units=units).strip()

        if intent == "mine":
            harvesters = self._build_targets_expr(
                type_list=["矿车"],
                faction=entities.get("faction") or "己方",
                range_=entities.get("range") or "all",
            )
            return Template(template).safe_substitute(harvesters=harvesters).strip()

        if intent == "query_actor":
            targets = self._build_targets_expr(
                type_list=self._list_or_none(entities.get("unit")),
                faction=entities.get("faction"),
                range_=entities.get("range") or "all",
                group_id=entities.get("group_id"),
                actor_id=entities.get("actor_id"),
            )
            return Template(template).safe_substitute(targets=targets).strip()

        return Template(template).safe_substitute(**entities).strip()

    @staticmethod
    def _list_or_none(value: Optional[str]) -> Optional[list[str]]:
        if not value:
            return None
        return [value]

    def _build_targets_expr(
        self,
        *,
        type_list: Optional[list[str]] = None,
        faction: Optional[str] = None,
        range_: Optional[str] = None,
        group_id: Optional[int] = None,
        actor_id: Optional[int] = None,
    ) -> str:
        parts: list[str] = []
        if type_list:
            parts.append(f"type={type_list!r}")
        if faction:
            parts.append(f"faction={faction!r}")
        if range_:
            parts.append(f"range={range_!r}")
        if group_id is not None:
            parts.append(f"groupId={[group_id]!r}")
        if actor_id is not None:
            parts.append(f"actorId={[actor_id]!r}")

        return f"TargetsQueryParam({', '.join(parts)})" if parts else "TargetsQueryParam(range='selected')"

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
