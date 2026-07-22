from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal, TypeAlias


@dataclass
class UnknownType:
    kind: Literal["unknown"] = "unknown"


@dataclass
class NullType:
    kind: Literal["null"] = "null"


@dataclass
class AtomicType:
    name: str
    kind: Literal["atom"] = "atom"


@dataclass
class StringLiteralType:
    value: str
    kind: Literal["string_literal"] = "string_literal"


@dataclass
class ListType:
    element_type: TypeExpr
    kind: Literal["list"] = "list"


@dataclass
class RecordType:
    fields: Dict[str, TypeExpr]
    kind: Literal["record"] = "record"


@dataclass
class NullableType:
    element_type: TypeExpr
    kind: Literal["nullable"] = "nullable"


@dataclass
class UnionType:
    members: List[TypeExpr]
    kind: Literal["union"] = "union"


@dataclass
class MapType:
    value_type: TypeExpr
    kind: Literal["map"] = "map"


@dataclass
class NamedRef:
    name: str
    kind: Literal["ref"] = "ref"


TypeExpr: TypeAlias = (
    UnknownType
    | NullType
    | AtomicType
    | StringLiteralType
    | ListType
    | RecordType
    | MapType
    | NullableType
    | UnionType
    | NamedRef
)

Unknown = UnknownType()
Null = NullType()
StringType = AtomicType("string")
NumberType = AtomicType("number")
BoolType = AtomicType("boolean")


def flatten_union_members(members: List[TypeExpr]) -> List[TypeExpr]:
    result: List[TypeExpr] = []
    for m in members:
        if m.kind == "union":
            result.extend(flatten_union_members(m.members))
        else:
            result.append(m)
    return result
