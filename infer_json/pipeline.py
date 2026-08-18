import sys
from functools import reduce

from .config import Config
from .infer import infer_type
from .simplify import simplify_unions, widen_literals
from .type_exprs import (
    MapType,
    RecordType,
    TypeExpr,
    UnionType,
    merge,
    merge_records,
)


def run_pipeline(items: list[object], config: Config) -> list[tuple[str | None, TypeExpr]]:
    inferred = [infer_type(item, config) for item in items]
    records, other_types = _partition_records(inferred)
    record_groups = _group_by_keyset(records)

    discriminant: str | None = None
    if config.find_discriminant and len(record_groups) > 1:
        discriminant = _find_discriminant(record_groups)
        if discriminant:
            print(f'// Discriminant key: "{discriminant}"', file=sys.stderr)
        else:
            print("// No single discriminant key found", file=sys.stderr)
    record_variants = _name_record_variants(record_groups, discriminant)
    other_variants: list[tuple[str | None, TypeExpr]] = [(None, t) for t in other_types]

    if config.flatten_maps:
        variants = _flatten_into_map(record_variants, other_variants)
    else:
        variants = record_variants + other_variants

    variants = _widen_and_simplify(variants, discriminant, config)
    return _assign_names(variants)


def _partition_records(types: list[TypeExpr]) -> tuple[list[RecordType], list[TypeExpr]]:
    records: list[RecordType] = []
    other: list[TypeExpr] = []
    for t in types:
        if t.kind == "record":
            records.append(t)
        else:
            other.append(t)
    return records, other


def _group_by_keyset(records: list[RecordType]) -> list[RecordType]:
    groups: dict[frozenset[str], RecordType] = {}
    for record in records:
        ks = frozenset(record.fields.keys())
        if ks in groups:
            groups[ks] = merge_records(groups[ks].fields, record.fields)
        else:
            groups[ks] = record
    return list(groups.values())


def _name_record_variants(groups: list[RecordType], discriminant: str | None) -> list[tuple[str | None, TypeExpr]]:
    if discriminant:
        groups = _regroup_by_discriminant(groups, discriminant)

    print(f"// {len(groups)} variant(s)\n", file=sys.stderr)

    named: list[tuple[str | None, TypeExpr]] = []
    for group in groups:
        disc_field = group.fields.get(discriminant) if discriminant else None
        if disc_field is not None and disc_field[0].kind == "string_literal":
            named.append((disc_field[0].value, group))
        else:
            named.append((None, group))
    return named


def _flatten_into_map(
    record_variants: list[tuple[str | None, TypeExpr]],
    other_variants: list[tuple[str | None, TypeExpr]],
) -> list[tuple[str | None, TypeExpr]]:
    map_values: list[TypeExpr] = []
    non_map: list[tuple[str | None, TypeExpr]] = []

    for name, t in other_variants:
        if t.kind == "map":
            map_values.append(t.value_type)
        else:
            non_map.append((name, t))

    if not map_values:
        return record_variants + other_variants

    for _, t in record_variants:
        if t.kind == "record":
            map_values.extend(v[0] for v in t.fields.values())

    flat_value = reduce(merge, map_values)
    return [(None, MapType(flat_value))] + non_map


def _widen_and_simplify(
    variants: list[tuple[str | None, TypeExpr]], discriminant: str | None, config: Config
) -> list[tuple[str | None, TypeExpr]]:
    widened = [(name, widen_literals(t, discriminant, config)) for name, t in variants]

    if not discriminant and len(widened) > 1:
        types = [t for _, t in widened]
        combined = simplify_unions(UnionType(types), config.min_shared_keys)
        members = combined.members if combined.kind == "union" else [combined]
        return [(None, t) for t in members]

    return [(name, simplify_unions(t, config.min_shared_keys)) for name, t in widened]


def _assign_names(variants: list[tuple[str | None, TypeExpr]]) -> list[tuple[str | None, TypeExpr]]:
    if len(variants) == 1:
        name = variants[0][0] or "Root"
        return [(name, variants[0][1])]

    return variants


def _find_discriminant(groups: list[RecordType]) -> str | None:
    all_keys: set[str] = set()
    for group in groups:
        for k, (v, _) in group.fields.items():
            if v.kind == "string_literal":
                all_keys.add(k)

    best_key: str | None = None
    best_distinct = 0

    for key in all_keys:
        values: list[str] = []
        for group in groups:
            field = group.fields.get(key)
            if field is not None and field[0].kind == "string_literal":
                values.append(field[0].value)

        if len(values) < 2:
            continue

        distinct = len(set(values))
        if distinct > best_distinct:
            best_distinct = distinct
            best_key = key

    return best_key


def _regroup_by_discriminant(groups: list[RecordType], discriminant: str) -> list[RecordType]:
    by_value: dict[str, RecordType] = {}
    untagged: list[RecordType] = []

    for group in groups:
        field = group.fields.get(discriminant)
        if field is None or field[0].kind != "string_literal":
            untagged.append(group)
            continue
        val = field[0].value
        if val in by_value:
            by_value[val] = merge_records(by_value[val].fields, group.fields)
        else:
            by_value[val] = group

    return list(by_value.values()) + untagged
