"""Synthetic topology generators and standard course scenario presets.

Generates ring, 2D grid, tree, random geometric, scale-free networks,
and mandatory 6, 8, and 10-node evaluation topologies.
"""

from __future__ import annotations

import math
import random

import networkx as nx

from routelab.topology.model import Topology, TopologyLink, TopologyNode


def generate_ring(num_nodes: int = 6, default_cost: float = 1.0) -> Topology:
    """Generate a circular ring topology with cartographer drafting positions."""
    topo = Topology(name=f"Ring-{num_nodes}")
    cx, cy, r = 400.0, 300.0, 180.0
    for i in range(num_nodes):
        node_id = f"R{i + 1}"
        theta = (2 * math.pi * i) / num_nodes
        x = cx + r * math.cos(theta)
        y = cy + r * math.sin(theta)
        topo.add_node(
            TopologyNode(id=node_id, x=round(x, 1), y=round(y, 1), as_number=65000 + i + 1)
        )

    for i in range(num_nodes):
        src = f"R{i + 1}"
        dst = f"R{((i + 1) % num_nodes) + 1}"
        topo.add_link(TopologyLink(source=src, target=dst, cost=default_cost, latency_ms=10.0))
    return topo


def generate_grid(rows: int = 3, cols: int = 3, default_cost: float = 1.0) -> Topology:
    """Generate a 2D mesh grid topology."""
    topo = Topology(name=f"Grid-{rows}x{cols}")
    spacing_x = 150.0
    spacing_y = 120.0
    offset_x = 200.0
    offset_y = 150.0

    for r in range(rows):
        for c in range(cols):
            node_id = f"R{r + 1}_{c + 1}"
            x = offset_x + c * spacing_x
            y = offset_y + r * spacing_y
            topo.add_node(TopologyNode(id=node_id, x=round(x, 1), y=round(y, 1)))

    for r in range(rows):
        for c in range(cols):
            curr = f"R{r + 1}_{c + 1}"
            if c + 1 < cols:
                right = f"R{r + 1}_{c + 2}"
                topo.add_link(TopologyLink(source=curr, target=right, cost=default_cost))
            if r + 1 < rows:
                down = f"R{r + 2}_{c + 1}"
                topo.add_link(TopologyLink(source=curr, target=down, cost=default_cost))
    return topo


def generate_tree(depth: int = 3, branching_factor: int = 2, default_cost: float = 1.0) -> Topology:
    """Generate a balanced hierarchical tree topology."""
    topo = Topology(name=f"Tree-d{depth}-b{branching_factor}")
    counter = 1

    def add_subtree(
        parent_id: str | None, current_depth: int, x: float, y: float, spread: float
    ) -> None:
        nonlocal counter
        node_id = f"R{counter}"
        counter += 1
        topo.add_node(TopologyNode(id=node_id, x=round(x, 1), y=round(y, 1)))
        if parent_id is not None:
            topo.add_link(TopologyLink(source=parent_id, target=node_id, cost=default_cost))

        if current_depth < depth:
            step = spread / max(1, branching_factor)
            start_x = x - (spread / 2.0) + (step / 2.0)
            for i in range(branching_factor):
                child_x = start_x + i * step
                child_y = y + 100.0
                add_subtree(node_id, current_depth + 1, child_x, child_y, spread * 0.55)

    add_subtree(None, 1, 400.0, 100.0, 500.0)
    return topo


