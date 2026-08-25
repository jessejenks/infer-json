from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias


@dataclass(frozen=True)
class UnknownType:
    kind: Literal["unknown"] = "unknown"


@dataclass(frozen=True)
class AtomicType:
    name: Literal["null", "boolean", "int", "float", "string"]
    kind: Literal["atom"] = "atom"


@dataclass(frozen=True)
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
    # T ≤ T
    # unknown ≤ T
    if a is b or a.kind == "unknown":
        return True

    if a.kind == b.kind:
        # T ≤ T
        # int ≤ float
        if a.kind == "atom":
            return a.name == b.name or (a.name == "int" and b.name == "float")  # type: ignore[union-attr]
        # T ≤ T
        if a.kind == "string_literal":
            return a.value == b.value  # type: ignore[union-attr]
        # List T ≤ List S if T ≤ S
        if a.kind == "list":
            return is_subtype(a.element_type, b.element_type)  # type: ignore[union-attr]
        # Map[K]T ≤ Map[K]S if T ≤ S
        if a.kind == "map":
            return is_subtype(a.value_type, b.value_type)  # type: ignore[union-attr]
        if a.kind == "record":
            return _is_subtype_records(a.fields, b.fields)  # type: ignore[union-attr]
        # A1 | ... | An ≤ T if forall i, Ai ≤ T
        if a.kind == "union":
            return all(is_subtype(u_m, b) for u_m in a.members)  # type: ignore[union-attr]
        return a == b

    # literal ≤ string
    if a.kind == "string_literal" and b.kind == "atom":
        return b.name == "string"
    # A1 | ... | An ≤ T if forall i, Ai ≤ T
    if a.kind == "union":
        return all(is_subtype(u_m, b) for u_m in a.members)
    # A ≤ B1 | ... | Bm if exists j, A ≤ Bj
    if b.kind == "union":
        return any(is_subtype(a, v_m) for v_m in b.members)

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


def _dedup_atoms_and_literals(
    members: list[TypeExpr],
) -> tuple[list[AtomicType | StringLiteralType], list[TypeExpr]]:
    simple: list[AtomicType | StringLiteralType] = []
    structural: list[TypeExpr] = []
    seen_atoms: set[AtomicType] = set()
    seen_literal_values: set[str] = set()

    for x in members:
        # unknown | T = T
        if x is Unknown:
            continue

        if x.kind == "atom":
            # T | T = T
            if x in seen_atoms:
                continue
            # int | float = float
            if x is IntType and FloatType in seen_atoms:
                continue
            if x is FloatType and IntType in seen_atoms:
                simple = [y for y in simple if y is not IntType]
                seen_atoms.discard(IntType)
            seen_atoms.add(x)
            # "a" | string = string
            if x is StringType and seen_literal_values:
                simple = [y for y in simple if y.kind != "string_literal"]
                seen_literal_values.clear()
            simple.append(x)

        elif x.kind == "string_literal":
            # "a" | string = string
            if StringType in seen_atoms:
                continue
            # T | T = T
            if x.value in seen_literal_values:
                continue
            seen_literal_values.add(x.value)
            simple.append(x)

        else:
            structural.append(x)

    return simple, structural


def merge_union_members(members: list[TypeExpr]) -> list[TypeExpr]:
    simple, structural = _dedup_atoms_and_literals(members)
    result: list[TypeExpr] = []
    for x in structural:
        if any(is_subtype(x, y) for y in result):
            continue
        result = [y for y in result if not is_subtype(y, x)]
        result.append(x)
    return simple + result


def merge(a: TypeExpr, b: TypeExpr) -> TypeExpr:
    if a is b or a == b:
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
        case (StringLiteralType(), StringLiteralType()):
            return UnionType([a, b])
        case (RecordType(), RecordType()):
            return merge_records(a.fields, b.fields)
        case _:
            result = merge_union_members(flatten_union_members([a, b]))
            if not result:
                return Unknown
            if len(result) == 1:
                return result[0]
            return UnionType(result)
