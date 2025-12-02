from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, Dict

import json5

from .schema import SeedConfig

CONFIG_DIR = Path(__file__).resolve().parent
CONFIG_PATH = CONFIG_DIR / "seed_config.jsonc"


def load_config(path: str | Path | None = None) -> SeedConfig:
    """加载配置：若 JSONC 缺失则沿用 Python 默认值。"""
    cfg = SeedConfig()
    # target_path = Path(path) if path else CONFIG_PATH
    # overrides = _read_config_file(target_path)
    # if overrides:
    #     _apply_dict_to_dataclass(cfg, overrides)
    return cfg


# —— 内部工具 —— #
def _read_config_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    raw_text = path.read_text(encoding="utf-8")
    try:
        data = json5.loads(raw_text) or {}
    except json5.JSON5DecodeError:
        data = {}
    return data


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

