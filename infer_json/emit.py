from __future__ import annotations

import re

from .config import Config
from .type_exprs import (
    ListType,
    MapType,
    NamedRef,
    RecordType,
    TypeExpr,
    UnionType,
)


def normalize_to_pascal(s: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]", "_", s)
    return "".join(w[0].upper() + w[1:] for w in normalized.split("_") if w)


def needs_root_definition(named_types: list[tuple[str | None, TypeExpr]]) -> bool:
    return len(named_types) != 1 or named_types[0][1].kind != "record"


def prepare_variants(
    named_types: list[tuple[str | None, TypeExpr]],
    config: Config,
) -> tuple[dict[str, TypeExpr], list[TypeExpr]]:
    extracted: dict[str, TypeExpr] = {}
    variants: list[TypeExpr] = []
    single_variant = len(named_types) == 1

    variant_idx = 0
    for name, simplified in named_types:
        if name is not None:
            label = f"{config.prefix}{normalize_to_pascal(name)}"
        elif single_variant:
            if simplified.kind in ("list", "map", "union"):
                label = f"{config.prefix}{config.variant}"
            else:
                label = f"{config.prefix}{config.root}"
        else:
            label = f"{config.prefix}{config.variant}{variant_idx}"
            variant_idx += 1

        variants.append(extract_named_types(simplified, [label], extracted))

    return extracted, variants


def extract_named_types(
    t: TypeExpr,
    path: list[str],
    extracted: dict[str, TypeExpr],
) -> TypeExpr:
    match t.kind:
        case "record":
            new_fields: dict[str, tuple[TypeExpr, bool]] = {}
            for k, (v, r) in t.fields.items():
                path.append(k)
                new_fields[k] = (extract_named_types(v, path, extracted), r)
                path.pop()
            name = "".join(normalize_to_pascal(p) for p in path)
            if name in extracted:
                suffix = 2
                while f"{name}{suffix}" in extracted:
                    suffix += 1
                name = f"{name}{suffix}"
            extracted[name] = RecordType(new_fields)
            return NamedRef(name)
        case "list":
            return ListType(extract_named_types(t.element_type, path, extracted))
        case "map":
            return MapType(extract_named_types(t.value_type, path, extracted))
        case "union":
            return UnionType([extract_named_types(m, path, extracted) for m in t.members])
        case _:
            return t


_cache: dict[int, str] = {0: ""}


def get_indent(depth: int, config: Config) -> str:
    depth = max(0, depth)
    if depth not in _cache:
        unit = (" " * config.tab_width) if config.use_spaces else "\t"
        _cache[depth] = unit * depth
    return _cache[depth]
