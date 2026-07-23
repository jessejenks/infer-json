from __future__ import annotations

from typing import List

from .emit import snake_to_pascal
from .type_exprs import RecordType, TypeExpr


def type_to_go(t: TypeExpr) -> str:
    match t.kind:
        case "unknown" | "null" | "union":
            return "any"
        case "atom":
            if t.name == "boolean":
                return "bool"
            if t.name == "float":
                return "float64"
            return t.name
        case "string_literal":
            return "string"
        case "ref":
            return t.name
        case "map":
            return f"map[string]{type_to_go(t.value_type)}"
        case "list":
            return f"[]{type_to_go(t.element_type)}"
        case "nullable":
            inner = type_to_go(t.element_type)
            if t.element_type.kind in ("map", "list"):
                return inner
            return f"*{inner}"
        case "record":
            return struct_to_go(t)
    raise ValueError(f"Unhandled type kind: {t.kind}")


def struct_to_go(t: RecordType, indent: int = 0) -> str:
    if not t.fields:
        return "struct{}"
    pad = "\t" * (indent + 1)
    closing_pad = "\t" * indent
    lines: List[str] = []
    for key, field_type in t.fields.items():
        field_name = snake_to_pascal(key)
        tag = f'`json:"{key}"`'
        if field_type.kind == "nullable":
            go_type = type_to_go(field_type.element_type)
            if field_type.element_type.kind not in ("map", "list"):
                go_type = f"*{go_type}"
            tag = f'`json:"{key},omitempty"`'
        else:
            go_type = type_to_go(field_type)
        lines.append(f"{pad}{field_name} {go_type} {tag}")
    return "struct {\n" + "\n".join(lines) + f"\n{closing_pad}}}"
