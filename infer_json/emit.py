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


def snake_to_pascal(s: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]", "_", s)
    return "".join(w[0].upper() + w[1:] for w in normalized.split("_") if w)


def prepare_variants(
    named_types: list[tuple[str | None, TypeExpr]], config: Config
) -> tuple[dict[str, TypeExpr], list[TypeExpr]]:
    extracted: dict[str, TypeExpr] = {}
    variants: list[TypeExpr] = []
    single_variant = len(named_types) == 1

    variant_idx = 0
    for name, simplified in named_types:
        label = snake_to_pascal(name) if name else config.root if single_variant else f"{config.variant}{variant_idx}"

        if simplified.kind == "list" and single_variant:
            path = [label, "item"]
        else:
            path = [label]

        extracted_top = extract_named_types(simplified, path, extracted, config.prefix, is_root=single_variant)
        if extracted_top.kind not in ("ref", "list", "map"):
            extracted[label] = extracted_top
            extracted_top = NamedRef(label)
        if name is None and extracted_top.kind == "ref":
            variant_idx += 1
        variants.append(extracted_top)

    return extracted, variants


def extract_named_types(
    t: TypeExpr,
    path: list[str],
    extracted: dict[str, TypeExpr],
    prefix="",
    is_root=False,
) -> TypeExpr:
    match t.kind:
        case "record":
            new_fields: dict[str, tuple[TypeExpr, bool]] = {}
            for k, (v, r) in t.fields.items():
                new_fields[k] = (extract_named_types(v, [*path, k], extracted, prefix), r)
            name = "".join(snake_to_pascal(p) for p in path)
            if prefix and not is_root:
                name = f"{prefix}{name}"
            if name in extracted:
                suffix = 2
                while f"{name}{suffix}" in extracted:
                    suffix += 1
                name = f"{name}{suffix}"
            extracted[name] = RecordType(new_fields)
            return NamedRef(name)
        case "list":
            return ListType(extract_named_types(t.element_type, path, extracted, prefix))
        case "union":
            return UnionType([extract_named_types(m, path, extracted, prefix) for m in t.members])
        case "map":
            return MapType(extract_named_types(t.value_type, path, extracted, prefix))
        case _:
            return t
