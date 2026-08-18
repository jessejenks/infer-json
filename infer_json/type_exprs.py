from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias


@dataclass
class UnknownType:
    kind: Literal["unknown"] = "unknown"


@dataclass
class AtomicType:
    name: Literal["null", "boolean", "int", "float", "string"]
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
class MapType:
    value_type: TypeExpr
    kind: Literal["map"] = "map"


@dataclass
class RecordType:
    fields: dict[str, tuple[TypeExpr, bool]]
    kind: Literal["record"] = "record"


@dataclass
class UnionType:
    members: list[TypeExpr]
    kind: Literal["union"] = "union"

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, UnionType):
            return False
        if len(self.members) != len(value.members):
            return False
        return all(a in value.members for a in self.members)


@dataclass
class NamedRef:
    name: str
    kind: Literal["ref"] = "ref"


TypeExpr: TypeAlias = (
    UnknownType | AtomicType | StringLiteralType | ListType | MapType | RecordType | UnionType | NamedRef
)

Unknown = UnknownType()
Null = AtomicType("null")
BoolType = AtomicType("boolean")
IntType = AtomicType("int")
FloatType = AtomicType("float")
StringType = AtomicType("string")


def _is_subtype_records(a: dict[str, tuple[TypeExpr, bool]], b: dict[str, tuple[TypeExpr, bool]]):
    for k, (t, req) in a.items():
        if k not in b:
            return False
        s, reqb = b[k]
        # if T ≤ S
        # {k : T} ≤ {k : S}
        # {k : T} ≤ {k?: S}
        # {k?: T} ≤ {k?: S}
        if (req or not reqb) and is_subtype(t, s):
            continue
        # {k?: T} ≰ {k: S}
        return False
    for k, (_, req) in b.items():
        if k in a:
            continue  # already checked
        if req:
            return False
    # {} ≤ {k?: S}
    return True


def is_subtype(a: TypeExpr, b: TypeExpr) -> bool:
    if a == b:
        return True
    match (a, b):
        case (UnknownType(), _):
            return True
        case (AtomicType(name=u), AtomicType(name=v)):
            return u == "int" and v == "float"
        case (StringLiteralType(), AtomicType(name="string")):
            return True
        case (ListType(element_type=u), ListType(element_type=v)):
            return is_subtype(u, v)
        case (MapType(value_type=u), MapType(value_type=v)):
            return is_subtype(u, v)
        case (RecordType(), RecordType()):
            return _is_subtype_records(a.fields, b.fields)
        case (UnionType(members=u), _):
            return all(is_subtype(u_m, b) for u_m in u)
        case (_, UnionType(members=v)):
            return any(is_subtype(a, v_m) for v_m in v)
        case _:
            return False


def merge_records(a: dict[str, tuple[TypeExpr, bool]], b: dict[str, tuple[TypeExpr, bool]]) -> RecordType:
    result: dict[str, tuple[TypeExpr, bool]] = {}
    for k in [*a.keys(), *(k for k in b if k not in a)]:
        if k in a and k in b:
            ta, ra = a[k]
            tb, rb = b[k]
            result[k] = (merge(ta, tb), ra and rb)
        elif k in a:
            result[k] = (a[k][0], False)
        else:
            result[k] = (b[k][0], False)
    return RecordType(result)


def flatten_union_members(members: list[TypeExpr]):
    stack = list(reversed(members))
    flat: list[TypeExpr] = []
    while stack:
        m = stack.pop()
        if m.kind == "union":
            stack.extend(reversed(m.members))
        else:
            flat.append(m)
    return flat


def merge_union_members(members: list[TypeExpr]) -> list[TypeExpr]:
    result: list[TypeExpr] = []
    for x in members:
        if any(is_subtype(x, y) for y in result):
            continue
        result = [y for y in result if not is_subtype(y, x)]
        result.append(x)
    return result


def merge(a: TypeExpr, b: TypeExpr) -> TypeExpr:
    if a == b:
        return a
    match (a, b):
        case (UnknownType(), c) | (c, UnknownType()):
            return c
        case (AtomicType(name=u), AtomicType(name=v)):
            if u == "int" and v == "float":
                return b
            if u == "float" and v == "int":
                return a
            return UnionType([a, b])
        case (StringLiteralType(), AtomicType(name="string")):
            return b
        case (AtomicType(name="string"), StringLiteralType()):
            return a
        case (RecordType(), RecordType()):
            return merge_records(a.fields, b.fields)
        case _:
            result = merge_union_members(flatten_union_members([a, b]))
            if not result:
                return Unknown
            if len(result) == 1:
                return result[0]
            return UnionType(result)
