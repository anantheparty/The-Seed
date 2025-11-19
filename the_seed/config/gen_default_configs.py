from __future__ import annotations

import argparse
import json
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, Dict

from .manager import CONFIG_PATH
from .schema import SeedConfig


def main() -> None:
    parser = argparse.ArgumentParser(
        description="根据 SeedConfig 数据类生成注释模板（JSONC）。"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=CONFIG_PATH,
        help=f"输出文件路径（默认: {CONFIG_PATH})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="目标文件存在时仍然覆盖。",
    )
    args = parser.parse_args()
    output: Path = args.output.expanduser().resolve()

    if output.exists() and not args.force:
        raise SystemExit(
            f"目标文件 {output} 已存在。使用 --force 覆盖，或指定 --output 另存。"
        )

    template = render_template()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(template + "\n", encoding="utf-8")
    print(f"已生成模板：{output}")


def render_template() -> str:
    data = _dataclass_to_plain_dict(SeedConfig())
    lines = ["{"] + _render_block(data, indent=2, path="") + ["}"]
    return "\n".join(lines)


def _render_block(mapping: Dict[str, Any], *, indent: int, path: str) -> list[str]:
    items = list(mapping.items())
    lines: list[str] = []
    indent_str = " " * indent
    for idx, (key, value) in enumerate(items):
        if idx > 0:
            lines.append("")
        full_path = f"{path}.{key}" if path else key
        comma = "," if idx < len(items) - 1 else ""
        if isinstance(value, dict):
            lines.append(f"{indent_str}// {full_path}")
            lines.append(f"{indent_str}\"{key}\": {{")
            lines.extend(_render_block(value, indent=indent + 2, path=full_path))
            lines.append(f"{indent_str}}}{comma}")
        else:
            default_json = json.dumps(value, ensure_ascii=False)
            lines.append(f"{indent_str}// {full_path} 默认值: {default_json}")
            lines.append(f"{indent_str}// \"{key}\": {default_json}{comma}")
    if not items:
        lines.append(f"{indent_str}// （暂无字段）")
    return lines


def _dataclass_to_plain_dict(obj: Any) -> Dict[str, Any]:
    if is_dataclass(obj):
        result: Dict[str, Any] = {}
        for f in fields(obj):
            result[f.name] = _dataclass_to_plain_dict(getattr(obj, f.name))
        return result
    if isinstance(obj, dict):
        return {k: _dataclass_to_plain_dict(v) for k, v in obj.items()}
    return obj


if __name__ == "__main__":
    main()

