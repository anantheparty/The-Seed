from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from string import Template
from typing import Any, Dict, Optional

from .command_dict import (
    COMMAND_DICT,
    COUNT_CLASSIFIERS,
    DEFAULT_COMMAND_TEMPLATE_DIR,
    DIRECTION_ALIASES,
    ENTITY_ALIASES,
    FACTION_ALIASES,
    PRODUCE_SEPARATORS,
    RANGE_ALIASES,
    SEQUENCE_CONNECTORS,
)
from ....utils import LogManager

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


@dataclass(frozen=True)
class ClauseRouteResult:
    matched: bool
    intent: Optional[str] = None
    score: float = 0.0
    reason: str = ""
    entities: Optional[Dict[str, Any]] = None
    step_code: str = ""


class CommandRouter:
    """Lightweight rule-based command router with optional similarity matching."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        similarity_threshold: float = 0.72,
        command_dict: Optional[Dict[str, Dict[str, Any]]] = None,
        dict_path: Optional[str] = None,
        template_dir: Optional[str] = None,
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

        self.template_dir = self._resolve_template_dir(template_dir, dict_path)
        self._step_template_map = self._load_step_templates()
        self._wrapper_template_map = self._load_wrapper_templates()

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

        clauses = self._split_sequence_clauses(normalized)
        if len(clauses) >= 2:
            return self._route_sequence(clauses)

        single_result = self._route_single_clause(normalized, for_sequence=False)
        if not single_result.matched:
            return RouteResult(
                matched=False,
                intent=single_result.intent,
                score=single_result.score,
                reason=single_result.reason,
                entities=single_result.entities,
            )

        code = self._render_single_wrapper(single_result.step_code, single_result.intent)
        if not code:
            return RouteResult(
                matched=False,
                intent=single_result.intent,
                score=single_result.score,
                reason="wrapper_missing",
                entities=single_result.entities,
            )

        return RouteResult(
            matched=True,
            intent=single_result.intent,
            score=single_result.score,
            code=code,
            reason="matched",
            entities=single_result.entities,
        )

    def _route_sequence(self, clauses: list[str]) -> RouteResult:
        if len(clauses) > 6:
            return RouteResult(
                matched=False,
                intent="composite_sequence",
                reason="sequence_too_long",
                entities={"clauses": clauses, "step_count": len(clauses)},
            )

        step_codes: list[str] = []
        step_intents: list[str] = []
        step_scores: list[float] = []
        step_entities: list[Dict[str, Any]] = []

        for idx, clause in enumerate(clauses, start=1):
            result = self._route_single_clause(clause, for_sequence=True)
            if not result.matched:
                return RouteResult(
                    matched=False,
                    intent="composite_sequence",
                    score=result.score,
                    reason=f"sequence_clause_failed_{idx}:{result.reason}",
                    entities={
                        "clauses": clauses,
                        "failed_index": idx,
                        "failed_clause": clause,
                        "failed_intent": result.intent,
                        "step_count": len(clauses),
                    },
                )

            if not result.intent:
                return RouteResult(
                    matched=False,
                    intent="composite_sequence",
                    reason=f"sequence_clause_failed_{idx}:no_intent",
                    entities={"clauses": clauses, "failed_index": idx, "step_count": len(clauses)},
                )

            step_codes.append(result.step_code)
            step_intents.append(result.intent)
            step_scores.append(result.score)
            step_entities.append(result.entities or {})

        code = self._render_sequence_wrapper(step_codes, step_intents, clauses)
        if not code:
            return RouteResult(
                matched=False,
                intent="composite_sequence",
                reason="wrapper_missing",
                entities={"clauses": clauses, "step_count": len(clauses)},
            )

        score = min(step_scores) if step_scores else 0.0
        return RouteResult(
            matched=True,
            intent="composite_sequence",
            score=score,
            code=code,
            reason="matched",
            entities={
                "clauses": clauses,
                "step_intents": step_intents,
                "step_scores": step_scores,
                "step_entities": step_entities,
                "step_count": len(clauses),
            },
        )

    def _route_single_clause(self, clause: str, *, for_sequence: bool) -> ClauseRouteResult:
        entities_hint = self._extract_common_entities(clause)

        intent, score = self._match_intent(clause)
        intent, score = self._apply_entity_heuristics(intent, score, entities_hint, clause)
        if not intent:
            return ClauseRouteResult(
                matched=False,
                score=score,
                reason="no_intent",
                entities=entities_hint,
            )

        threshold = self._adaptive_threshold(clause, score)
        if score < threshold:
            return ClauseRouteResult(
                matched=False,
                intent=intent,
                score=score,
                reason="low_confidence",
                entities=entities_hint,
            )

        rule = self.command_dict.get(intent, {})
        if for_sequence and not bool(rule.get("allow_in_sequence", True)):
            return ClauseRouteResult(
                matched=False,
                intent=intent,
                score=score,
                reason="intent_not_allowed_in_sequence",
                entities=entities_hint,
            )

        entities = self._extract_entities(clause, intent)
        step_template = self._step_template_map.get(intent)
        if step_template is None:
            return ClauseRouteResult(
                matched=False,
                intent=intent,
                score=score,
                reason="template_missing",
                entities=entities,
            )

        if not step_template.strip():
            return ClauseRouteResult(
                matched=False,
                intent=intent,
                score=score,
                reason="empty_template",
                entities=entities,
            )

        step_code = self._render_step_template(intent, step_template, entities)
        if not step_code:
            return ClauseRouteResult(
                matched=False,
                intent=intent,
                score=score,
                reason="render_failed",
                entities=entities,
            )

        return ClauseRouteResult(
            matched=True,
            intent=intent,
            score=score,
            reason="matched",
            entities=entities,
            step_code=step_code,
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

    def _resolve_template_dir(self, template_dir: Optional[str], dict_path: Optional[str]) -> Path:
        if template_dir:
            return Path(template_dir)
        if dict_path:
            return Path(dict_path).parent / DEFAULT_COMMAND_TEMPLATE_DIR
        return Path(__file__).resolve().parents[1] / DEFAULT_COMMAND_TEMPLATE_DIR

    def _load_step_templates(self) -> Dict[str, Optional[str]]:
        template_map: Dict[str, Optional[str]] = {}
        for intent, rule in self.command_dict.items():
            template_path = self._resolve_template_path(
                intent=intent,
                rule=rule,
                template_field="step_template_file",
                default_relative=f"steps/{intent}.py.tmpl",
            )
            try:
                template_map[intent] = template_path.read_text(encoding="utf-8")
            except FileNotFoundError:
                logger.warning(
                    "CommandRouter: step template not found for intent=%s path=%s",
                    intent,
                    template_path,
                )
                template_map[intent] = None
            except Exception as e:
                logger.warning(
                    "CommandRouter: failed to load step template intent=%s path=%s err=%s",
                    intent,
                    template_path,
                    e,
                )
                template_map[intent] = None
        return template_map

    def _load_wrapper_templates(self) -> Dict[str, Optional[str]]:
        wrappers = {
            "single_action": self.template_dir / "wrappers" / "single_action.py.tmpl",
            "sequence_action": self.template_dir / "wrappers" / "sequence_action.py.tmpl",
        }
        loaded: Dict[str, Optional[str]] = {}
        for key, path in wrappers.items():
            try:
                loaded[key] = path.read_text(encoding="utf-8")
            except FileNotFoundError:
                logger.warning("CommandRouter: wrapper template not found key=%s path=%s", key, path)
                loaded[key] = None
            except Exception as e:
                logger.warning(
                    "CommandRouter: failed to load wrapper template key=%s path=%s err=%s",
                    key,
                    path,
                    e,
                )
                loaded[key] = None
        return loaded

    def _resolve_template_path(
        self,
        *,
        intent: str,
        rule: Dict[str, Any],
        template_field: str,
        default_relative: str,
    ) -> Path:
        template_file = rule.get(template_field)
        if template_file:
            candidate = Path(str(template_file))
            if candidate.is_absolute():
                return candidate
            return self.template_dir / candidate
        return self.template_dir / default_relative

    def _normalize(self, text: str) -> str:
        text = (text or "").strip().lower()
        text = re.sub(r"\s+", "", text)
        text = self._strip_fillers(text)
        text = self._strip_polite_tail(text)
        return text

    @staticmethod
    def _strip_fillers(text: str) -> str:
        fillers = [
            "请帮我",
            "麻烦你",
            "麻烦",
            "烦请",
            "劳烦",
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

    @staticmethod
    def _strip_polite_tail(text: str) -> str:
        tail_tokens = [
            "谢谢你",
            "谢谢",
            "辛苦了",
            "辛苦",
            "快点",
            "赶紧",
            "立刻",
            "马上",
            "尽快",
            "好吗",
            "好么",
            "好嘛",
            "行吗",
            "吧",
            "哈",
            "呀",
            "啊",
            "啦",
            "呢",
            "哦",
        ]
        out = text
        changed = True
        while changed and out:
            changed = False
            out = out.rstrip("!！。?？~～,，;； ")
            for token in tail_tokens:
                if out.endswith(token):
                    out = out[: -len(token)]
                    changed = True
                    break
        return out.rstrip("!！。?？~～,，;； ")

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
        command: str,
    ) -> tuple[Optional[str], float]:
        unit = entities.get("unit")
        count = entities.get("count")
        looks_query = self._looks_like_query(command)
        looks_produce = self._looks_like_produce(command)
        looks_expand_mine = self._looks_like_expand_mine(command)
        looks_implicit_produce = self._looks_like_implicit_produce(command, unit)
        looks_stop_attack = self._looks_like_stop_attack(command)
        looks_global_attack = self._looks_like_global_attack(command)

        if looks_stop_attack:
            return "stop_attack", max(score, 0.90)

        if looks_global_attack:
            return "attack", max(score, 0.90)

        if looks_expand_mine:
            return "produce", max(score, 0.92)

        if looks_implicit_produce and unit and not looks_query:
            return "produce", max(score, 0.88)

        if looks_query and unit:
            if intent in (None, "produce"):
                return "query_actor", max(score, 0.82)
            if intent == "query_actor":
                return intent, min(1.0, score + 0.1)

        if looks_produce and intent == "query_actor":
            return "produce", max(score, 0.82)

        if unit and intent is None and not looks_query:
            return "produce", max(score, 0.7)

        if intent == "produce" and unit:
            bonus = 0.2
            if count and count > 1:
                bonus += 0.05
            return intent, min(1.0, score + bonus)

        if intent == "query_actor" and unit:
            return intent, min(1.0, score + 0.1)

        return intent, score

    @staticmethod
    def _looks_like_query(command: str) -> bool:
        return bool(
            re.search(
                r"(查询|查看|列出|查下|看下|看看|查兵|查单位|有多少|多少|几辆|几只|几架|兵力|状态|战况|局势|概况|情况)",
                command,
            )
        )

    @staticmethod
    def _looks_like_status_query(command: str) -> bool:
        return bool(
            re.search(
                r"(状态|战况|局势|概况|战场情况|当前情况|目前情况|资源情况|电力情况|兵力情况)",
                command,
            )
        )

    @staticmethod
    def _looks_like_produce(command: str) -> bool:
        return bool(
            re.search(
                r"(建造|生产|训练|制造|造|补(?!给)|爆兵|出兵|起兵|来一个|来一辆|搞一个|整一个|下电|补电|下兵营|下车间|开车间|拍兵)",
                command,
            )
        )

    @staticmethod
    def _looks_like_expand_mine(command: str) -> bool:
        return bool(
            re.search(
                r"(开(?:[一二三四五六七八九十两\d]+)?矿|开分矿|双矿|三矿|起矿|拉矿场|补矿)",
                command,
            )
        )

    @staticmethod
    def _looks_like_implicit_produce(command: str, unit: Optional[str]) -> bool:
        if not unit:
            return False
        if re.search(r"(展开|部署|下基地|开基地|基地车|建造车|mcv)", command):
            return False
        if re.search(r"(采矿|挖矿|采集|矿车干活|矿车采矿|去矿区|拉钱|采钱)", command):
            return False
        if re.search(r"(侦察|侦查|探索|探路|探图|开图)", command):
            return False
        if re.search(r"(查询|查看|列出|查下|看下|看看|有多少|多少|几辆|几只|几架|兵力|状态|战况|局势|概况|情况)", command):
            return False
        if re.search(r"(攻击|进攻|突袭|集火|停火|停止攻击|停止进攻|取消攻击)", command):
            return False
        if re.search(r"^([0-9一二三四五六七八九十两]+)(个|辆|座|架|名|只|台)?", command):
            return True
        return bool(re.fullmatch(r"[\u4e00-\u9fffA-Za-z0-9]{1,8}", command))

    @staticmethod
    def _looks_like_stop_attack(command: str) -> bool:
        return bool(
            re.search(
                r"(停火|停止(?:攻击|进攻|开火|作战|行动)|取消(?:攻击|进攻)|别攻击|不要攻击|先停手|停一停)",
                command,
            )
        )

    @staticmethod
    def _looks_like_global_attack(command: str) -> bool:
        return bool(
            re.search(
                r"(全面(?:进攻|攻击)|全军出击|总攻|总进攻|全线进攻|反攻|压上去|打过去|推过去)",
                command,
            )
        )

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        if fuzz is not None:
            return fuzz.token_set_ratio(a, b) / 100.0
        return SequenceMatcher(None, a, b).ratio()

    def _adaptive_threshold(self, command: str, score: float) -> float:
        if len(command) <= 4 and score >= 0.5:
            return 0.5
        if len(command) <= 6 and score >= 0.6:
            return 0.6
        return self.similarity_threshold

    @staticmethod
    def _build_alias_map(alias_groups: Dict[str, list[str]]) -> Dict[str, str]:
        alias_map: Dict[str, str] = {}
        for canonical, aliases in alias_groups.items():
            for alias in aliases:
                alias_map[alias.lower()] = canonical
        return alias_map

    def _extract_entities(self, command: str, intent: str) -> Dict[str, Any]:
        if intent == "produce":
            return self._extract_produce_entities(command)
        if intent == "attack":
            return self._extract_attack_entities(command)
        if intent == "stop_attack":
            return self._extract_stop_attack_entities(command)
        if intent == "query_actor":
            return self._extract_query_entities(command)
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

        count = self._extract_count(command)
        entities["count"] = count or 1

        return entities

    def _extract_produce_entities(self, command: str) -> Dict[str, Any]:
        entities = self._extract_common_entities(command)
        items = self._extract_production_items(command)

        if not items and self._looks_like_expand_mine(command):
            mine_count = self._extract_expand_mine_count(command)
            items = [{"unit": "矿场", "count": mine_count}]

        if items:
            entities["production_items"] = items
            entities["unit"] = items[0]["unit"]
            entities["count"] = items[0]["count"]
        elif entities.get("unit"):
            entities["production_items"] = [
                {
                    "unit": entities["unit"],
                    "count": entities.get("count") or 1,
                }
            ]

        return entities

    @staticmethod
    def _extract_expand_mine_count(command: str) -> int:
        m = re.search(r"开([一二三四五六七八九十两\d]+)矿", command)
        if m:
            raw = m.group(1)
            if raw.isdigit():
                return max(1, int(raw))
            simple = {
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
                "十": 10,
            }
            if raw in simple:
                return simple[raw]
        if "双矿" in command:
            return 2
        if "三矿" in command:
            return 3
        return 1

    def _extract_production_items(self, command: str) -> list[Dict[str, Any]]:
        segments = self._split_by_keywords(command, PRODUCE_SEPARATORS)
        if not segments:
            segments = [command]

        items: list[Dict[str, Any]] = []
        for segment in segments:
            unit = self._match_alias(segment, self._entity_alias_map, self._entity_kp)
            if not unit:
                continue
            count = self._extract_count(segment) or 1
            items.append({"unit": unit, "count": count})

        if not items:
            unit = self._match_alias(command, self._entity_alias_map, self._entity_kp)
            if unit:
                items.append({"unit": unit, "count": self._extract_count(command) or 1})

        return items

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

        if self._looks_like_global_attack(command):
            entities["global_attack"] = True
            entities["faction"] = "己方"
            entities["target_faction"] = "敌方"
            entities["range"] = "all"

        return entities

    def _extract_stop_attack_entities(self, command: str) -> Dict[str, Any]:
        entities = self._extract_common_entities(command)
        entities["faction"] = "己方"
        if "target_faction" not in entities:
            entities["target_faction"] = "敌方"
        return entities

    def _extract_query_entities(self, command: str) -> Dict[str, Any]:
        entities = self._extract_common_entities(command)
        status_query = self._looks_like_status_query(command)
        if status_query:
            entities["status_query"] = True
            # "看下状态/查下状态"里的“下”经常被误判成方向“南”。
            if entities.get("direction") == "南" and re.search(
                r"(看下|查下|看一下|查一下|看一眼|查一查|看一看)",
                command,
            ):
                entities.pop("direction", None)
        return entities

    def _split_attack_segments(self, command: str) -> tuple[str, str]:
        patterns = [
            r"用(?P<attacker>.+?)攻击(?P<target>.+)",
            r"用(?P<attacker>.+?)打(?P<target>.+)",
            r"让(?P<attacker>.+?)攻击(?P<target>.+)",
            r"让(?P<attacker>.+?)进攻(?P<target>.+)",
            r"让(?P<attacker>.+?)突袭(?P<target>.+)",
            r"派(?P<attacker>.+?)攻击(?P<target>.+)",
            r"派(?P<attacker>.+?)进攻(?P<target>.+)",
            r"派(?P<attacker>.+?)突袭(?P<target>.+)",
            r"命令(?P<attacker>.+?)攻击(?P<target>.+)",
            r"命令(?P<attacker>.+?)进攻(?P<target>.+)",
            r"(?P<attacker>.+?)进攻(?P<target>.+)",
            r"(?P<attacker>.+?)突袭(?P<target>.+)",
            r"(?P<attacker>.+?)打(?P<target>.+)",
            r"(?P<attacker>.+?)集火(?P<target>.+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                return match.group("attacker"), match.group("target")
        return command, command

    def _split_sequence_clauses(self, command: str) -> list[str]:
        parts = self._split_by_keywords(command, SEQUENCE_CONNECTORS)
        cleaned: list[str] = []
        for part in parts:
            clause = self._strip_sequence_prefixes(part)
            clause = self._strip_fillers(clause)
            clause = self._strip_polite_tail(clause)
            clause = clause.strip("!！。?？~～,，;； ")
            if clause and not self._is_non_semantic_clause(clause):
                cleaned.append(clause)

        if len(cleaned) >= 2:
            return cleaned
        return [command]

    @staticmethod
    def _is_non_semantic_clause(text: str) -> bool:
        return bool(
            re.fullmatch(
                r"(快点|赶紧|立刻|马上|尽快|谢谢你?|辛苦了?|好的|好|吧|呀|啊|哈|啦|呢|哦)+",
                text,
            )
        )

    @staticmethod
    def _strip_sequence_prefixes(text: str) -> str:
        prefixes = ["先", "然后", "再", "接着", "随后", "之后", "并且", "并"]
        output = text
        changed = True
        while changed:
            changed = False
            for prefix in prefixes:
                if output.startswith(prefix):
                    output = output[len(prefix) :]
                    changed = True
        return output

    @staticmethod
    def _split_by_keywords(text: str, keywords: list[str]) -> list[str]:
        escaped = [re.escape(x) for x in sorted(set(keywords), key=len, reverse=True) if x]
        if not escaped:
            return [text]

        pattern = r"(?:" + "|".join(escaped) + r")"
        parts = [p for p in re.split(pattern, text) if p]
        return parts

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
        classifier_pattern = "|".join(re.escape(x) for x in COUNT_CLASSIFIERS)

        digit_match = re.search(rf"(?<![a-zA-Z])(\d+)\s*(?:{classifier_pattern})?", command)
        if digit_match:
            try:
                return int(digit_match.group(1))
            except ValueError:
                pass

        chinese_match = re.search(
            rf"([一二三四五六七八九十两]+)\s*(?:{classifier_pattern})?",
            command,
        )
        if not chinese_match:
            return None

        return self._parse_chinese_number(chinese_match.group(1))

    def _render_step_template(self, intent: str, template: str, entities: Dict[str, Any]) -> Optional[str]:
        if not template:
            return None

        if intent == "produce":
            items = entities.get("production_items") or []
            produce_items_code = self._build_production_items_code(items)
            if not produce_items_code:
                return None
            return Template(template).safe_substitute(
                unit=entities.get("unit", ""),
                count=entities.get("count", 1),
                production_items_code=produce_items_code,
            ).strip()

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
            return Template(template).safe_substitute(
                attackers=attackers,
                targets=targets,
                global_attack=str(bool(entities.get("global_attack"))),
            ).strip()

        if intent == "stop_attack":
            units = self._build_targets_expr(
                type_list=self._list_or_none(entities.get("attacker_type") or entities.get("unit")),
                faction=entities.get("faction") or "己方",
                range_=entities.get("range") or "selected",
            )
            fallback_units = self._build_targets_expr(
                type_list=self._list_or_none(entities.get("attacker_type") or entities.get("unit")),
                faction=entities.get("faction") or "己方",
                range_="all",
            )
            return Template(template).safe_substitute(
                units=units,
                fallback_units=fallback_units,
            ).strip()

        if intent == "explore":
            units = self._build_targets_expr(
                type_list=self._list_or_none(entities.get("unit")),
                faction=entities.get("faction") or "己方",
                range_=entities.get("range") or "selected",
            )
            return Template(template).safe_substitute(
                units=units,
                has_unit_filter=str(bool(entities.get("unit"))),
            ).strip()

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
            has_query_filter = any(
                entities.get(k) is not None and entities.get(k) != ""
                for k in ("unit", "faction", "group_id", "actor_id", "direction")
            )
            return Template(template).safe_substitute(
                targets=targets,
                status_query=str(bool(entities.get("status_query"))),
                has_query_filter=str(bool(has_query_filter)),
            ).strip()

        return Template(template).safe_substitute(**entities).strip()

    def _build_production_items_code(self, items: list[Dict[str, Any]]) -> str:
        lines: list[str] = []

        for item in items:
            unit = item.get("unit")
            if not unit:
                continue

            count_raw = item.get("count")
            try:
                count = int(count_raw)
            except (TypeError, ValueError):
                count = 1
            if count < 1:
                count = 1

            lines.append(f"if not api.ensure_can_produce_unit({unit!r}):")
            lines.append(f"    raise RuntimeError('不能生产{unit}：前置不足或失败')")
            lines.append(f"api.produce_wait({unit!r}, {count}, auto_place_building=True)")
            lines.append(f"logger.info('生产了{count}个{unit}')")
            lines.append(f"_step_messages.append('已生产{count}个{unit}')")

        return "\n".join(lines).strip()

    def _render_single_wrapper(self, step_code: str, intent: Optional[str]) -> Optional[str]:
        wrapper = self._wrapper_template_map.get("single_action")
        if not wrapper:
            return None

        return Template(wrapper).safe_substitute(
            intent=intent or "",
            step_code=self._indent_code(step_code, spaces=4),
        ).strip()

    def _render_sequence_wrapper(
        self,
        step_codes: list[str],
        step_intents: list[str],
        clauses: list[str],
    ) -> Optional[str]:
        wrapper = self._wrapper_template_map.get("sequence_action")
        if not wrapper:
            return None

        blocks: list[str] = []
        for idx, (step_code, step_intent, clause) in enumerate(
            zip(step_codes, step_intents, clauses), start=1
        ):
            block = "\n".join(
                [
                    f"_current_step = {idx}",
                    f"_current_intent = {step_intent!r}",
                    f"_current_clause = {clause!r}",
                    step_code,
                ]
            )
            blocks.append(self._indent_code(block, spaces=4))

        return Template(wrapper).safe_substitute(step_blocks="\n\n".join(blocks)).strip()

    @staticmethod
    def _indent_code(code: str, *, spaces: int) -> str:
        prefix = " " * spaces
        return "\n".join(prefix + line if line else line for line in code.splitlines())

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
