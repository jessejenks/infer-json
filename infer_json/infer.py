from __future__ import annotations

import re
from typing import Any, Dict

from .config import Config
from .merge import merge
from .type_exprs import (
    BoolType,
    ListType,
    MapType,
    Null,
    NumberType,
    RecordType,
    StringLiteralType,
    TypeExpr,
    Unknown,
)

_NON_IDENTIFIER_RE = re.compile(r"[^a-zA-Z0-9_$]")


def _has_data_keys(keys: Any, max_key_length: int) -> bool:
    if max_key_length == 0:
        return False
    for k in keys:
        if len(k) > max_key_length:
            return True
        if _NON_IDENTIFIER_RE.search(k):
            return True
    return False


def infer_type(value: Any, config: Config) -> TypeExpr:
    if value is None:
        return Null
    if isinstance(value, bool):
        return BoolType
    if isinstance(value, int) or isinstance(value, float):
        return NumberType
    if isinstance(value, str):
        return StringLiteralType(value)
    if isinstance(value, list):
        if len(value) == 0:
            return ListType(Unknown)
        elem_type: TypeExpr = Unknown
        for v in value:
            elem_type = merge(elem_type, infer_type(v, config))
        return ListType(elem_type)
    if isinstance(value, dict):
        if _has_data_keys(value.keys(), config.max_key_length):
            val_type: TypeExpr = Unknown
            for v in value.values():
                val_type = merge(val_type, infer_type(v, config))
            return MapType(val_type)
        fields: Dict[str, TypeExpr] = {}
        for k, v in value.items():
            fields[k] = infer_type(v, config)
        return RecordType(fields)
    return Unknown
