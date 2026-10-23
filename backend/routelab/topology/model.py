"""Topology data models and graph interchange formats for RouteLab."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

import networkx as nx


@dataclass
class TopologyNode:
    """Node configuration in a topology.

    Attributes:
        id: Unique router string identifier.
        x: X-coordinate for canvas drafting view.
        y: Y-coordinate for canvas drafting view.
        as_number: Autonomous System number (for BGP-lite policy evaluation).
        metadata: Arbitrary UI/metadata annotations.
    """

    id: str
    x: float = 0.0
    y: float = 0.0
    as_number: int = 65001
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TopologyNode:
        return cls(
            id=data["id"],
            x=data.get("x", 0.0),
            y=data.get("y", 0.0),
            as_number=data.get("as_number", 65001),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TopologyLink:
    """Link configuration connecting two router nodes.

    Attributes:
        source: First endpoint router ID.
        target: Second endpoint router ID.
        cost: Routing metric cost.
        latency_ms: Base propagation latency in milliseconds.
        jitter_ms: Uniform random latency variation (+/-).
        loss_rate: Packet loss probability (0.0 to 1.0).
        bandwidth_bps: Bandwidth constraint in bits/second (0 for unconstrained).
    """

    source: str
    target: str
    cost: float = 1.0
    latency_ms: float = 10.0
    jitter_ms: float = 0.0
    loss_rate: float = 0.0
    bandwidth_bps: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TopologyLink:
        return cls(
            source=data["source"],
            target=data["target"],
            cost=float(data.get("cost", 1.0)),
            latency_ms=float(data.get("latency_ms", 10.0)),
            jitter_ms=float(data.get("jitter_ms", 0.0)),
            loss_rate=float(data.get("loss_rate", 0.0)),
            bandwidth_bps=float(data.get("bandwidth_bps", 0.0)),
        )


@dataclass
class Topology:
    """Complete network topology containing nodes and interconnecting links."""

    name: str = "Untitled Topology"
    nodes: dict[str, TopologyNode] = field(default_factory=dict)
    links: list[TopologyLink] = field(default_factory=list)

    def add_node(self, node: TopologyNode) -> None:
        self.nodes[node.id] = node

    def add_link(self, link: TopologyLink) -> None:
        self.links.append(link)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "links": [lnk.to_dict() for lnk in self.links],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Topology:
        topo = cls(name=data.get("name", "Imported Topology"))
        for n_data in data.get("nodes", []):
            topo.add_node(TopologyNode.from_dict(n_data))
        for l_data in data.get("links", []):
            topo.add_link(TopologyLink.from_dict(l_data))
        return topo

    def to_networkx(self) -> nx.Graph:
        """Convert topology to a NetworkX Graph for shortest-path oracle validation."""
        g = nx.Graph()
        for node_id, node in self.nodes.items():
            g.add_node(
                node_id,
                x=float(node.x),
                y=float(node.y),
                as_number=int(node.as_number),
                metadata=json.dumps(node.metadata),
            )
        for link in self.links:
            g.add_edge(
                link.source,
                link.target,
                weight=float(link.cost),
                latency=float(link.latency_ms),
                loss=float(link.loss_rate),
            )
        return g

    @classmethod
    def from_networkx(cls, g: nx.Graph, name: str = "GraphML Topology") -> Topology:
        """Construct Topology from NetworkX Graph."""
        topo = cls(name=name)
        try:
            pos = nx.spring_layout(g, seed=42) if g.number_of_nodes() > 0 else {}
        except Exception:  # noqa: BLE001
            pos = {}

        for n in g.nodes():
            node_id = str(n)
            node_data = g.nodes[n]
            coords = pos.get(n, (0.0, 0.0))
            raw_meta = node_data.get("metadata", "{}")
            meta = json.loads(raw_meta) if isinstance(raw_meta, str) else {}
            topo.add_node(
                TopologyNode(
                    id=node_id,
                    x=float(node_data.get("x", coords[0] * 400 + 400)),
                    y=float(node_data.get("y", coords[1] * 300 + 300)),
                    as_number=int(node_data.get("as_number", 65001)),
                    metadata=meta,
                )
            )
        for u, v, data in g.edges(data=True):
            topo.add_link(
                TopologyLink(
                    source=str(u),
                    target=str(v),
                    cost=float(data.get("weight", 1.0)),
                    latency_ms=float(data.get("latency", 10.0)),
                    loss_rate=float(data.get("loss", 0.0)),
                )
            )
        return topo
