from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Set

from .config import Config
from .infer import infer_type
from .merge import merge_records
from .type_exprs import RecordType


@dataclass
class Cluster:
    key_set: FrozenSet[str]
    merged_type: RecordType
    count: int = 0
    constant_string_keys: Dict[str, str] = field(default_factory=dict)


def cluster_objects(objects: List[dict], config: Config) -> List[Cluster]:
    keyset_to_cluster: Dict[FrozenSet[str], Cluster] = {}

    for obj in objects:
        ks = frozenset(obj.keys())
        inferred = infer_type(obj, config)
        assert inferred.kind == "record"

        if ks not in keyset_to_cluster:
            keyset_to_cluster[ks] = Cluster(
                key_set=ks,
                merged_type=inferred,
                count=1,
                constant_string_keys={k: v for k, v in obj.items() if isinstance(v, str)},
            )
        else:
            cluster = keyset_to_cluster[ks]
            cluster.merged_type = merge_records(cluster.merged_type, inferred)
            cluster.count += 1

            drop = []
            for k, v in cluster.constant_string_keys.items():
                if k not in obj or obj[k] != v:
                    drop.append(k)
            for k in drop:
                del cluster.constant_string_keys[k]

    return list(keyset_to_cluster.values())


def find_discriminant_key(clusters: List[Cluster]) -> str | None:
    if len(clusters) <= 1:
        return None

    all_constant_keys: Set[str] = set()
    for cluster in clusters:
        all_constant_keys.update(cluster.constant_string_keys.keys())

    best_key: str | None = None
    best_distinct_values = 0

    for key in all_constant_keys:
        values: List[str] = []
        present_count = 0
        for cluster in clusters:
            if key in cluster.constant_string_keys:
                present_count += 1
                values.append(cluster.constant_string_keys[key])

        if present_count < 2:
            continue

        distinct = len(set(values))
        if distinct > best_distinct_values:
            best_distinct_values = distinct
            best_key = key

    return best_key


def merge_clusters_by_discriminant(clusters: List[Cluster], discriminant: str) -> List[Cluster]:
    by_value: Dict[str, Cluster] = {}
    untagged: List[Cluster] = []

    for cluster in clusters:
        val = cluster.constant_string_keys.get(discriminant)
        if val is None:
            untagged.append(cluster)
            continue
        if val not in by_value:
            by_value[val] = Cluster(
                key_set=cluster.key_set,
                merged_type=cluster.merged_type,
                count=cluster.count,
                constant_string_keys={discriminant: val},
            )
        else:
            existing = by_value[val]
            existing.merged_type = merge_records(existing.merged_type, cluster.merged_type)
            existing.count += cluster.count
            existing.key_set = existing.key_set | cluster.key_set

    return list(by_value.values()) + untagged
