"""Topology abstractions, graph loaders, and network presets."""

from routelab.topology.generators import (
    generate_grid,
    generate_random_geometric,
    generate_ring,
    generate_scale_free,
    generate_tree,
    preset_6_node,
    preset_8_node,
    preset_10_node,
    preset_bgp_tier1,
    preset_count_to_infinity,
)
from routelab.topology.loader import TopologyLoader, TopologyValidationError
from routelab.topology.model import Topology, TopologyLink, TopologyNode

__all__ = [
    "Topology",
    "TopologyNode",
    "TopologyLink",
    "TopologyLoader",
    "TopologyValidationError",
    "generate_ring",
    "generate_grid",
    "generate_tree",
    "generate_random_geometric",
    "generate_scale_free",
    "preset_6_node",
    "preset_8_node",
    "preset_10_node",
    "preset_count_to_infinity",
    "preset_bgp_tier1",
]
