from infer_json.config import Config
from infer_json.pipeline import _find_discriminant, run_pipeline
from infer_json.type_exprs import (
    BoolType,
    FloatType,
    IntType,
    ListType,
    MapType,
    Null,
    RecordType,
    StringLiteralType,
    StringType,
    UnionType,
)


class TestDefaultConfig:
    def test_simple_record(self):
        named_types = run_pipeline([{"foo": "bar", "count": 1, "pi": 3.14, "done": None}], Config())
        assert named_types == [
            (
                None,
                RecordType(
                    {
                        "foo": (StringType, True),
                        "count": (IntType, True),
                        "pi": (FloatType, True),
                        "done": (Null, True),
                    },
                ),
            )
        ]

    def test_list_of_simple_record(self):
        named_types = run_pipeline([{"key": [{"foo": "bar", "count": 1, "pi": 3.14, "done": None}]}], Config())
        assert named_types == [
            (
                None,
                RecordType(
                    {
                        "key": (
                            ListType(
                                RecordType(
                                    {
                                        "foo": (StringType, True),
                                        "count": (IntType, True),
                                        "pi": (FloatType, True),
                                        "done": (Null, True),
                                    }
                                )
                            ),
                            True,
                        )
                    }
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
        assert named_types == [(None, RecordType({"foo": (UnionType([StringType, Null]), True)}))]

    def test_nested_records_preserved(self):
        named_types = run_pipeline([{"outer": {"inner": 1}}], Config())
        assert named_types == [(None, RecordType({"outer": (RecordType({"inner": (IntType, True)}), True)}))]

    def test_literals_widened_by_default(self):
        named_types = run_pipeline(
            [
                {"status": "active"},
                {"status": "inactive"},
            ],
            Config(),
        )
        assert named_types == [(None, RecordType({"status": (StringType, True)}))]


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
        field_type = first_type.fields["status"][0]
        assert field_type == UnionType([StringLiteralType("active"), StringLiteralType("inactive")])

    def test_long_literals_widened(self):
        named_types = run_pipeline(
            [{"key": "cffc1d89-62da-4a08-89e2-e13d85e908a7"}],
            Config(max_literals=5, max_literal_length=10),
        )
        assert len(named_types) == 1
        first_type = named_types[0][1]
        assert first_type.kind == "record"
        assert first_type.fields["key"][0] is StringType


class TestMapAndRecordInteraction:
    def test_all_maps(self):
        named_types = run_pipeline(
            [
                {"foo": "bar"},
                {"foo": "baz"},
            ],
            Config(max_key_length=1),
        )
        assert named_types == [(None, MapType(StringType))]

    def test_map_values_deduped(self):
        named_types = run_pipeline(
            [
                {"very-long-key-that-is-a-map": True},
                {"very-long-key-that-is-a-map": False},
            ],
            Config(),
        )
        assert named_types == [(None, MapType(BoolType))]

    def test_map_literals_widened(self):
        named_types = run_pipeline(
            [{"very-long-key-that-is-a-map": "cffc1d89-62da-4a08-89e2-e13d85e908a7"}],
            Config(max_literal_length=10),
        )
        assert named_types == [(None, MapType(StringType))]

    def test_mixed_without_flatten_keeps_both_variants(self):
        named_types = run_pipeline(
            [
                {"type": "dog", "bark": True},
                {"very-long-key-that-is-a-map": 42},
            ],
            Config(),
        )
        assert len(named_types) == 2
        assert named_types[0][1] == RecordType({"type": (StringType, True), "bark": (BoolType, True)})
        assert named_types[1][1] == MapType(IntType)

    def test_flatten_collapses_records_into_map(self):
        named_types = run_pipeline(
            [
                {"enable": True, "very-long-key-that-is-a-map": "some-string"},
                {"enable": False},
            ],
            Config(flatten_maps=True),
        )
        assert named_types == [(None, MapType(UnionType([BoolType, StringType])))]

    def test_flatten_deduplicates_value_types(self):
        named_types = run_pipeline(
            [
                {"enable": True, "very-long-key-that-is-a-map": True},
                {"enable": False},
            ],
            Config(flatten_maps=True),
        )
        assert named_types == [(None, MapType(BoolType))]


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
        dog = types_by_name["dog"]
        assert dog.kind == "record"
        assert dog.fields["type"][0] == StringLiteralType("dog")
        cat = types_by_name["cat"]
        assert cat.kind == "record"
        assert cat.fields["type"][0] == StringLiteralType("cat")

    def test_preserves_discriminant_literal_despite_max_literals(self):
        named_types = run_pipeline(
            [
                {"type": "dog", "bark": True},
                {"type": "cat", "purr": True},
            ],
            Config(find_discriminant=True, max_literals=0),
        )
        types_by_name = dict(named_types)
        dog = types_by_name["dog"]
        assert dog.kind == "record"
        assert dog.fields["type"][0] == StringLiteralType("dog")

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
        assert "dog" in names
        assert "cat" in names
        map_entry = named_types[-1]
        assert map_entry[0] is None
        assert map_entry[1] == MapType(IntType)


class TestNaming:
    def test_single_variant_is_root(self):
        named_types = run_pipeline([{"foo": 1}], Config())
        assert named_types[0][0] is None

    def test_multiple_variants_are_numbered(self):
        named_types = run_pipeline(
            [
                {"foo": 1},
                {"bar": 2},
            ],
            Config(),
        )
        names = [name for name, _ in named_types]
        assert names == [None, None]

    def test_discriminant_uses_pascal_cased_values(self):
        named_types = run_pipeline(
            [
                {"kind": "my_thing", "x": 1},
                {"kind": "other_thing", "y": 2},
            ],
            Config(find_discriminant=True),
        )
        names = [name for name, _ in named_types]
        assert "my_thing" in names
        assert "other_thing" in names

    def test_single_map_is_root(self):
        named_types = run_pipeline(
            [{"very-long-key-that-is-a-map": 42}],
            Config(),
        )
        assert named_types[0][0] is None

    def test_custom_root_name(self):
        named_types = run_pipeline([{"foo": 1}], Config(root="Api"))
        assert named_types[0][0] == None


class TestDiscriminantDiscovery:
    def test_finds_discriminant_key(self):
        groups = [
            RecordType({"type": (StringLiteralType("a"), True), "x": (IntType, True)}),
            RecordType({"type": (StringLiteralType("b"), True), "y": (StringType, True)}),
        ]
        assert _find_discriminant(groups) == "type"


class TestTopLevelLists:
    def test_single_list_of_records(self):
        named_types = run_pipeline(
            [[{"foo": "bar"}, {"foo": "baz"}]],
            Config(),
        )
        assert len(named_types) == 1
        assert named_types[0][0] is None
        root = named_types[0][1]
        assert root.kind == "list"
        assert root.element_type == RecordType({"foo": (StringType, True)})

    def test_multiple_lists_merged(self):
        named_types = run_pipeline(
            [
                [{"foo": "bar"}],
                [{"foo": "baz", "extra": 1}],
            ],
            Config(),
        )
        assert len(named_types) == 1
        root = named_types[0][1]
        assert root.kind == "list"
        assert root.element_type.kind == "record"
        assert "foo" in root.element_type.fields
        assert root.element_type.fields["extra"][0] is IntType

    def test_mixed_dicts_and_lists(self):
        named_types = run_pipeline(
            [
                {"foo": "bar"},
                [{"baz": 1}],
            ],
            Config(),
        )
        assert len(named_types) == 2
        dict_type = named_types[0][1]
        assert dict_type.kind == "record"
        assert dict_type.fields["foo"][0] is StringType
        list_type = named_types[1][1]
        assert list_type.kind == "list"
        assert list_type.element_type == RecordType({"baz": (IntType, True)})
