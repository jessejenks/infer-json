import argparse
from typing import List


class Config(argparse.Namespace):
    files: List[str] = []
    find_discriminant: bool = False
    min_shared_keys: int = 0
    max_literals: int = 0
    max_key_length: int = 25
    max_literal_length: int = 100
    output: str = "ts"
