import argparse
from dataclasses import dataclass, field
from typing import List


@dataclass
class Config(argparse.Namespace):
    files: List[str] = field(default_factory=list)
    find_discriminant: bool = False
    min_shared_keys: int = 0
    max_literals: int = 0
    max_key_length: int = 25
    max_literal_length: int = 100
    flatten_maps: bool = False
    output: str = "ts"

    @staticmethod
    def attach_arguments(parser: argparse.ArgumentParser):
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
            help="Min shared keys to merge similar record types in unions (default 0)",
        )
        parser.add_argument(
            "-l",
            "--max-literals",
            type=int,
            help="Max distinct string literals before widening to string (default 0)",
        )
        parser.add_argument(
            "-K",
            "--max-key-length",
            type=int,
            help="Keys longer than this are treated as data; the dict becomes Record<string, T> (default 25, 0 to disable)",
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
            "-o",
            "--output",
            choices=["ts", "go"],
            help="Output language (default: ts)",
        )
