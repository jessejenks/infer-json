import argparse
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Config(argparse.Namespace):
    files: list[str] = field(default_factory=list)
    find_discriminant: bool = False
    min_shared_keys: int = 0
    max_literals: int = 0
    max_depth: int = 0
    max_key_length: int = 25
    max_literal_length: int = 100
    flatten_maps: bool = False
    root: str = "Root"
    prefix: str = ""
    variant: str = "Variant"
    sort_keys: bool = False
    readonly: bool = False
    use_spaces: bool = False
    tab_width: int = 2
    output: Literal["ts", "go"] = "ts"

    @staticmethod
    def attach_arguments(parser: argparse.ArgumentParser):
        parser.add_argument(
            "files", nargs="*", help="JSON or JSONL files to process (reads stdin if none given, or use - for stdin)"
        )
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
            help="Minimum shared keys required to merge similar record types in unions (default 0)",
        )
        parser.add_argument(
            "-l",
            "--max-literals",
            type=int,
            help="Max distinct string literals before widening to string (default 0)",
        )
        parser.add_argument(
            "-D",
            "--max-depth",
            type=int,
            help="Maximum depth of type before collapsing to unknown/any (default 0, meaning no maximum)",
        )
        parser.add_argument(
            "-K",
            "--max-key-length",
            type=int,
            help="Keys longer than this turn the object into a map type (default 25, 0 to disable)",
        )
        parser.add_argument(
            "-L",
            "--max-literal-length",
            type=int,
            help="String literals longer than this are widened to string (default 100, 0 to disable)",
        )
        parser.add_argument(
            "-F",
            "--flatten-maps",
            action="store_true",
            help="A top-level map causes all top-level objects to become a map (default false)",
        )
        parser.add_argument(
            "-s",
            "--sort-keys",
            action="store_true",
            help="Sort object keys alphabetically in output",
        )
        parser.add_argument(
            "--readonly",
            action="store_true",
            help="Emit readonly fields in TypeScript output (ignored for Go)",
        )
        parser.add_argument(
            "--use-spaces",
            action="store_true",
            help="Use spaces for indentation instead of tabs",
        )
        parser.add_argument(
            "--tab-width",
            type=int,
            help="Number of spaces per indentation level (default 2, only used with --use-spaces)",
        )
        parser.add_argument(
            "-r",
            "--root",
            help="Root type name (default 'Root')",
        )
        parser.add_argument(
            "-p",
            "--prefix",
            help="Global prefix for type names (default '')",
        )
        parser.add_argument(
            "--variant",
            help="Name prefix used for anonymous types (default 'Variant')",
        )
        parser.add_argument(
            "-o",
            "--output",
            choices=["ts", "go"],
            help="Output language (default: ts)",
        )