def generate_random_geometric(
    num_nodes: int = 20, radius: float = 0.35, seed: int = 42
) -> Topology:
    """Generate a connected Random Geometric Graph (RGG)."""
    rng = random.Random(seed)
    max_tries = 20
    for _ in range(max_tries):
        g = nx.random_geometric_graph(num_nodes, radius, seed=rng.randint(1, 100000))
        if nx.is_connected(g):
            topo = Topology(name=f"RGG-{num_nodes}")
            for n in g.nodes():
                pos = g.nodes[n]["pos"]
                node_id = f"R{n + 1}"
                topo.add_node(
                    TopologyNode(
                        id=node_id,
                        x=round(pos[0] * 700 + 50, 1),
                        y=round(pos[1] * 500 + 50, 1),
                    )
                )
            for u, v in g.edges():
                pos_u = g.nodes[u]["pos"]
                pos_v = g.nodes[v]["pos"]
                dist = math.dist(pos_u, pos_v)
                cost = max(1.0, round(dist * 10, 1))
                topo.add_link(
                    TopologyLink(
                        source=f"R{u + 1}",
                        target=f"R{v + 1}",
                        cost=cost,
                        latency_ms=round(dist * 50, 1),
                    )
                )
            return topo

    # Fallback to connected scale-free if RGG failed connectivity
    return generate_scale_free(num_nodes, m=2, seed=seed)


def generate_scale_free(num_nodes: int = 20, m: int = 2, seed: int = 42) -> Topology:
    """Generate Barabási–Albert scale-free power-law topology."""
    g = nx.barabasi_albert_graph(num_nodes, m, seed=seed)
    try:
        pos = nx.spring_layout(g, seed=seed)
    except Exception:  # noqa: BLE001
        pos = {
            n: (
                math.cos((2 * math.pi * n) / max(1, num_nodes)),
                math.sin((2 * math.pi * n) / max(1, num_nodes)),
            )
            for n in g.nodes()
        }
    topo = Topology(name=f"ScaleFree-{num_nodes}")
    for n in g.nodes():
        coords = pos[n]
        node_id = f"R{n + 1}"
        topo.add_node(
            TopologyNode(
                id=node_id,
                x=round(coords[0] * 320 + 400, 1),
                y=round(coords[1] * 240 + 300, 1),
            )
        )
    for u, v in g.edges():
        topo.add_link(
            TopologyLink(
                source=f"R{u + 1}",
                target=f"R{v + 1}",
                cost=1.0,
                latency_ms=10.0,
            )
        )
    return topo


# Mandatory Course Presets (Team 20)
def preset_6_node() -> Topology:
    """Course-mandated 6-node mesh benchmark topology."""
    topo = Topology(name="Course-6-Node-Benchmark")
    positions = {
        "A": (150.0, 200.0),
        "B": (350.0, 120.0),
        "C": (550.0, 200.0),
        "D": (550.0, 400.0),
        "E": (350.0, 480.0),
        "F": (150.0, 400.0),
    }
    for node_id, (x, y) in positions.items():
        topo.add_node(TopologyNode(id=node_id, x=x, y=y, as_number=65001))

    links = [
        ("A", "B", 2.0, 5.0),
        ("A", "F", 4.0, 10.0),
        ("B", "C", 3.0, 8.0),
        ("B", "E", 7.0, 15.0),
        ("C", "D", 1.0, 3.0),
        ("D", "E", 5.0, 12.0),
        ("E", "F", 2.0, 6.0),
        ("B", "F", 6.0, 14.0),
    ]
    for u, v, cost, lat in links:
        topo.add_link(TopologyLink(source=u, target=v, cost=cost, latency_ms=lat))
    return topo


def preset_8_node() -> Topology:
    """Course-mandated 8-node augmented mesh benchmark topology."""
    topo = Topology(name="Course-8-Node-Benchmark")
    positions = {
        "R1": (120.0, 180.0),
        "R2": (300.0, 120.0),
        "R3": (500.0, 120.0),
        "R4": (680.0, 180.0),
        "R5": (680.0, 400.0),
        "R6": (500.0, 460.0),
        "R7": (300.0, 460.0),
        "R8": (120.0, 400.0),
    }
    for node_id, (x, y) in positions.items():
        topo.add_node(TopologyNode(id=node_id, x=x, y=y, as_number=65001))

    links = [
        ("R1", "R2", 2.0),
        ("R2", "R3", 4.0),
        ("R3", "R4", 3.0),
        ("R4", "R5", 2.0),
        ("R5", "R6", 5.0),
        ("R6", "R7", 1.0),
        ("R7", "R8", 3.0),
        ("R8", "R1", 4.0),
        ("R2", "R7", 6.0),
        ("R3", "R6", 2.0),
        ("R2", "R6", 7.0),
    ]
    for u, v, cost in links:
        topo.add_link(TopologyLink(source=u, target=v, cost=cost, latency_ms=10.0))
    return topo


