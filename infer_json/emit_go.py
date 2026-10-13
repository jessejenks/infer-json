from __future__ import annotations

from .config import Config
from .emit import get_indent, make_name_unique, normalize_to_pascal
from .type_exprs import Null, RecordType, TypeExpr


def type_to_go(t: TypeExpr, config: Config) -> str:
    match t.kind:
        case "unknown" | "union":
            return "any"
        case "atom":
            if t.name == "null":
                return "any"
            if t.name == "boolean":
                return "bool"
            if t.name == "float":
                return "float64"
            return t.name
        case "string_literal":
            return "string"
        case "ref":
            return t.name
        case "map":
            return f"map[string]{type_to_go(t.value_type, config)}"
        case "list":
            return f"[]{type_to_go(t.element_type, config)}"
        case "record":
            return struct_to_go(t, config)
    raise ValueError(f"Unhandled type kind: {t.kind}")


def _is_valid_go_tag_name(key: str) -> bool:
    # based on isValidTag in Go's encoding/json
    if key:
        return all(c.isalpha() or c.isdecimal() or c in "!#$%&()*+-./:;<=>?@[]^_{|}~ " for c in key)
    return False


def struct_to_go(t: RecordType, config: Config, depth: int = 0) -> str:
    if not t.fields:
        return "struct{}"
    pad = get_indent(depth + 1, config)
    closing_pad = get_indent(depth, config)
    fields = sorted(t.fields.items()) if config.sort_keys else list(t.fields.items())
    lines: list[str] = []
    field_names = set[str]()
    for key, (field_type, required) in fields:
        field_name = normalize_to_pascal(key)
        if not field_name or not field_name[0].isupper():
            field_name = f"X{field_name}"
        field_name = make_name_unique(field_name, field_names)
        field_names.add(field_name)
        if not _is_valid_go_tag_name(key):
            raise ValueError(f"Key cannot be used as a Go struct tag: {key!r}")
        if not required:
            tag = f'`json:"{key},omitempty"`'
        else:
            tag = f'`json:"{key}"`'

        nillable = False
        if field_type.kind == "union":
            non_null = [m for m in field_type.members if m is not Null]
            if len(non_null) == 1:
                tp = non_null[0]
                go_type = type_to_go(tp, config)
                nillable = not required or (len(non_null) < len(field_type.members) and tp.kind not in ("map", "list"))
            else:
                go_type = "any"
        else:
            go_type = type_to_go(field_type, config)
            nillable = not required and field_type.kind not in ("map", "list")
        if nillable:
            go_type = f"*{go_type}"
        lines.append(f"{pad}{field_name} {go_type} {tag}")
    return "struct {\n" + "\n".join(lines) + f"\n{closing_pad}}}"
