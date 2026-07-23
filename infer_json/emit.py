from __future__ import annotations

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
