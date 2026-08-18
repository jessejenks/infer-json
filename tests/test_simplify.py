from infer_json.config import Config
from infer_json.simplify import (
    count_literals,
    merge_similar_records,
    widen_literals,
)
from infer_json.type_exprs import (
    BoolType,
    IntType,
    ListType,
    MapType,
    RecordType,
    StringLiteralType,
    StringType,
    UnionType,
)


class TestMergeSimilarRecords:
    def test_merges_similar_records(self):
        a = RecordType({"x": (StringType, True), "y": (IntType, True), "z": (BoolType, True)})
        b = RecordType({"x": (StringType, True), "y": (IntType, True), "w": (StringType, True)})
        result = merge_similar_records([a, b], 2)
        assert len(result) == 1
        assert result[0].kind == "record"
        assert "w" in result[0].fields
        assert "z" in result[0].fields

    def test_no_merge_below_threshold(self):
        a = RecordType({"x": (StringType, True), "y": (IntType, True)})
        b = RecordType({"a": (StringType, True), "b": (IntType, True)})
        result = merge_similar_records([a, b], 3)
        assert len(result) == 2

    def test_merges_list_wrapped_records(self):
        a = ListType(RecordType({"x": (StringType, True), "y": (IntType, True), "z": (BoolType, True)}))
        b = ListType(RecordType({"x": (StringType, True), "y": (IntType, True), "w": (StringType, True)}))
        result = merge_similar_records([a, b], 2)
        assert len(result) == 1
        assert result[0].kind == "list"
        assert result[0].element_type.kind == "record"

    def test_merges_map_wrapped_records(self):
        a = MapType(RecordType({"x": (StringType, True), "y": (IntType, True), "z": (BoolType, True)}))
        b = MapType(RecordType({"x": (StringType, True), "y": (IntType, True), "w": (StringType, True)}))
        result = merge_similar_records([a, b], 2)
        assert len(result) == 1
        assert result[0].kind == "map"
        assert result[0].value_type.kind == "record"


class TestWidenLiterals:
    def test_preserves_discriminant(self):
        t = RecordType({"type": (StringLiteralType("foo"), True), "name": (StringLiteralType("bar"), True)})
        result = widen_literals(t, "type", Config(max_literals=0))
        assert result.kind == "record"
        assert result.fields["type"] == (StringLiteralType("foo"), True)
        assert result.fields["name"] == (StringType, True)

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
        assert result is StringType

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

    def test_duplicates_counted_once(self):
        t = UnionType([StringLiteralType("a"), StringLiteralType("b"), StringLiteralType("a")])
        assert count_literals(t) == 2