def preset_10_node() -> Topology:
    """Course-mandated 10-node WAN backbone benchmark topology."""
    topo = Topology(name="Course-10-Node-Benchmark")
    positions = {
        "N1": (100.0, 200.0),
        "N2": (250.0, 120.0),
        "N3": (450.0, 100.0),
        "N4": (650.0, 120.0),
        "N5": (800.0, 200.0),
        "N6": (800.0, 380.0),
        "N7": (650.0, 460.0),
        "N8": (450.0, 480.0),
        "N9": (250.0, 460.0),
        "N10": (100.0, 380.0),
    }
    for node_id, (x, y) in positions.items():
        topo.add_node(TopologyNode(id=node_id, x=x, y=y, as_number=65001))

    links = [
        ("N1", "N2", 3.0),
        ("N2", "N3", 4.0),
        ("N3", "N4", 2.0),
        ("N4", "N5", 5.0),
        ("N5", "N6", 2.0),
        ("N6", "N7", 4.0),
        ("N7", "N8", 3.0),
        ("N8", "N9", 2.0),
        ("N9", "N10", 4.0),
        ("N10", "N11" if False else "N1", 3.0),
        ("N2", "N9", 6.0),
        ("N3", "N8", 5.0),
        ("N4", "N7", 4.0),
        ("N2", "N8", 8.0),
    ]
    for u, v, cost in links:
        topo.add_link(TopologyLink(source=u, target=v, cost=cost, latency_ms=10.0))
    return topo


def preset_count_to_infinity() -> Topology:
    """Linear chain designed to reliably reproduce count-to-infinity upon A-B link severance."""
    topo = Topology(name="Count-to-Infinity-Linear")
    nodes = ["A", "B", "C", "D"]
    for i, n in enumerate(nodes):
        topo.add_node(TopologyNode(id=n, x=150.0 + i * 180.0, y=280.0))
    topo.add_link(TopologyLink(source="A", target="B", cost=1.0, latency_ms=10.0))
    topo.add_link(TopologyLink(source="B", target="C", cost=1.0, latency_ms=10.0))
    topo.add_link(TopologyLink(source="C", target="D", cost=1.0, latency_ms=10.0))
    return topo


def preset_bgp_tier1() -> Topology:
    """Multi-AS BGP topology with AS_PATH loop scenario and customer-provider policies."""
    topo = Topology(name="BGP-Multi-AS-Interdomain")
    as_map = {
        "AS100_R1": (200.0, 180.0, 100),
        "AS200_R1": (450.0, 120.0, 200),
        "AS300_R1": (700.0, 180.0, 300),
        "AS400_R1": (450.0, 380.0, 400),
    }
    for node_id, (x, y, asn) in as_map.items():
        topo.add_node(TopologyNode(id=node_id, x=x, y=y, as_number=asn))

    topo.add_link(TopologyLink(source="AS100_R1", target="AS200_R1", cost=1.0))
    topo.add_link(TopologyLink(source="AS200_R1", target="AS300_R1", cost=1.0))
    topo.add_link(TopologyLink(source="AS100_R1", target="AS400_R1", cost=2.0))
    topo.add_link(TopologyLink(source="AS400_R1", target="AS300_R1", cost=2.0))
    topo.add_link(TopologyLink(source="AS200_R1", target="AS400_R1", cost=1.5))
    return topo
