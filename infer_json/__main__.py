from __future__ import annotations

import argparse
import json
import sys
from typing import Dict, List

from .cluster import (
    cluster_objects,
    find_discriminant_key,
    merge_clusters_by_discriminant,
)
from .config import Config
from .emit import extract_named_types, snake_to_pascal, type_to_ts
from .simplify import simplify_unions, widen_literals
from .type_exprs import TypeExpr, UnionType


def _collect_objects(parsed: object, objects: List[dict]) -> None:
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict):
                objects.append(item)
    elif isinstance(parsed, dict):
        objects.append(parsed)


def main() -> None:
    parser = argparse.ArgumentParser(prog="infer_json", description="Infer TypeScript types from JSON/JSONL files")
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
    args = parser.parse_args(namespace=Config())

    objects: List[dict] = []
    for filepath in args.files:
        is_jsonl = args.jsonl or filepath.endswith(".jsonl")
        with open(filepath, "r") as f:
            if is_jsonl:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    _collect_objects(json.loads(line), objects)
            else:
                _collect_objects(json.load(f), objects)

    print(f"// Inferred from {len(objects)} objects across {len(args.files)} file(s)", file=sys.stderr)

    clusters = cluster_objects(objects, args)
    discriminant: str | None = None
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

    extracted: Dict[str, TypeExpr] = {}
    variant_names: List[str] = []
    single_variant = len(simplified_types) == 1

    for i, simplified in enumerate(simplified_types):
        if single_variant and not discriminant:
            name = "Root"
        elif discriminant:
            label = clusters[i].constant_string_keys.get(discriminant, f"Variant{i}")
            name = snake_to_pascal(label)
        else:
            name = f"Variant{i}"
        extracted_top = extract_named_types(simplified, [name], extracted)
        assert extracted_top.kind == "ref"
        variant_names.append(extracted_top.name)

    for type_name, type_expr in extracted.items():
        print(f"type {type_name} = {type_to_ts(type_expr)};\n")

    if not single_variant:
        print(f"type Root = {' | '.join(variant_names)};")


if __name__ == "__main__":
    main()
