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
    record_groups = _group_by_keyset(records, config)

    discriminant: str | None = None
    if config.find_discriminant:
        if len(record_groups) > 1:
            discriminant = _find_discriminant(record_groups)
            if discriminant:
                print(f'// Discriminant key: "{discriminant}"', file=sys.stderr)
            else:
                print("// No single discriminant key found", file=sys.stderr)
        elif len(records) > 1:
            nested = _find_nested_discriminant(records)
            if nested:
                disc_key, nested_field = nested
                print(f'// Nested discriminant: "{disc_key}" on field "{nested_field}"', file=sys.stderr)
                discriminant = disc_key
                record_groups = _group_by_nested_discriminant(records, disc_key, config)

    record_variants = _name_record_variants(record_groups, discriminant)
    other_variants: list[tuple[str | None, TypeExpr]] = [(None, t) for t in other_types]

    if config.flatten_maps:
        variants = _flatten_into_map(record_variants, other_variants)
    else:
        variants = record_variants + other_variants

    return _widen_and_simplify(variants, discriminant, config)


def _partition_records(types: list[TypeExpr]) -> tuple[list[RecordType], list[TypeExpr]]:
    records: list[RecordType] = []
    other: list[TypeExpr] = []
    for t in types:
        if t.kind == "record":
            records.append(t)
        else:
            other.append(t)
    return records, other


def _group_by_keyset(records: list[RecordType], config: Config) -> list[RecordType]:
    groups: dict[frozenset[str], RecordType] = {}
    for record in records:
        ks = frozenset(record.fields.keys())
        if ks in groups:
            groups[ks] = merge_records(groups[ks].fields, record.fields, config.max_literals)
        else:
            groups[ks] = record
    return list(groups.values())


def _name_record_variants(groups: list[RecordType], discriminant: str | None) -> list[tuple[str | None, TypeExpr]]:
    if discriminant:
        groups = _regroup_by_discriminant(groups, discriminant)

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
    if not discriminant and len(variants) > 1:
        types = [t for _, t in variants]
        combined = widen_literals(UnionType(types), None, config)
        simplified = simplify_unions(combined, config.min_shared_keys)
        members = simplified.members if simplified.kind == "union" else [simplified]
        return [(None, t) for t in members]

    widened = [(name, widen_literals(t, discriminant, config)) for name, t in variants]
    return [(name, simplify_unions(t, config.min_shared_keys)) for name, t in widened]


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


def _find_nested_discriminant(records: list[RecordType]) -> tuple[str, str] | None:
    candidate_keys = _string_literal_keys_in_all(records)
    if not candidate_keys:
        return None

    varying_fields = _nested_fields_with_varying_keysets(records)
    if not varying_fields:
        return None

    best: tuple[str, str] | None = None
    best_distinct = float("inf")

    for disc_key in candidate_keys:
        for nested_field in varying_fields:
            value_to_keysets = _partition_nested_keysets(records, disc_key, nested_field)
            if len(value_to_keysets) < 2:
                continue

            distinct_keysets: set[frozenset[str]] = set()
            for ks_set in value_to_keysets.values():
                distinct_keysets.update(ks_set)
            if len(distinct_keysets) < 2:
                continue

            # Prefer the key with the fewest distinct values
            n = len(value_to_keysets)
            if n < best_distinct:
                best_distinct = n
                best = (disc_key, nested_field)

    return best


def _string_literal_keys_in_all(records: list[RecordType]) -> set[str]:
    candidates: set[str] = set()
    for k, (v, _) in records[0].fields.items():
        if v.kind == "string_literal":
            candidates.add(k)
    for rec in records[1:]:
        candidates = {k for k in candidates if k in rec.fields and rec.fields[k][0].kind == "string_literal"}
    return candidates


def _nested_fields_with_varying_keysets(records: list[RecordType]) -> list[str]:
    varying: list[str] = []
    for k in records[0].fields:
        keysets: list[frozenset[str]] = []
        for rec in records:
            field = rec.fields.get(k)
            if field is not None and field[0].kind == "record":
                keysets.append(frozenset(field[0].fields.keys()))
        if len(keysets) == len(records) and len(set(keysets)) > 1:
            varying.append(k)
    return varying


def _partition_nested_keysets(
    records: list[RecordType], disc_key: str, nested_field: str
) -> dict[str, set[frozenset[str]]]:
    result: dict[str, set[frozenset[str]]] = {}
    for rec in records:
        disc_val = rec.fields[disc_key][0]
        nested_t = rec.fields[nested_field][0]
        if disc_val.kind != "string_literal" or nested_t.kind != "record":
            continue
        nested_ks = frozenset(nested_t.fields.keys())
        result.setdefault(disc_val.value, set()).add(nested_ks)
    return result


def _group_by_nested_discriminant(records: list[RecordType], disc_key: str, config: Config) -> list[RecordType]:
    by_value: dict[str, list[RecordType]] = {}
    for rec in records:
        val = rec.fields[disc_key][0]
        if val.kind != "string_literal":
            continue
        by_value.setdefault(val.value, []).append(rec)

    groups: list[RecordType] = []
    for recs in by_value.values():
        merged = recs[0]
        for rec in recs[1:]:
            merged = merge_records(merged.fields, rec.fields, config.max_literals)
        groups.append(merged)
    return groups
