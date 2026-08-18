from infer_json.type_exprs import (
    BoolType,
    FloatType,
    IntType,
    ListType,
    MapType,
    RecordType,
    StringLiteralType,
    StringType,
    UnionType,
    Unknown,
    is_subtype,
    merge,
)


class TestMerge:
    def test_merge_with_unknown_is_id(self):
        assert merge(Unknown, Unknown) is Unknown
        assert merge(Unknown, StringType) is StringType
        assert merge(FloatType, Unknown) is FloatType

    def test_same_atom_merges(self):
        assert merge(StringType, StringType) is StringType

    def test_different_atoms_become_union(self):
        result = merge(StringType, IntType)
        assert result.kind == "union"
        assert len(result.members) == 2

    def test_same_literal_merges(self):
        assert merge(StringLiteralType("foo"), StringLiteralType("foo")) == StringLiteralType("foo")

    def test_different_literals_create_union(self):
        result = merge(StringLiteralType("a"), StringLiteralType("b"))
        assert result.kind == "union"
        assert len(result.members) == 2
        assert result.members[0] == StringLiteralType("a")
        assert result.members[1] == StringLiteralType("b")

    def test_literal_and_string_widen(self):
        assert merge(StringLiteralType("x"), StringType) is StringType
        assert merge(StringType, StringLiteralType("x")) is StringType

    def test_empty_record_merge(self):
        result = merge(RecordType({}), RecordType({"k": (StringType, True)}))
        assert result.kind == "record"
        assert "k" in result.fields
        assert result.fields["k"][1] is False

    def test_record_monadic_merge(self):
        a = RecordType({"k": (StringType, True)})
        b = RecordType({"k": (IntType, True)})
        result = merge(a, b)
        assert result.kind == "record"
        assert "k" in result.fields
        assert result.fields["k"][1] is True
        assert result.fields["k"][0].kind == "union"

    def test_record_merge_shared_keys(self):
        a = RecordType({"x": (StringType, True), "y": (IntType, True)})
        b = RecordType({"x": (StringType, True), "z": (BoolType, True)})
        result = merge(a, b)
        assert result.kind == "record"
        assert "x" in result.fields
        assert "y" in result.fields
        assert "z" in result.fields
        assert result.fields["y"][1] is False
        assert result.fields["z"][1] is False

    def test_flatten_unions(self):
        result = merge(
            UnionType([StringType, UnionType([StringType, StringLiteralType("a")])]), UnionType([UnionType([IntType])])
        )
        assert result == UnionType([StringType, IntType])


class TestUnionEquality:
    def test_order_independent(self):
        assert UnionType([StringType, IntType]) == UnionType([IntType, StringType])
        assert UnionType([StringType, IntType, BoolType]) == UnionType([BoolType, StringType, IntType])
        assert UnionType([StringType, IntType]) != UnionType([StringType, BoolType])
        assert UnionType([StringType, IntType]) != UnionType([StringType, IntType, BoolType])


class TestSubtype:
    def test_unknown_is_bottom(self):
        assert is_subtype(Unknown, Unknown)
        assert is_subtype(Unknown, StringType)
        assert is_subtype(FloatType, Unknown) is False

    def test_atom_reflexive(self):
        assert is_subtype(IntType, IntType)
        assert is_subtype(BoolType, BoolType)
        assert is_subtype(StringType, StringType)

    def test_int_float_subtype(self):
        assert is_subtype(IntType, StringType) is False
        assert is_subtype(IntType, FloatType)

    def test_literal_reflexive(self):
        assert is_subtype(StringLiteralType("a"), StringLiteralType("a"))
        assert is_subtype(StringLiteralType("a"), StringLiteralType("b")) is False

    def test_literal_string_subtype(self):
        assert is_subtype(StringLiteralType("a"), StringType)

    def test_list_monotone(self):
        assert is_subtype(ListType(IntType), ListType(StringType)) is False
        assert is_subtype(ListType(IntType), ListType(IntType))
        assert is_subtype(ListType(IntType), ListType(FloatType))

    def test_map_monotone(self):
        assert is_subtype(MapType(IntType), MapType(StringType)) is False
        assert is_subtype(MapType(IntType), MapType(IntType))
        assert is_subtype(MapType(IntType), MapType(FloatType))

    def test_empty_record(self):
        assert is_subtype(RecordType({}), RecordType({"k": (StringType, True)})) is False
        assert is_subtype(RecordType({}), RecordType({"k": (StringType, False)}))

    def test_pointwise_record(self):
        assert is_subtype(RecordType({"k": (IntType, True)}), RecordType({"k": (FloatType, True)}))
        assert is_subtype(RecordType({"k": (IntType, True)}), RecordType({"k": (FloatType, False)}))
        assert is_subtype(RecordType({"k": (IntType, False)}), RecordType({"k": (FloatType, False)}))
        assert is_subtype(RecordType({"k": (IntType, False)}), RecordType({"k": (FloatType, True)})) is False

    def test_multi_key_record(self):
        assert is_subtype(RecordType({"k1": (IntType, True)}), RecordType({"k2": (IntType, True)})) is False
        assert (
            is_subtype(RecordType({"k1": (IntType, True)}), RecordType({"k1": (IntType, True), "k2": (IntType, True)}))
            is False
        )
        assert is_subtype(
            RecordType({"k1": (IntType, True)}), RecordType({"k1": (IntType, True), "k2": (IntType, False)})
        )

    def test_unions(self):
        assert is_subtype(UnionType([StringLiteralType("a"), StringLiteralType("b")]), StringType)
        assert is_subtype(StringLiteralType("a"), UnionType([IntType, StringType]))
        assert is_subtype(UnionType([StringLiteralType("a"), StringLiteralType("b")]), UnionType([IntType, StringType]))
