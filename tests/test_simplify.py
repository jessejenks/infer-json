from infer_json.config import Config
from infer_json.simplify import (
    count_literals,
    dedup_union_members,
    simplify_unions,
    type_eq,
    widen_literals,
)
from infer_json.type_exprs import (
    BoolType,
    IntType,
    ListType,
    MapType,
    Null,
    RecordType,
    StringLiteralType,
    StringType,
    UnionType,
    Unknown,
    flatten_union_members,
)


class TestTypeEq:
    def test_atoms(self):
        assert type_eq(StringType, StringType)
        assert not type_eq(StringType, IntType)

    def test_literals(self):
        assert type_eq(StringLiteralType("a"), StringLiteralType("a"))
        assert not type_eq(StringLiteralType("a"), StringLiteralType("b"))

    def test_records(self):
        a = RecordType({"x": StringType})
        b = RecordType({"x": StringType})
        c = RecordType({"x": IntType})
        assert type_eq(a, b)
        assert not type_eq(a, c)

    def test_different_kinds(self):
        assert not type_eq(StringType, StringLiteralType("x"))
        assert not type_eq(Unknown, Null)


class TestFlatten:
    def test_nested_unions(self):
        inner = UnionType([StringType, IntType])
        outer = UnionType([inner, BoolType])
        flat = flatten_union_members(outer.members)
        assert len(flat) == 3

    def test_no_unions(self):
        flat = flatten_union_members([StringType, IntType])
        assert len(flat) == 2


class TestDedup:
    def test_removes_duplicates(self):
        result = dedup_union_members([StringType, IntType, StringType, StringType])
        assert len(result) == 2

    def test_dedup_records(self):
        a = RecordType({"x": StringType})
        b = RecordType({"x": StringType})
        result = dedup_union_members([a, b])
        assert len(result) == 1

    def test_flattens_and_deduplicates(self):
        inner = UnionType([StringType, IntType])
        result = dedup_union_members([inner, StringType, BoolType])
        assert len(result) == 3


class TestSimplifyUnions:
    def test_single_member_collapses(self):
        t = UnionType([StringType])
        result = simplify_unions(t, 0)
        assert result is StringType

    def test_dedup_in_record_field(self):
        t = RecordType({"x": UnionType([StringType, StringType])})
        result = simplify_unions(t, 0)
        assert result.fields["x"] is StringType  # type: ignore

    def test_merges_similar_records(self):
        a = RecordType({"x": StringType, "y": IntType, "z": BoolType})
        b = RecordType({"x": StringType, "y": IntType, "w": StringType})
        t = UnionType([a, b])
        result = simplify_unions(t, 2)
        assert result.kind == "record"
        assert "w" in result.fields
        assert "z" in result.fields

    def test_no_merge_below_threshold(self):
        a = RecordType({"x": StringType, "y": IntType})
        b = RecordType({"a": StringType, "b": IntType})
        t = UnionType([a, b])
        result = simplify_unions(t, 3)
        assert result.kind == "union"

    def test_merges_list_wrapped_records(self):
        a = ListType(RecordType({"x": StringType, "y": IntType, "z": BoolType}))
        b = ListType(RecordType({"x": StringType, "y": IntType, "w": StringType}))
        t = UnionType([a, b])
        result = simplify_unions(t, 2)
        assert result.kind == "list"
        assert result.element_type.kind == "record"

    def test_merges_map_wrapped_records(self):
        a = MapType(RecordType({"x": StringType, "y": IntType, "z": BoolType}))
        b = MapType(RecordType({"x": StringType, "y": IntType, "w": StringType}))
        t = UnionType([a, b])
        result = simplify_unions(t, 2)
        assert result.kind == "map"
        assert result.value_type.kind == "record"


class TestWidenLiterals:
    def test_preserves_discriminant(self):
        t = RecordType({"type": StringLiteralType("foo"), "name": StringLiteralType("bar")})
        result = widen_literals(t, "type", Config(max_literals=0))
        assert result.fields["type"] == StringLiteralType("foo")  # type: ignore
        assert result.fields["name"] is StringType  # type: ignore

    def test_widens_all_when_zero(self):
        t = StringLiteralType("x")
        assert widen_literals(t, None, Config(max_literals=0)) is StringType

    def test_keeps_small_unions(self):
        t = UnionType([StringLiteralType("a"), StringLiteralType("b")])
        result = widen_literals(t, None, Config(max_literals=10))
        assert result.kind == "union"
        assert all(m.kind == "string_literal" for m in result.members)

    def test_widens_large_unions(self):
        t = UnionType([StringLiteralType(str(i)) for i in range(20)])
        result = widen_literals(t, None, Config(max_literals=10))
        assert result.kind == "union"
        assert all(m is StringType for m in result.members)

    def test_widens_long_literals(self):
        t = StringLiteralType("x" * 200)
        result = widen_literals(t, None, Config(max_literal_length=100))
        assert result is StringType

    def test_keeps_short_literals(self):
        t = StringLiteralType("short")
        result = widen_literals(t, None, Config(max_literals=10, max_literal_length=100))
        assert result.kind == "string_literal"

    def test_max_literal_length_disabled(self):
        t = StringLiteralType("x" * 200)
        result = widen_literals(t, None, Config(max_literals=10, max_literal_length=0))
        assert result.kind == "string_literal"


class TestCountLiterals:
    def test_single(self):
        assert count_literals(StringLiteralType("x")) == 1

    def test_non_literal(self):
        assert count_literals(StringType) == 0

    def test_union(self):
        t = UnionType([StringLiteralType("a"), StringLiteralType("b"), IntType])
        assert count_literals(t) == 2
