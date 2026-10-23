"""Topology persistence, GraphML / JSON serialization, and graph sanity validation."""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx

from routelab.topology.model import Topology


class TopologyValidationError(Exception):
    """Raised when topology definition violates structural sanity."""


class TopologyLoader:
    """Handles importing, exporting, and verifying network topologies."""

    @classmethod
    def load_json(cls, file_path: str | Path) -> Topology:
        path = Path(file_path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        topo = Topology.from_dict(data)
        cls.validate(topo)
        return topo

    @classmethod
    def save_json(cls, topo: Topology, file_path: str | Path) -> None:
        cls.validate(topo)
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(topo.to_dict(), f, indent=2)

    @classmethod
    def load_graphml(cls, file_path: str | Path) -> Topology:
        path = Path(file_path)
        g = nx.read_graphml(path)
        topo = Topology.from_networkx(g, name=path.stem)
        cls.validate(topo)
        return topo

    @classmethod
    def save_graphml(cls, topo: Topology, file_path: str | Path) -> None:
        cls.validate(topo)
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        g = topo.to_networkx()
        nx.write_graphml(g, path)

    @classmethod
    def validate(cls, topo: Topology) -> list[str]:
        """Validate topology structure. Raises TopologyValidationError if invalid."""
        errors: list[str] = []
        if not topo.nodes:
            errors.append("Topology contains no nodes")

        node_keys = set(topo.nodes.keys())
        for link in topo.links:
            if link.source not in node_keys:
                errors.append(f"Link source '{link.source}' does not exist in nodes")
            if link.target not in node_keys:
                errors.append(f"Link target '{link.target}' does not exist in nodes")
            if link.source == link.target:
                errors.append(f"Self-loop detected on node '{link.source}'")
            if link.cost <= 0:
                errors.append(
                    f"Non-positive link cost {link.cost} between {link.source} and {link.target}"
                )

        if errors:
            raise TopologyValidationError("; ".join(errors))

        # Check connectivity
        g = topo.to_networkx()
        if len(topo.nodes) > 1 and not nx.is_connected(g):
            # Not fatal error, but warnings can be returned
            pass

        return errors
