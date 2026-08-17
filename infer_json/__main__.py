from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Dict, List, Tuple

from .cluster import (
    cluster_objects,
    find_discriminant_key,
    merge_clusters_by_discriminant,
)
from .config import Config
from .emit import extract_named_types, snake_to_pascal
from .emit_go import type_to_go
from .emit_ts import type_to_ts
from .merge import merge
from .simplify import simplify_unions, widen_literals
from .type_exprs import MapType, TypeExpr, UnionType


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
    parser.add_argument("files", nargs="+", help="JSON or JSONL files to process")
    parser.add_argument(
        "--jsonl",
        action="store_true",
        help="Force all files to be read as JSONL (default: only files with .jsonl extension)",
    )
    parser.add_argument(
        "-d",
        "--find-discriminant",
        action="store_true",
        help="Search for a discriminant key to split variants on",
    )
    parser.add_argument(
        "-k",
        "--min-shared-keys",
        type=int,
        default=0,
        help="Min shared keys to merge similar record types in unions (default 0)",
    )
    parser.add_argument(
        "-l",
        "--max-literals",
        type=int,
        default=0,
        help="Max distinct string literals before widening to string (default 0)",
    )
    parser.add_argument(
        "-K",
        "--max-key-length",
        type=int,
        default=25,
        help="Keys longer than this are treated as data; the dict becomes Record<string, T> (default 25, 0 to disable)",
    )
    parser.add_argument(
        "-L",
        "--max-literal-length",
        type=int,
        default=100,
        help="String literals longer than this are widened to string (default 100, 0 to disable)",
    )
    parser.add_argument(
        "-F",
        "--flatten-maps",
        action="store_true",
        help="A top-level map causes all top-level objects to become a map (default false)",
    )
    parser.add_argument(
        "-o",
        "--output",
        choices=["ts", "go"],
        default="ts",
        help="Output language (default: ts)",
    )
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

    clusters, map_type = cluster_objects(objects, args)
    named_types: List[Tuple[str, TypeExpr]] = []
    discriminant: str | None = None
    if args.flatten_maps and map_type:
        merged_value = map_type.value_type
        for cluster in clusters:
            for field_type in cluster.merged_type.fields.values():
                merged_value = merge(merged_value, field_type)
        widened = widen_literals(MapType(merged_value), None, args)
        simplified = simplify_unions(widened, args.min_shared_keys)
        named_types.append(("Root", simplified))
    else:
        if args.find_discriminant:
            discriminant = find_discriminant_key(clusters)
            if discriminant:
                clusters = merge_clusters_by_discriminant(clusters, discriminant)
                print(f'// Discriminant key: "{discriminant}"', file=sys.stderr)
            else:
                print("// No single discriminant key found", file=sys.stderr)

        print(f"// {len(clusters)} variant(s)\n", file=sys.stderr)

        widened_types: List[TypeExpr] = []
        for cluster in clusters:
            widened = widen_literals(cluster.merged_type, discriminant, args)
            widened_types.append(widened)

        if not discriminant and len(widened_types) > 1:
            combined = simplify_unions(UnionType(widened_types), args.min_shared_keys)
            if combined.kind == "union":
                simplified_types = combined.members
            else:
                simplified_types = [combined]
        else:
            simplified_types = [simplify_unions(w, args.min_shared_keys) for w in widened_types]

        for i, t in enumerate(simplified_types):
            if discriminant:
                label = clusters[i].constant_string_keys.get(discriminant, f"Variant{i}")
                named_types.append((snake_to_pascal(label), t))
            else:
                named_types.append((f"Variant{i}", t))
        if map_type:
            widened_map = widen_literals(map_type, None, args)
            simplified_map = simplify_unions(widened_map, args.min_shared_keys)
            named_types.append((f"Variant{len(named_types)}", simplified_map))

        if len(named_types) == 1 and not discriminant:
            named_types[0] = ("Root", named_types[0][1])

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
