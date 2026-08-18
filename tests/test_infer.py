from infer_json.config import Config
from infer_json.infer import infer_type
from infer_json.type_exprs import (
    BoolType,
    FloatType,
    IntType,
    Null,
    StringLiteralType,
    Unknown,
)


class TestInferType:
    def test_primitives(self):
        config = Config()
        assert infer_type(None, config) is Null
        assert infer_type(True, config) is BoolType
        assert infer_type(42, config) is IntType
        assert infer_type(3.14, config) is FloatType
        assert infer_type("hi", config) == StringLiteralType("hi")

    def test_empty_list(self):
        result = infer_type([], Config())
        assert result.kind == "list"
        assert result.element_type is Unknown

    def test_dict_becomes_record(self):
        result = infer_type({"a": 1, "b": "x"}, Config())
        assert result.kind == "record"
        assert result.fields["a"][0] is IntType
        assert result.fields["a"][1] is True
        assert result.fields["b"][0] == StringLiteralType("x")
        assert result.fields["b"][1] is True

    def test_long_keys_become_map(self):
        result = infer_type({"a_very_long_key_name_that_exceeds": 1}, Config(max_key_length=10))
        assert result.kind == "map"

    def test_data_key_detection_disabled(self):
        result = infer_type({"a_very_long_key_name_that_exceeds": 1}, Config(max_key_length=0))
        assert result.kind == "record"
