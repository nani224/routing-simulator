"""Unit tests for topology models, generators, presets, and validation."""

import tempfile
from pathlib import Path

import networkx as nx
import pytest
from routelab.topology.generators import (
    generate_grid,
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


def test_topology_model_and_networkx() -> None:
    topo = Topology(name="TestNet")
    topo.add_node(TopologyNode("A", 10.0, 20.0, as_number=100))
    topo.add_node(TopologyNode("B", 30.0, 40.0, as_number=200))
    topo.add_link(TopologyLink("A", "B", cost=3.5, latency_ms=12.0))

    g = topo.to_networkx()
    assert g.number_of_nodes() == 2
    assert g.number_of_edges() == 1
    assert g["A"]["B"]["weight"] == 3.5

    reconstructed = Topology.from_networkx(g, name="Restored")
    assert len(reconstructed.nodes) == 2
    assert len(reconstructed.links) == 1


def test_topology_generators_connectivity() -> None:
    ring = generate_ring(6)
    assert len(ring.nodes) == 6
    assert len(ring.links) == 6
    assert nx.is_connected(ring.to_networkx())

    grid = generate_grid(3, 3)
    assert len(grid.nodes) == 9
    assert len(grid.links) == 12
    assert nx.is_connected(grid.to_networkx())

    tree = generate_tree(depth=3, branching_factor=2)
    assert len(tree.nodes) == 7
    assert len(tree.links) == 6
    assert nx.is_connected(tree.to_networkx())

    scale_free = generate_scale_free(15, m=2, seed=42)
    assert len(scale_free.nodes) == 15
    assert nx.is_connected(scale_free.to_networkx())


def test_course_presets() -> None:
    p6 = preset_6_node()
    assert len(p6.nodes) == 6
    assert nx.is_connected(p6.to_networkx())

    p8 = preset_8_node()
    assert len(p8.nodes) == 8
    assert nx.is_connected(p8.to_networkx())

    p10 = preset_10_node()
    assert len(p10.nodes) == 10
    assert nx.is_connected(p10.to_networkx())

    c2inf = preset_count_to_infinity()
    assert len(c2inf.nodes) == 4
    assert len(c2inf.links) == 3

    bgp = preset_bgp_tier1()
    assert len(bgp.nodes) == 4
    assert len(bgp.links) == 5


def test_topology_validation_errors() -> None:
    # 1. Non-existent target node
    topo_bad = Topology(name="Bad")
    topo_bad.add_node(TopologyNode("A"))
    topo_bad.add_link(TopologyLink("A", "B", cost=1.0))
    with pytest.raises(TopologyValidationError, match="does not exist in nodes"):
        TopologyLoader.validate(topo_bad)

    # 2. Self loop
    topo_self = Topology(name="Self")
    topo_self.add_node(TopologyNode("A"))
    topo_self.add_link(TopologyLink("A", "A", cost=1.0))
    with pytest.raises(TopologyValidationError, match="Self-loop detected"):
        TopologyLoader.validate(topo_self)


def test_topology_json_and_graphml_io() -> None:
    topo = preset_6_node()
    with tempfile.TemporaryDirectory() as tmp_dir:
        json_path = Path(tmp_dir) / "topo.json"
        graphml_path = Path(tmp_dir) / "topo.graphml"

        TopologyLoader.save_json(topo, json_path)
        loaded_json = TopologyLoader.load_json(json_path)
        assert len(loaded_json.nodes) == 6

        TopologyLoader.save_graphml(topo, graphml_path)
        loaded_graphml = TopologyLoader.load_graphml(graphml_path)
        assert len(loaded_graphml.nodes) == 6
