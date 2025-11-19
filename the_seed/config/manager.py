from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, Dict

from .schema import SeedConfig

CONFIG_DIR = Path(__file__).resolve().parent
CONFIG_PATH = CONFIG_DIR / "seed_config.jsonc"


def load_config(path: str | Path | None = None) -> SeedConfig:
    """加载配置：若 JSONC 缺失则沿用 Python 默认值。"""
    cfg = SeedConfig()
    target_path = Path(path) if path else CONFIG_PATH
    overrides = _read_config_file(target_path)
    if overrides:
        _apply_dict_to_dataclass(cfg, overrides)
    return cfg


# —— 内部工具 —— #
def _read_config_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    raw_text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(_strip_json_comments(raw_text)) or {}
    except json.JSONDecodeError:
        data = {}
    return data


def _strip_json_comments(text: str) -> str:
    """移除 // 与 /* ... */ 注释，保持字符串内容不变。"""
    result = []
    in_string = False
    escape = False
    i = 0
    length = len(text)

    while i < length:
        char = text[i]
        if in_string:
            result.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            i += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            i += 1
            continue

        if char == "/" and i + 1 < length:
            nxt = text[i + 1]
            if nxt == "/":
                i += 2
                while i < length and text[i] not in ("\n", "\r"):
                    i += 1
                continue
            if nxt == "*":
                i += 2
                while i + 1 < length and not (text[i] == "*" and text[i + 1] == "/"):
                    i += 1
                i += 2
                continue

        result.append(char)
        i += 1

    return "".join(result)


def _apply_dict_to_dataclass(instance: Any, data: Dict[str, Any]) -> None:
    for f in fields(instance):
        if f.name not in data:
            continue
        value = data[f.name]
        current = getattr(instance, f.name)
        if is_dataclass(current):
            if isinstance(value, dict):
                _apply_dict_to_dataclass(current, value)
        else:
            setattr(instance, f.name, value)

