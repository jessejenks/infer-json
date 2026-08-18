from __future__ import annotations

from typing import Any

from .config import Config
from .type_exprs import (
    BoolType,
    FloatType,
    IntType,
    ListType,
    MapType,
    Null,
    RecordType,
    StringLiteralType,
    TypeExpr,
    Unknown,
    merge,
)


def _looks_like_map_keys(keys: Any, max_key_length: int) -> bool:
    if max_key_length == 0:
        return False
    for k in keys:
        if len(k) > max_key_length:
            return True
    return False


def infer_type(value: Any, config: Config, depth: int = 0) -> TypeExpr:
    if value is None:
        return Null
    if isinstance(value, bool):
        return BoolType
    if isinstance(value, int):
        return IntType
    if isinstance(value, float):
        return FloatType
    if isinstance(value, str):
        return StringLiteralType(value)
    if isinstance(value, list):
        if len(value) == 0:
            return ListType(Unknown)
        elem_type: TypeExpr = Unknown
        for v in value:
            elem_type = merge(elem_type, infer_type(v, config, depth))
        return ListType(elem_type)
    if config.max_depth > 0 and config.max_depth == depth:
        return Unknown
    if isinstance(value, dict):
        if _looks_like_map_keys(value.keys(), config.max_key_length):
            val_type: TypeExpr = Unknown
            for v in value.values():
                val_type = merge(val_type, infer_type(v, config, depth + 1))
            return MapType(val_type)
        return RecordType({k: (infer_type(v, config, depth + 1), True) for k, v in value.items()})
    return Unknown
