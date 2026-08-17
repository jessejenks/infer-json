from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Dict, List

from .config import Config
from .emit import extract_named_types
from .emit_go import type_to_go
from .emit_ts import type_to_ts
from .pipeline import run_pipeline
from .type_exprs import TypeExpr


def _collect_objects(parsed: object, objects: List[dict]) -> None:
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict):
                objects.append(item)
    elif isinstance(parsed, dict):
        objects.append(parsed)


COMMENT_PATTERN = re.compile(r"//")


def _count_trailing_backslashes(s: str, pos: int) -> int:
    count = 0
    pos -= 1
    while pos >= 0 and s[pos] == "\\":
        count += 1
        pos -= 1
    return count


def _remove_comments(line: str) -> str:
    in_string = False
    for i, c in enumerate(line):
        if c == '"' and _count_trailing_backslashes(line, i) % 2 == 0:
            in_string = not in_string
        elif not in_string and line[i : i + 2] == "//":
            return line[:i]
    return line


def _clean_line(line: str) -> str:
    # remove jsonc style comments
    if COMMENT_PATTERN.search(line):
        return _remove_comments(line.strip())
    return line.strip()


def main() -> None:
    parser = argparse.ArgumentParser(prog="infer_json", description="Infer types from JSON/JSONL files")
    Config.attach_arguments(parser)
    args = parser.parse_args(namespace=Config())

    if args.output == "go":
        args.max_literals = 0
        args.find_discriminant = False

    objects: List[dict] = []
    for filepath in args.files:
        is_jsonl = args.jsonl or filepath.endswith(".jsonl")
        with open(filepath, "r") as f:
            if is_jsonl:
                for line in f:
                    line = _clean_line(line)
                    if not line:
                        continue
                    _collect_objects(json.loads(line), objects)
            else:
                cleaned = "\n".join(cl for line in f if (cl := _clean_line(line)))
                _collect_objects(json.loads(cleaned), objects)

    print(f"// Inferred from {len(objects)} objects across {len(args.files)} file(s)", file=sys.stderr)

    named_types = run_pipeline(objects, args)

    extracted: Dict[str, TypeExpr] = {}
    variant_names: List[str] = []
    single_variant = len(named_types) == 1

    for name, simplified in named_types:
        extracted_top = extract_named_types(simplified, [name], extracted)
        match extracted_top.kind:
            case "ref":
                variant_names.append(extracted_top.name)
            case _:
                extracted[name] = extracted_top
                variant_names.append(name)

    if args.output == "go":
        for type_name, type_expr in extracted.items():
            print(f"type {type_name} {type_to_go(type_expr)}\n")
        if not single_variant:
            print(f"// Root is one of: {', '.join(variant_names)}")
    else:
        for type_name, type_expr in extracted.items():
            print(f"type {type_name} = {type_to_ts(type_expr)};\n")
        if not single_variant:
            print(f"type Root = {' | '.join(variant_names)};")


if __name__ == "__main__":
    main()
