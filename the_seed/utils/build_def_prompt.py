import inspect
import textwrap
from typing import Any, get_type_hints

def _safe_get_type_hints(func):
    try:
        return get_type_hints(func, include_extras=True)
    except Exception:
        return {}

def _ann_to_str(ann):
    if ann is inspect._empty:
        return None
    # typing 对象的字符串会比较长，但可用；你也可以在这里做更漂亮的缩写
    try:
        s = getattr(ann, "__name__", None) or str(ann)
    except Exception:
        s = str(ann)
    return s.replace("typing.", "")

def _unwrap_descriptor(owner, name):
    """
    用 getattr_static 避免 descriptor 绑定；同时识别 staticmethod/classmethod
    返回: (callable, kind) kind in {"function","staticmethod","classmethod","callable"}
    """
    raw = inspect.getattr_static(owner, name)
    if isinstance(raw, staticmethod):
        return raw.__func__, "staticmethod"
    if isinstance(raw, classmethod):
        return raw.__func__, "classmethod"
    if inspect.isfunction(raw):
        return raw, "function"
    if callable(raw):
        return raw, "callable"
    raise TypeError(f"{name} is not callable")

def build_def_style_prompt(
    cls_or_obj: Any,
    fn_names: list[str],
    *,
    title: str | None = None,
    omit_first_param_for_methods: bool = True,   # 通常把 self/cls 省掉，更像“工具函数”
    include_doc_first_line: bool = True,
    include_doc_block: bool = False,             # True 会把完整 docstring 放进去（会很长）
) -> str:
    owner = cls_or_obj if isinstance(cls_or_obj, type) else cls_or_obj.__class__
    header = title or f"Available functions on {owner.__name__}:"
    lines = [header]

    for name in fn_names:
        func, kind = _unwrap_descriptor(owner, name)

        # 签名
        try:
            sig = inspect.signature(func)
        except (TypeError, ValueError):
            lines.append(f"- {name}: <signature unavailable>")
            continue

        hints = _safe_get_type_hints(func)
        params_out = []
        inserted_kw_star = False

        params = list(sig.parameters.values())
        if omit_first_param_for_methods and kind in {"function", "classmethod"} and params:
            # function/classmethod 这两类一般首参是 self/cls（staticmethod 没有）
            params = params[1:]

        for p in params:
            chunk = ""

            if p.kind == inspect.Parameter.VAR_POSITIONAL:
                chunk += f"*{p.name}"
            elif p.kind == inspect.Parameter.VAR_KEYWORD:
                chunk += f"**{p.name}"
            else:
                if p.kind == inspect.Parameter.KEYWORD_ONLY and not inserted_kw_star:
                    # 如果没有 *args，但出现 keyword-only，需要显式插入 "*"
                    has_var_positional = any(x.kind == inspect.Parameter.VAR_POSITIONAL for x in params)
                    if not has_var_positional:
                        params_out.append("*")
                    inserted_kw_star = True

                chunk += p.name

            ann = hints.get(p.name, p.annotation)
            ann_s = _ann_to_str(ann)
            if ann_s:
                chunk += f": {ann_s}"

            if p.default is not inspect._empty and p.kind not in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                try:
                    d = repr(p.default)
                except Exception:
                    d = "<default>"
                chunk += f" = {d}"

            params_out.append(chunk)

        ret_ann = hints.get("return", sig.return_annotation)
        ret_s = _ann_to_str(ret_ann)

        prefix = "@staticmethod\n" if kind == "staticmethod" else "@classmethod\n" if kind == "classmethod" else ""
        def_line = f"{prefix}def {name}({', '.join(params_out)})"
        if ret_s:
            def_line += f" -> {ret_s}"
        def_line += ":"

        # docstring
        ds = inspect.getdoc(func) or ""
        if include_doc_first_line and ds.strip():
            first = ds.strip().splitlines()[0].strip()
            lines.append(f"- {def_line}  # {first}")
        else:
            lines.append(f"- {def_line}")

        if include_doc_block and ds.strip():
            block = textwrap.indent(ds, "    ")
            lines.append(block)

    return "\n".join(lines)


# ===== Test =====
if __name__ == "__main__":
    class Toolset:
        def move(self, x: float, y: float, *, speed: float = 1.0) -> None:
            """Move to (x,y) with optional speed.
            Args:
                x: The x coordinate to move to.
                y: The y coordinate to move to.
                speed: The speed to move at.
            Returns:
                None
            """
            ...

        @staticmethod
        def ping(host: str, timeout: float = 1.0) -> bool:
            """Return True if host is reachable.
            Args:
                host: The host to ping.
                timeout: The timeout in seconds.
            Returns:
                True if host is reachable, False otherwise.
            """
            ...

        @classmethod
        def version(cls) -> str:
            """Return toolset version string.
            Args:
                cls: The class to return the version string for.
            Returns:
                The version string.
            """
            return "1.0"

    prompt = build_def_style_prompt(
        Toolset,
        ["move", "ping", "version"],
        omit_first_param_for_methods=False,
        include_doc_first_line=True,
        include_doc_block=False,
    )
    print(prompt)