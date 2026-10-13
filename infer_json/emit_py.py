from __future__ import annotations

import json

from .config import Config
from .emit import get_indent
from .type_exprs import Null, RecordType, TypeExpr


def type_to_py(t: TypeExpr, config: Config, depth: int = 0, name: str = "") -> str:
    prefix = ""
    if depth == 0 and name:
        prefix = f"type {name} = "
    match t.kind:
        case "unknown":
            return f"{prefix}Any"
        case "atom":
            if t.name == "null":
                return f"{prefix}None"
            if t.name == "boolean":
                return f"{prefix}bool"
            if t.name == "string":
                return f"{prefix}str"
            return f"{prefix}{t.name}"
        case "string_literal":
            return f"{prefix}Literal[{json.dumps(t.value, ensure_ascii=False)}]"
        case "ref":
            # aliasing?
            return f"{prefix}{t.name}"
        case "map":
            return f"{prefix}dict[str, {type_to_py(t.value_type, config, depth+1)}]"
        case "list":
            return f"{prefix}list[{type_to_py(t.element_type, config, depth+1)}]"
        case "union":
            parts = []
            nullable = False
            for m in t.members:
                if m is Null:
                    nullable = True
                    continue
                parts.append(type_to_py(m, config, depth + 1))
            if nullable:
                parts.append("None")
            return prefix + " | ".join(parts)
        case "record":
            return record_to_py(t, config, depth, name)
    raise ValueError(f"Unhandled type kind: {t.kind}")


def record_to_py(t: RecordType, config: Config, depth: int = 0, name: str = "") -> str:
    if not t.fields:
        return f"{name} = TypedDict({json.dumps(name, ensure_ascii=False)}, {{}})"
    pad = get_indent(depth + 1, config)
    closing_pad = get_indent(depth, config)
    fields = sorted(t.fields.items()) if config.sort_keys else list(t.fields.items())
    lines = []
    for key, (field_type, required) in fields:
        key = json.dumps(key, ensure_ascii=False)
        s = type_to_py(field_type, config, depth + 1)
        if required and config.readonly:
            lines.append(f"{pad}{key}: Readonly[{s}],")
        elif required:
            lines.append(f"{pad}{key}: {s},")
        elif config.readonly:
            lines.append(f"{pad}{key}: Readonly[NotRequired[{s}]],")
        else:
            lines.append(f"{pad}{key}: NotRequired[{s}],")
    return f"{name} = TypedDict({json.dumps(name, ensure_ascii=False)}, {{\n" + "\n".join(lines) + f"\n{closing_pad}}})"
