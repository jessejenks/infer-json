from __future__ import annotations

import json

from .type_exprs import Null, RecordType, TypeExpr


def type_to_ts(t: TypeExpr, indent: int = 0) -> str:
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
            return f"Record<string, {type_to_ts(t.value_type, indent)}>"
        case "list":
            inner = type_to_ts(t.element_type, indent)
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
                parts.append(type_to_ts(m, indent))
            if nullable:
                parts.append("null")
            return " | ".join(parts)
        case "record":
            return record_to_ts(t, indent)
    raise ValueError(f"Unhandled type kind: {t.kind}")


def record_to_ts(t: RecordType, indent: int = 0) -> str:
    if not t.fields:
        return "{}"
    pad = "  " * (indent + 1)
    closing_pad = "  " * indent
    lines = []
    for key, (field_type, required) in t.fields.items():
        s = type_to_ts(field_type, indent + 1)
        opt = "" if required else "?"
        lines.append(f"{pad}{key}{opt}: {s};")
    return "{\n" + "\n".join(lines) + f"\n{closing_pad}}}"
