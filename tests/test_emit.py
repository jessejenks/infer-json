from infer_json.emit import extract_named_types, snake_to_pascal
from infer_json.emit_go import type_to_go
from infer_json.emit_ts import type_to_ts
from infer_json.type_exprs import (
    BoolType,
    FloatType,
    IntType,
    ListType,
    MapType,
    NamedRef,
    Null,
    RecordType,
    StringLiteralType,
    StringType,
    TypeExpr,
    UnionType,
    Unknown,
)


class TestSnakeToPascal:
    def test_basic(self):
        assert snake_to_pascal("hello_world") == "HelloWorld"

    def test_kebab(self):
        assert snake_to_pascal("queue-operation") == "QueueOperation"

    def test_single(self):
        assert snake_to_pascal("foo") == "Foo"


class TestTypeToTs:
    def test_primitives(self):
        assert type_to_ts(Unknown) == "unknown"
        assert type_to_ts(Null) == "null"
        assert type_to_ts(StringType) == "string"
        assert type_to_ts(IntType) == "number"
        assert type_to_ts(FloatType) == "number"
        assert type_to_ts(BoolType) == "boolean"

    def test_literal(self):
        assert type_to_ts(StringLiteralType("foo")) == '"foo"'

    def test_list(self):
        assert type_to_ts(ListType(StringType)) == "string[]"

    def test_list_of_union_gets_parens(self):
        t = ListType(UnionType([StringType, IntType]))
        assert type_to_ts(t) == "(string | number)[]"

    def test_map(self):
        assert type_to_ts(MapType(StringType)) == "Record<string, string>"

    def test_ref(self):
        assert type_to_ts(NamedRef("Foo")) == "Foo"

    def test_record(self):
        t = RecordType({"name": (StringType, True), "age": (IntType, True)})
        result = type_to_ts(t)
        assert "name: string;" in result
        assert "age: number;" in result

    def test_optional_fields(self):
        t = RecordType({"name": (StringType, False)})
        result = type_to_ts(t)
        assert "name?: string;" in result


class TestTypeToGo:
    def test_primitives(self):
        assert type_to_go(Unknown) == "any"
        assert type_to_go(Null) == "any"
        assert type_to_go(StringType) == "string"
        assert type_to_go(IntType) == "int"
        assert type_to_go(FloatType) == "float64"
        assert type_to_go(BoolType) == "bool"

    def test_literal(self):
        assert type_to_go(StringLiteralType("foo")) == "string"

    def test_list(self):
        assert type_to_go(ListType(StringType)) == "[]string"

    def test_list_of_union_gets_parens(self):
        t = ListType(UnionType([StringType, IntType]))
        assert type_to_go(t) == "[]any"

    def test_map(self):
        assert type_to_go(MapType(StringType)) == "map[string]string"

    def test_ref(self):
        assert type_to_go(NamedRef("Foo")) == "Foo"

    def test_record(self):
        t = RecordType({"name": (StringType, True), "age": (IntType, True)})
        result = type_to_go(t)
        assert 'Name string `json:"name"`' in result
        assert 'Age int `json:"age"`' in result

    def test_optional_fields(self):
        t = RecordType({"name": (StringType, False)})
        result = type_to_go(t)
        assert 'Name *string `json:"name,omitempty"`' in result


class TestExtractNamedTypes:
    def test_simple_record(self):
        t = RecordType({"x": (StringType, True)})
        extracted: dict[str, TypeExpr] = {}
        ref = extract_named_types(t, ["Foo"], extracted)
        assert ref.kind == "ref"
        assert ref.name == "Foo"
        assert "Foo" in extracted
        foo = extracted["Foo"]
        assert foo.kind == "record"
        assert foo.fields["x"][0] is StringType

    def test_nested_records(self):
        inner = RecordType({"y": (IntType, True)})
        outer = RecordType({"child": (inner, True)})
        extracted = {}
        extract_named_types(outer, ["Parent"], extracted)
        assert "Parent" in extracted
        assert "ParentChild" in extracted

    def test_dedup_names(self):
        t1 = RecordType({"x": (StringType, True)})
        t2 = RecordType({"y": (IntType, True)})
        extracted = {}
        extract_named_types(t1, ["Foo"], extracted)
        extract_named_types(t2, ["Foo"], extracted)
        assert "Foo" in extracted
        assert "Foo2" in extracted

    def test_map_value_extracted(self):
        inner = RecordType({"val": (StringType, True)})
        t = RecordType({"data": (MapType(inner), True)})
        extracted = {}
        extract_named_types(t, ["Root"], extracted)
        assert "Root" in extracted
        assert "RootData" in extracted
