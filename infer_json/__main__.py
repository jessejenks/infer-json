from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
import sys

from .config import Config
from .emit import needs_root_definition, prepare_variants
from .emit_go import type_to_go
from .emit_py import type_to_py
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
    parser = argparse.ArgumentParser(prog="infer-json", description="Infer types from JSON/JSONL files")
    parser.add_argument("--version", action="version", version=f"%(prog)s {importlib.metadata.version('infer-json')}")
    Config.attach_arguments(parser)
    args = parser.parse_args(namespace=Config())

    if args.output == "go":
        args.max_literals = 0

    if not args.files:
        args.files = ["-"]

    items: list[object] = []
    read_any_successfully = False
    for filepath in args.files:
        is_stdin = filepath == "-"
        is_jsonl = args.jsonl or (not is_stdin and filepath.endswith(".jsonl"))
        f = sys.stdin
        try:
            if not is_stdin:
                f = open(filepath, "r")
            if is_jsonl:
                for line in f:
                    line = _clean_line(line)
                    if not line:
                        continue
                    items.append(json.loads(line))
            else:
                cleaned = "\n".join(cl for line in f if (cl := _clean_line(line)))
                items.append(json.loads(cleaned))
            read_any_successfully = True
        except OSError as e:
            print("Failed to read file", file=sys.stderr)
            print(e, file=sys.stderr)
            pass
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON document: {filepath}", file=sys.stderr)
            print(f"{e.msg}: line {e.lineno} column {e.colno} (char {e.pos})", file=sys.stderr)
        finally:
            if not is_stdin:
                f.close()

    if not read_any_successfully:
        return

    print(f"// Inferred from {len(items)} items across {len(args.files)} file(s)", file=sys.stderr)

    named_types = run_pipeline(items, args)
    extracted, variants = prepare_variants(named_types, args)

    match args.output:
        case "typescript" | "ts":
            for type_name, type_expr in extracted.items():
                print(f"type {type_name} = {type_to_ts(type_expr, args)};\n")
            variant_names = [type_to_ts(v, args) for v in variants]
            if not variants:
                return
            if needs_root_definition(named_types):
                print(f"type {args.prefix}{args.root} = {' | '.join(variant_names)};")
        case "go":
            for type_name, type_expr in extracted.items():
                print(f"type {type_name} {type_to_go(type_expr, args)}\n")
            variant_names = [type_to_go(v, args) for v in variants]
            if not variants:
                return
            if needs_root_definition(named_types):
                if len(variants) > 1:
                    print(f"// {args.prefix}{args.root} is one of: {', '.join(variant_names)}")
                else:
                    print(f"// {args.prefix}{args.root} is: {', '.join(variant_names)}")

        case "python" | "py":
            for type_name, type_expr in extracted.items():
                print(type_to_py(type_expr, args, name=type_name))
                print()
            if not variants:
                return
            if needs_root_definition(named_types):
                if len(variants) > 1:
                    print(f"type {args.prefix}{args.root} = {' | '.join(type_to_py(v, args) for v in variants)}")
                    return
                print(type_to_py(variants[0], args, name=f"{args.prefix}{args.root}"))


if __name__ == "__main__":
    main()
