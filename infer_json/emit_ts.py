from __future__ import annotations

import json
import re

from .config import Config
from .emit import get_indent
from .type_exprs import Null, RecordType, TypeExpr


def type_to_ts(t: TypeExpr, config: Config, depth: int = 0) -> str:
    match t.kind:
        case "unknown":
            return "unknown"
        case "atom":
            if t.name in ("int", "float"):
                return "number"
            return t.name
        case "string_literal":
            return json.dumps(t.value)
        case "ref":
            return t.name
        case "map":
            return f"Record<string, {type_to_ts(t.value_type, config, depth)}>"
        case "list":
            inner = type_to_ts(t.element_type, config, depth)
            if t.element_type.kind == "union":
                return f"({inner})[]"
            return f"{inner}[]"
        case "union":
            parts = []
            nullable = False
            for m in t.members:
                if m is Null:
                    nullable = True
                    continue
                parts.append(type_to_ts(m, config, depth))
            if nullable:
                parts.append("null")
            return " | ".join(parts)
        case "record":
            return record_to_ts(t, config, depth)
    raise ValueError(f"Unhandled type kind: {t.kind}")


# JS is actually very permissive but we are conservative for quoting
_TS_IDENTIFIER_NO_QUOTES = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def record_to_ts(t: RecordType, config: Config, depth: int = 0) -> str:
    if not t.fields:
        return "{}"
    pad = get_indent(depth + 1, config)
    closing_pad = get_indent(depth, config)
    readonly = "readonly " if config.readonly else ""
    fields = sorted(t.fields.items()) if config.sort_keys else list(t.fields.items())
    lines = []
    for key, (field_type, required) in fields:
        s = type_to_ts(field_type, config, depth + 1)
        opt = "" if required else "?"
        if not _TS_IDENTIFIER_NO_QUOTES.match(key):
            key = json.dumps(key)
        lines.append(f"{pad}{readonly}{key}{opt}: {s};")
    return "{\n" + "\n".join(lines) + f"\n{closing_pad}}}"
