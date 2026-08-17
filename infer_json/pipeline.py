import sys
from typing import Dict, List, Tuple

from .cluster import (
    cluster_objects,
    find_discriminant_key,
    merge_clusters_by_discriminant,
)
from .config import Config
from .emit import snake_to_pascal
from .merge import merge
from .simplify import simplify_unions, widen_literals
from .type_exprs import MapType, TypeExpr, UnionType


def run_pipeline(objects: List[Dict], config: Config):
    clusters, map_type = cluster_objects(objects, config)
    named_types: List[Tuple[str, TypeExpr]] = []
    discriminant: str | None = None
    if config.flatten_maps and map_type:
        merged_value = map_type.value_type
        for cluster in clusters:
            for field_type in cluster.merged_type.fields.values():
                merged_value = merge(merged_value, field_type)
        widened = widen_literals(MapType(merged_value), None, config)
        simplified = simplify_unions(widened, config.min_shared_keys)
        named_types.append(("Root", simplified))
    else:
        if config.find_discriminant:
            discriminant = find_discriminant_key(clusters)
            if discriminant:
                clusters = merge_clusters_by_discriminant(clusters, discriminant)
                print(f'// Discriminant key: "{discriminant}"', file=sys.stderr)
            else:
                print("// No single discriminant key found", file=sys.stderr)

        print(f"// {len(clusters)} variant(s)\n", file=sys.stderr)

        widened_types: List[TypeExpr] = []
        for cluster in clusters:
            widened = widen_literals(cluster.merged_type, discriminant, config)
            widened_types.append(widened)

        if not discriminant and len(widened_types) > 1:
            combined = simplify_unions(UnionType(widened_types), config.min_shared_keys)
            if combined.kind == "union":
                simplified_types = combined.members
            else:
                simplified_types = [combined]
        else:
            simplified_types = [simplify_unions(w, config.min_shared_keys) for w in widened_types]

        for i, t in enumerate(simplified_types):
            if discriminant:
                label = clusters[i].constant_string_keys.get(discriminant, f"Variant{i}")
                named_types.append((snake_to_pascal(label), t))
            else:
                named_types.append((f"Variant{i}", t))
        if map_type:
            widened_map = widen_literals(map_type, None, config)
            simplified_map = simplify_unions(widened_map, config.min_shared_keys)
            named_types.append((f"Variant{len(named_types)}", simplified_map))

        if len(named_types) == 1 and not discriminant:
            named_types[0] = ("Root", named_types[0][1])

    return named_types
