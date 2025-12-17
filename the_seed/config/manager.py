from __future__ import annotations

from .schema import SeedConfig


def load_config() -> SeedConfig:
    """返回直接在 schema.py 中声明的配置默认值。"""
    return SeedConfig()

