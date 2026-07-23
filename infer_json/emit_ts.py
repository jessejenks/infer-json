from __future__ import annotations

import json

from .type_exprs import RecordType, TypeExpr


def type_to_ts(t: TypeExpr, indent: int = 0) -> str:
    match t.kind:
        case "unknown":
            return "unknown"
        case "null":
            return "null"
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
            if t.element_type.kind in ("union", "nullable"):
                return f"({inner})[]"
            return f"{inner}[]"
        case "nullable":
            inner = type_to_ts(t.element_type, indent)
            return f"{inner} | null"
        case "union":
            parts = [type_to_ts(m, indent) for m in t.members]
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
    for key, field_type in t.fields.items():
        optional = field_type.kind == "nullable"
        if optional:
            inner_type = type_to_ts(field_type.element_type, indent + 1)
            lines.append(f"{pad}{key}?: {inner_type};")
        else:
            lines.append(f"{pad}{key}: {type_to_ts(field_type, indent + 1)};")
    return "{\n" + "\n".join(lines) + f"\n{closing_pad}}}"
