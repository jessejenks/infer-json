from __future__ import annotations

from typing import Dict, List

from .type_exprs import (
    ListType,
    MapType,
    NullableType,
    RecordType,
    StringType,
    TypeExpr,
    UnionType,
    Unknown,
    flatten_union_members,
)


def _make_union(members: List[TypeExpr]) -> TypeExpr:
    flat = flatten_union_members(members)
    if len(flat) == 1:
        return flat[0]
    return UnionType(flat)


def merge(a: TypeExpr, b: TypeExpr) -> TypeExpr:
    if a.kind == "unknown":
        return b if b.kind != "unknown" else Unknown
    if b.kind == "unknown":
        return a

    if a.kind == "null":
        if b.kind in ("null", "nullable"):
            return b
        return NullableType(b)
    if b.kind == "null":
        if a.kind == "nullable":
            return a
        return NullableType(a)

    if a.kind == "nullable":
        return NullableType(merge(a.element_type, b if b.kind != "nullable" else b.element_type))
    if b.kind == "nullable":
        return NullableType(merge(a, b.element_type))

    if a.kind == "string_literal" and b.kind == "string_literal":
        if a.value == b.value:
            return a
        return UnionType([a, b])

    if a.kind == "string_literal" and b.kind == "atom" and b.name == "string":
        return StringType
    if b.kind == "string_literal" and a.kind == "atom" and a.name == "string":
        return StringType

    if a.kind == "atom" and b.kind == "atom":
        if a.name == b.name:
            return a
        return UnionType([a, b])

    if a.kind == "list" and b.kind == "list":
        return ListType(merge(a.element_type, b.element_type))

    if a.kind == "record" and b.kind == "record":
        return merge_records(a, b)

    if a.kind == "map" and b.kind == "map":
        return MapType(merge(a.value_type, b.value_type))

    return _make_union([a, b])


def merge_records(a: RecordType, b: RecordType) -> RecordType:
    new_fields: Dict[str, TypeExpr] = {}
    for k, t in a.fields.items():
        if k not in b.fields:
            new_fields[k] = make_nullable(t)
        else:
            new_fields[k] = merge(t, b.fields[k])
    for k, t in b.fields.items():
        if k not in a.fields:
            new_fields[k] = make_nullable(t)
    return RecordType(new_fields)


def make_nullable(t: TypeExpr) -> TypeExpr:
    if t.kind in ("null", "nullable"):
        return t
    return NullableType(t)
