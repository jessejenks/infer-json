from __future__ import annotations

from .config import Config
from .emit import snake_to_pascal
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


def struct_to_go(t: RecordType, config: Config, indent: int = 0) -> str:
    if not t.fields:
        return "struct{}"
    unit = " " * config.tab_width if config.use_spaces else "\t"
    pad = unit * (indent + 1)
    closing_pad = unit * indent
    fields = sorted(t.fields.items()) if config.sort_keys else list(t.fields.items())
    lines: list[str] = []
    for key, (field_type, required) in fields:
        field_name = snake_to_pascal(key)
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
