from __future__ import annotations

import argparse
import json
import re
import sys

from .config import Config
from .emit import prepare_variants
from .emit_go import type_to_go
from .emit_ts import type_to_ts
from .pipeline import run_pipeline

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

    items: list[object] = []
    for filepath in args.files:
        is_jsonl = args.jsonl or filepath.endswith(".jsonl")
        with open(filepath, "r") as f:
            if is_jsonl:
                for line in f:
                    line = _clean_line(line)
                    if not line:
                        continue
                    items.append(json.loads(line))
            else:
                cleaned = "\n".join(cl for line in f if (cl := _clean_line(line)))
                items.append(json.loads(cleaned))

    print(f"// Inferred from {len(items)} items across {len(args.files)} file(s)", file=sys.stderr)

    named_types = run_pipeline(items, args)
    extracted, variants = prepare_variants(named_types)

    if args.output == "go":
        emit = type_to_go
        for type_name, type_expr in extracted.items():
            print(f"type {type_name} {emit(type_expr)}\n")
        variant_names = [emit(v) for v in variants]
        if len(variants) > 1:
            print(f"// Root is one of: {', '.join(variant_names)}")
        elif variant_names[0] not in extracted:
            print(f"// Root is {variant_names[0]}")
    else:
        emit = type_to_ts
        for type_name, type_expr in extracted.items():
            print(f"type {type_name} = {emit(type_expr)};\n")
        variant_names = [emit(v) for v in variants]
        if len(variants) > 1:
            print(f"type Root = {' | '.join(variant_names)};")
        elif variant_names[0] not in extracted:
            print(f"type Root = {variant_names[0]};")


if __name__ == "__main__":
    main()
