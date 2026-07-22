from __future__ import annotations

from typing import Dict, List, Tuple

from .config import Config
from .merge import merge_records
from .type_exprs import (
    ListType,
    MapType,
    NullableType,
    RecordType,
    StringType,
    TypeExpr,
    UnionType,
    flatten_union_members,
)


def type_eq(a: TypeExpr, b: TypeExpr) -> bool:
    if a.kind != b.kind:
        return False
    match a.kind:
        case "unknown" | "null":
            return True
        case "atom":
            return a.name == b.name  # type: ignore
        case "string_literal":
            return a.value == b.value  # type: ignore
        case "ref":
            return a.name == b.name  # type: ignore
        case "list":
            return type_eq(a.element_type, b.element_type)  # type: ignore
        case "nullable":
            return type_eq(a.element_type, b.element_type)  # type: ignore
        case "record":
            if a.fields.keys() != b.fields.keys():  # type: ignore
                return False
            return all(type_eq(a.fields[k], b.fields[k]) for k in a.fields)  # type: ignore
        case "map":
            return type_eq(a.value_type, b.value_type)  # type: ignore
        case "union":
            if len(a.members) != len(b.members):  # type: ignore
                return False
            return all(type_eq(x, y) for x, y in zip(a.members, b.members))  # type: ignore
    return False


def dedup_union_members(members: List[TypeExpr]) -> List[TypeExpr]:
    flat = flatten_union_members(members)
    result: List[TypeExpr] = []
    for m in flat:
        if not any(type_eq(m, existing) for existing in result):
            result.append(m)
    return result


def record_overlap(a: RecordType, b: RecordType) -> int:
    return len(set(a.fields.keys()) & set(b.fields.keys()))


def simplify_unions(t: TypeExpr, min_shared_keys: int) -> TypeExpr:
    match t.kind:
        case "record":
            return RecordType({k: simplify_unions(v, min_shared_keys) for k, v in t.fields.items()})
        case "nullable":
            return NullableType(simplify_unions(t.element_type, min_shared_keys))
        case "list":
            return ListType(simplify_unions(t.element_type, min_shared_keys))
        case "map":
            return MapType(simplify_unions(t.value_type, min_shared_keys))
        case "union":
            simplified = [simplify_unions(m, min_shared_keys) for m in t.members]
            simplified = dedup_union_members(simplified)
            if min_shared_keys > 0:
                simplified = merge_similar_records(simplified, min_shared_keys)
            if len(simplified) == 1:
                return simplified[0]
            return UnionType(simplified)
        case _:
            return t


def unwrap_to_record(t: TypeExpr) -> RecordType | None:
    if t.kind == "record":
        return t
    if t.kind == "list" and t.element_type.kind == "record":
        return t.element_type
    if t.kind == "map" and t.value_type.kind == "record":
        return t.value_type
    return None


def rewrap_record(original: TypeExpr, merged: RecordType) -> TypeExpr:
    if original.kind == "list":
        return ListType(merged)
    if original.kind == "map":
        return MapType(merged)
    return merged


def merge_similar_records(members: List[TypeExpr], threshold: int) -> List[TypeExpr]:
    candidates: List[Tuple[int, RecordType]] = []
    for i, m in enumerate(members):
        rec = unwrap_to_record(m)
        if rec is not None:
            candidates.append((i, rec))

    if len(candidates) < 2:
        return members

    merged_into: Dict[int, int] = {}
    merged_records: Dict[int, RecordType] = {i: rec for i, rec in candidates}

    changed = True
    while changed:
        changed = False
        idxs = [i for i, _ in candidates if i not in merged_into]
        for a_pos in range(len(idxs)):
            i = idxs[a_pos]
            for b_pos in range(a_pos + 1, len(idxs)):
                j = idxs[b_pos]
                if record_overlap(merged_records[i], merged_records[j]) >= threshold:
                    merged_records[i] = merge_records(merged_records[i], merged_records[j])
                    merged_into[j] = i
                    changed = True

    candidate_idxs = {i for i, _ in candidates}
    result: List[TypeExpr] = []
    for i, m in enumerate(members):
        if i in merged_into:
            continue
        if i in candidate_idxs:
            result.append(rewrap_record(m, merged_records[i]))
        else:
            result.append(m)
    return result


def count_literals(t: TypeExpr) -> int:
    match t.kind:
        case "string_literal":
            return 1
        case "union":
            return sum(count_literals(m) for m in flatten_union_members(t.members))
        case _:
            return 0


def widen_literals(t: TypeExpr, discriminant_key: str | None, config: Config) -> TypeExpr:
    match t.kind:
        case "string_literal":
            if config.max_literals == 0:
                return StringType
            if config.max_literal_length > 0 and len(t.value) > config.max_literal_length:
                return StringType
            return t
        case "record":
            new_fields = {}
            for k, v in t.fields.items():
                if k == discriminant_key:
                    new_fields[k] = v
                else:
                    new_fields[k] = widen_literals(v, None, config)
            return RecordType(new_fields)
        case "nullable":
            return NullableType(widen_literals(t.element_type, None, config))
        case "list":
            return ListType(widen_literals(t.element_type, None, config))
        case "map":
            return MapType(widen_literals(t.value_type, None, config))
        case "union":
            flat = flatten_union_members(t.members)
            n = count_literals(t)
            if n > config.max_literals:
                widened = []
                for m in flat:
                    if m.kind == "string_literal":
                        widened.append(StringType)
                    else:
                        widened.append(widen_literals(m, None, config))
                return UnionType(widened)
            return UnionType([widen_literals(m, None, config) for m in flat])
        case _:
            return t
