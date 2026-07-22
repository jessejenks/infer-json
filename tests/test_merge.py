from infer_json.config import Config
from infer_json.infer import _has_data_keys, infer_type
from infer_json.merge import merge, merge_records
from infer_json.type_exprs import (
    BoolType,
    ListType,
    MapType,
    Null,
    NullableType,
    NumberType,
    RecordType,
    StringLiteralType,
    StringType,
    Unknown,
)


class TestMerge:
    def test_unknown_is_identity(self):
        assert merge(Unknown, StringType) is StringType
        assert merge(NumberType, Unknown) is NumberType
        assert merge(Unknown, Unknown) is Unknown

    def test_null_makes_nullable(self):
        result = merge(Null, StringType)
        assert result.kind == "nullable"
        assert result.element_type is StringType

    def test_null_with_nullable_is_idempotent(self):
        nullable_str = NullableType(StringType)
        assert merge(Null, nullable_str) is nullable_str

    def test_same_atom_merges(self):
        assert merge(StringType, StringType) is StringType

    def test_different_atoms_become_union(self):
        result = merge(StringType, NumberType)
        assert result.kind == "union"
        assert len(result.members) == 2

    def test_same_literal_stays(self):
        a = StringLiteralType("foo")
        assert merge(a, StringLiteralType("foo")) == a

    def test_different_literals_create_union(self):
        result = merge(StringLiteralType("a"), StringLiteralType("b"))
        assert result.kind == "union"
        assert len(result.members) == 2
        assert result.members[0] == StringLiteralType("a")
        assert result.members[1] == StringLiteralType("b")

    def test_literal_and_string_widen(self):
        assert merge(StringLiteralType("x"), StringType) is StringType
        assert merge(StringType, StringLiteralType("x")) is StringType

    def test_list_merge(self):
        a = ListType(StringType)
        b = ListType(NumberType)
        result = merge(a, b)
        assert result.kind == "list"
        assert result.element_type.kind == "union"

    def test_record_merge_shared_keys(self):
        a = RecordType({"x": StringType, "y": NumberType})
        b = RecordType({"x": StringType, "z": BoolType})
        result = merge_records(a, b)
        assert "x" in result.fields
        assert result.fields["y"].kind == "nullable"
        assert result.fields["z"].kind == "nullable"

    def test_map_merge(self):
        a = MapType(StringType)
        b = MapType(NumberType)
        result = merge(a, b)
        assert result.kind == "map"
        assert result.value_type.kind == "union"


class TestInferType:
    def test_primitives(self):
        config = Config()
        assert infer_type(None, config) is Null
        assert infer_type(True, config) is BoolType
        assert infer_type(42, config) is NumberType
        assert infer_type(3.14, config) is NumberType
        assert infer_type("hi", config) == StringLiteralType("hi")

    def test_empty_list(self):
        result = infer_type([], Config())
        assert result.kind == "list"
        assert result.element_type is Unknown

    def test_dict_becomes_record(self):
        result = infer_type({"a": 1, "b": "x"}, Config())
        assert result.kind == "record"
        assert result.fields["a"] is NumberType

    def test_data_keys_become_map(self):
        result = infer_type({"src/foo.ts": 1, "src/bar.ts": 2}, Config())
        assert result.kind == "map"
        assert result.value_type is NumberType

    def test_long_keys_become_map(self):
        result = infer_type({"a_very_long_key_name_that_exceeds": 1}, Config(max_key_length=10))
        assert result.kind == "map"

    def test_data_key_detection_disabled(self):
        result = infer_type({"src/foo.ts": 1}, Config(max_key_length=0))
        assert result.kind == "record"


class TestHasDataKeys:
    def test_slash(self):
        assert _has_data_keys(["src/foo"], 25)

    def test_space(self):
        assert _has_data_keys(["hello world"], 25)

    def test_dot(self):
        assert _has_data_keys(["file.txt"], 25)

    def test_normal_keys(self):
        assert not _has_data_keys(["foo", "bar_baz", "$ref"], 25)

    def test_length(self):
        assert _has_data_keys(["short", "a" * 30], 25)
        assert not _has_data_keys(["short"], 25)
