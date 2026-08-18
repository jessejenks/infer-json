from __future__ import annotations

import json

from .config import Config
from .type_exprs import Null, RecordType, TypeExpr


def type_to_ts(t: TypeExpr, config: Config, indent: int = 0) -> str:
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
            return f"Record<string, {type_to_ts(t.value_type, config, indent)}>"
        case "list":
            inner = type_to_ts(t.element_type, config, indent)
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
                parts.append(type_to_ts(m, config, indent))
            if nullable:
                parts.append("null")
            return " | ".join(parts)
        case "record":
            return record_to_ts(t, config, indent)
    raise ValueError(f"Unhandled type kind: {t.kind}")


def record_to_ts(t: RecordType, config: Config, indent: int = 0) -> str:
    if not t.fields:
        return "{}"
    unit = " " * config.tab_width if config.use_spaces else "\t"
    pad = unit * (indent + 1)
    closing_pad = unit * indent
    readonly = "readonly " if config.readonly else ""
    fields = sorted(t.fields.items()) if config.sort_keys else list(t.fields.items())
    lines = []
    for key, (field_type, required) in fields:
        s = type_to_ts(field_type, config, indent + 1)
        opt = "" if required else "?"
        lines.append(f"{pad}{readonly}{key}{opt}: {s};")
    return "{\n" + "\n".join(lines) + f"\n{closing_pad}}}"
