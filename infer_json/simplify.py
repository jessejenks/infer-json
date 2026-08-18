from __future__ import annotations

from functools import reduce

from .config import Config
from .type_exprs import (
    ListType,
    MapType,
    RecordType,
    StringType,
    TypeExpr,
    UnionType,
    flatten_union_members,
    merge,
    merge_records,
    merge_union_members,
)


def record_overlapping_key_count(a: RecordType, b: RecordType) -> int:
    return len(a.fields.keys() & b.fields.keys())


def _collapse_lists(members: list[TypeExpr]) -> list[TypeExpr]:
    lists: list[ListType] = []
    rest: list[TypeExpr] = []
    for m in members:
        if m.kind == "list":
            lists.append(m)
        else:
            rest.append(m)
    if len(lists) < 2:
        return members
    combined = ListType(reduce(merge, [l.element_type for l in lists]))
    return rest + [combined]


def _collapse_maps(members: list[TypeExpr]) -> list[TypeExpr]:
    maps: list[MapType] = []
    rest: list[TypeExpr] = []
    for m in members:
        if m.kind == "map":
            maps.append(m)
        else:
            rest.append(m)
    if len(maps) < 2:
        return members
    combined = MapType(reduce(merge, [m.value_type for m in maps]))
    return rest + [combined]


def simplify_unions(t: TypeExpr, min_shared_keys: int) -> TypeExpr:
    match t.kind:
        case "record":
            return RecordType({k: (simplify_unions(v, min_shared_keys), r) for k, (v, r) in t.fields.items()})
        case "list":
            return ListType(simplify_unions(t.element_type, min_shared_keys))
        case "map":
            return MapType(simplify_unions(t.value_type, min_shared_keys))
        case "union":
            simplified = [simplify_unions(m, min_shared_keys) for m in t.members]
            simplified = merge_union_members(simplified)
            simplified = _collapse_lists(simplified)
            simplified = _collapse_maps(simplified)
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


def merge_similar_records(members: list[TypeExpr], threshold: int) -> list[TypeExpr]:
    candidates: list[tuple[int, RecordType]] = []
    for i, m in enumerate(members):
        rec = unwrap_to_record(m)
        if rec is not None:
            candidates.append((i, rec))

    if len(candidates) < 2:
        return members

    merged_into: dict[int, int] = {}
    merged_records: dict[int, RecordType] = {i: rec for i, rec in candidates}

    changed = True
    while changed:
        changed = False
        idxs = [i for i, _ in candidates if i not in merged_into]
        for a_pos in range(len(idxs)):
            i = idxs[a_pos]
            for b_pos in range(a_pos + 1, len(idxs)):
                j = idxs[b_pos]
                if record_overlapping_key_count(merged_records[i], merged_records[j]) >= threshold:
                    merged_records[i] = merge_records(merged_records[i].fields, merged_records[j].fields)
                    merged_into[j] = i
                    changed = True

    candidate_idxs = {i for i, _ in candidates}
    result: list[TypeExpr] = []
    for i, m in enumerate(members):
        if i in merged_into:
            continue
        if i in candidate_idxs:
            result.append(rewrap_record(m, merged_records[i]))
        else:
            result.append(m)
    return result


def _collect_literal_values(t: TypeExpr, out: set[str]) -> None:
    match t.kind:
        case "string_literal":
            out.add(t.value)
        case "union":
            for m in t.members:
                _collect_literal_values(m, out)


def count_literals(t: TypeExpr) -> int:
    values: set[str] = set()
    _collect_literal_values(t, values)
    return len(values)


def widen_literals(t: TypeExpr, discriminant_key: str | None, config: Config) -> TypeExpr:
    match t.kind:
        case "string_literal":
            if config.max_literals == 0:
                return StringType
            if config.max_literal_length > 0 and len(t.value) > config.max_literal_length:
                return StringType
            return t
        case "record":
            new_fields: dict[str, tuple[TypeExpr, bool]] = {}
            for k, (v, r) in t.fields.items():
                if k == discriminant_key:
                    new_fields[k] = v, r
                else:
                    new_fields[k] = (widen_literals(v, None, config), r)
            return RecordType(new_fields)
        case "list":
            return ListType(widen_literals(t.element_type, None, config))
        case "map":
            return MapType(widen_literals(t.value_type, None, config))
        case "union":
            flat = merge_union_members(flatten_union_members(t.members))
            n = count_literals(t)
            if n > config.max_literals:
                widened = []
                for m in flat:
                    if m.kind == "string_literal":
                        widened.append(StringType)
                    else:
                        widened.append(widen_literals(m, None, config))
                result = merge_union_members(widened)
            else:
                result = merge_union_members([widen_literals(m, None, config) for m in flat])
            if len(result) == 1:
                return result[0]
            return UnionType(result)
        case _:
            return t
