"""Topologies management and generation router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from routelab.api.models import GenerateTopologyRequest, TopologySummary
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
from routelab.topology.model import Topology

router = APIRouter(prefix="/topologies", tags=["topologies"])

PRESET_GENERATORS = {
    "Course-6-Node-Benchmark": (
        preset_6_node,
        "Course-mandated 6-node meshed benchmark topology",
    ),
    "Course-8-Node-Benchmark": (
        preset_8_node,
        "8-node two-cluster topology with critical bridge link",
    ),
    "Course-10-Node-Benchmark": (
        preset_10_node,
        "10-node WAN backbone benchmark topology",
    ),
    "Count-to-Infinity-Linear": (
        preset_count_to_infinity,
        "Linear chain designed to reproduce count-to-infinity anomaly",
    ),
    "BGP-Multi-AS-Interdomain": (
        preset_bgp_tier1,
        "Multi-AS BGP topology with customer-provider peering",
    ),
}


@router.get("", response_model=list[TopologySummary])
def list_topologies() -> list[TopologySummary]:
    """List available built-in preset topologies."""
    summaries: list[TopologySummary] = []
    for name, (factory, desc) in PRESET_GENERATORS.items():
        topo = factory()
        summaries.append(
            TopologySummary(
                name=name,
                node_count=len(topo.nodes),
                link_count=len(topo.links),
                is_preset=True,
                description=desc,
            )
        )
    return summaries


@router.get("/{name}")
def get_topology(name: str) -> dict[str, Any]:
    """Retrieve full node and link layout data for a specific topology."""
    if name not in PRESET_GENERATORS:
        raise HTTPException(status_code=404, detail=f"Topology '{name}' not found")

    factory, desc = PRESET_GENERATORS[name]
    topo = factory()
    return {
        "name": topo.name,
        "description": desc,
        "nodes": [n.to_dict() for n in topo.nodes.values()],
        "links": [lnk.to_dict() for lnk in topo.links],
    }


@router.post("/generate")
def generate_topology(req: GenerateTopologyRequest) -> dict[str, Any]:
    """Generate dynamic synthetic topology on demand."""
    kind = req.kind.lower()
    topo: Topology

    if kind == "ring":
        topo = generate_ring(num_nodes=req.node_count)
    elif kind == "grid":
        w = req.width or int(req.node_count**0.5)
        h = req.height or (req.node_count // max(1, w))
        topo = generate_grid(rows=h, cols=w)
    elif kind == "tree":
        topo = generate_tree(branching_factor=req.branching_factor, depth=req.depth)
    elif kind == "random_geometric":
        topo = generate_random_geometric(num_nodes=req.node_count, radius=req.radius, seed=req.seed)
    elif kind == "scale_free":
        topo = generate_scale_free(num_nodes=req.node_count, m=req.attachment_m, seed=req.seed)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported topology generator type: '{req.kind}'",
        )

    topo.name = req.name or topo.name
    return {
        "name": topo.name,
        "kind": kind,
        "nodes": [n.to_dict() for n in topo.nodes.values()],
        "links": [lnk.to_dict() for lnk in topo.links],
    }
