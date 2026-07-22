from __future__ import annotations

import json
from typing import Dict, List

from .type_exprs import (
    ListType,
    MapType,
    NamedRef,
    NullableType,
    RecordType,
    TypeExpr,
    UnionType,
)


def snake_to_pascal(s: str) -> str:
    return "".join(w[0].upper() + w[1:] for w in s.replace("-", "_").split("_") if w)


def extract_named_types(
    t: TypeExpr,
    path: List[str],
    extracted: Dict[str, TypeExpr],
) -> TypeExpr:
    match t.kind:
        case "record":
            new_fields: Dict[str, TypeExpr] = {}
            for k, v in t.fields.items():
                new_fields[k] = extract_named_types(v, [*path, k], extracted)
            name = "".join(snake_to_pascal(p) for p in path)
            if name in extracted:
                suffix = 2
                while f"{name}{suffix}" in extracted:
                    suffix += 1
                name = f"{name}{suffix}"
            extracted[name] = RecordType(new_fields)
            return NamedRef(name)
        case "nullable":
            return NullableType(extract_named_types(t.element_type, path, extracted))
        case "list":
            return ListType(extract_named_types(t.element_type, path, extracted))
        case "union":
            return UnionType([extract_named_types(m, path, extracted) for m in t.members])
        case "map":
            return MapType(extract_named_types(t.value_type, path, extracted))
        case _:
            return t


def type_to_ts(t: TypeExpr, indent: int = 0) -> str:
    match t.kind:
        case "unknown":
            return "unknown"
        case "null":
            return "null"
        case "atom":
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
