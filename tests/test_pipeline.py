from infer_json.config import Config
from infer_json.pipeline import run_pipeline
from infer_json.type_exprs import (
    BoolType,
    FloatType,
    IntType,
    ListType,
    MapType,
    Null,
    NullableType,
    RecordType,
    StringLiteralType,
    StringType,
    UnionType,
)


class TestDefaultConfig:
    def test_simple_record(self):
        named_types = run_pipeline([{"foo": "bar", "count": 1, "pi": 3.14, "done": None}], Config())
        assert named_types == [
            ("Root", RecordType({"foo": StringType, "count": IntType, "pi": FloatType, "done": Null}))
        ]

    def test_list_of_simple_record(self):
        named_types = run_pipeline([{"key": [{"foo": "bar", "count": 1, "pi": 3.14, "done": None}]}], Config())
        assert named_types == [
            (
                "Root",
                RecordType(
                    {"key": ListType(RecordType({"foo": StringType, "count": IntType, "pi": FloatType, "done": Null}))}
                ),
            )
        ]

    def test_merges_objects_with_same_keys(self):
        named_types = run_pipeline(
            [
                {"foo": "bar"},
                {"foo": None},
            ],
            Config(),
        )
        assert named_types == [("Root", RecordType({"foo": NullableType(StringType)}))]

    def test_nested_records_preserved(self):
        named_types = run_pipeline([{"outer": {"inner": 1}}], Config())
        assert named_types == [("Root", RecordType({"outer": RecordType({"inner": IntType})}))]

    def test_literals_widened_by_default(self):
        named_types = run_pipeline(
            [
                {"status": "active"},
                {"status": "inactive"},
            ],
            Config(),
        )
        assert named_types == [("Root", RecordType({"status": StringType}))]


class TestLiterals:
    def test_kept_within_max_literals(self):
        named_types = run_pipeline(
            [
                {"status": "active"},
                {"status": "inactive"},
            ],
            Config(max_literals=5),
        )
        assert len(named_types) == 1
        first_type = named_types[0][1]
        assert first_type.kind == "record"
        field_type = first_type.fields["status"]
        assert field_type == UnionType([StringLiteralType("active"), StringLiteralType("inactive")])

    def test_long_literals_widened(self):
        named_types = run_pipeline(
            [{"key": "cffc1d89-62da-4a08-89e2-e13d85e908a7"}],
            Config(max_literals=5, max_literal_length=10),
        )
        assert len(named_types) == 1
        first_type = named_types[0][1]
        assert first_type.kind == "record"
        assert first_type.fields["key"] == StringType


class TestMapAndRecordInteraction:
    def test_all_maps(self):
        named_types = run_pipeline(
            [
                {"foo": "bar"},
                {"foo": "baz"},
            ],
            Config(max_key_length=1),
        )
        assert named_types == [("Root", MapType(StringType))]

    def test_map_values_deduped(self):
        named_types = run_pipeline(
            [
                {"very-long-key-that-is-a-map": True},
                {"very-long-key-that-is-a-map": False},
            ],
            Config(),
        )
        assert named_types == [("Root", MapType(BoolType))]

    def test_map_literals_widened(self):
        named_types = run_pipeline(
            [{"very-long-key-that-is-a-map": "cffc1d89-62da-4a08-89e2-e13d85e908a7"}],
            Config(max_literal_length=10),
        )
        assert named_types == [("Root", MapType(StringType))]

    def test_mixed_without_flatten_keeps_both_variants(self):
        named_types = run_pipeline(
            [
                {"type": "dog", "bark": True},
                {"very-long-key-that-is-a-map": 42},
            ],
            Config(),
        )
        assert len(named_types) == 2
        assert named_types[0][1] == RecordType({"type": StringType, "bark": BoolType})
        assert named_types[1][1] == MapType(IntType)

    def test_flatten_collapses_records_into_map(self):
        named_types = run_pipeline(
            [
                {"enable": True, "very-long-key-that-is-a-map": "some-string"},
                {"enable": False},
            ],
            Config(flatten_maps=True),
        )
        assert named_types == [("Root", MapType(UnionType([BoolType, StringType])))]

    def test_flatten_deduplicates_value_types(self):
        named_types = run_pipeline(
            [
                {"enable": True, "very-long-key-that-is-a-map": True},
                {"enable": False},
            ],
            Config(flatten_maps=True),
        )
        assert named_types == [("Root", MapType(BoolType))]


class TestDiscriminant:
    def test_groups_by_discriminant_value(self):
        named_types = run_pipeline(
            [
                {"type": "dog", "bark": True},
                {"type": "dog", "bark": False},
                {"type": "cat", "purr": True},
            ],
            Config(find_discriminant=True),
        )
        assert len(named_types) == 2
        types_by_name = dict(named_types)
        dog = types_by_name["Dog"]
        assert dog.kind == "record"
        assert dog.fields["type"] == StringLiteralType("dog")
        cat = types_by_name["Cat"]
        assert cat.kind == "record"
        assert cat.fields["type"] == StringLiteralType("cat")

    def test_preserves_discriminant_literal_despite_max_literals(self):
        named_types = run_pipeline(
            [
                {"type": "dog", "bark": True},
                {"type": "cat", "purr": True},
            ],
            Config(find_discriminant=True, max_literals=0),
        )
        types_by_name = dict(named_types)
        dog = types_by_name["Dog"]
        assert dog.kind == "record"
        assert dog.fields["type"] == StringLiteralType("dog")

    def test_map_variant_alongside_discriminant(self):
        named_types = run_pipeline(
            [
                {"type": "dog", "bark": True},
                {"type": "dog", "bark": False},
                {"type": "cat", "purr": True},
                {"very-long-key-that-is-a-map": 42},
            ],
            Config(find_discriminant=True),
        )
        names = [name for name, _ in named_types]
        assert "Dog" in names
        assert "Cat" in names
        map_entry = named_types[-1]
        assert map_entry[0].startswith("Variant")
        assert map_entry[1] == MapType(IntType)


class TestNaming:
    def test_single_variant_is_root(self):
        named_types = run_pipeline([{"foo": 1}], Config())
        assert named_types[0][0] == "Root"

    def test_multiple_variants_are_numbered(self):
        named_types = run_pipeline(
            [
                {"foo": 1},
                {"bar": 2},
            ],
            Config(),
        )
        names = [name for name, _ in named_types]
        assert names == ["Variant0", "Variant1"]

    def test_discriminant_uses_pascal_cased_values(self):
        named_types = run_pipeline(
            [
                {"kind": "my_thing", "x": 1},
                {"kind": "other_thing", "y": 2},
            ],
            Config(find_discriminant=True),
        )
        names = [name for name, _ in named_types]
        assert "MyThing" in names
        assert "OtherThing" in names

    def test_single_map_is_root(self):
        named_types = run_pipeline(
            [{"very-long-key-that-is-a-map": 42}],
            Config(),
        )
        assert named_types[0][0] == "Root"
