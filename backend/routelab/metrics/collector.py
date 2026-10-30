"""Performance metrics collection, reporting, and CSV/JSON export for RouteLab.

Aggregates:
- Convergence time (s)
- Control messages & byte volume
- Route flap counts
- Loop and blackhole occurrences
- Packet delivery ratio during network mutations
- Export to structured JSON and CSV tables
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from routelab.sim.engine import SimulationEngine


@dataclass
class RunMetrics:
    """Consolidated metrics summary for a single simulation run."""

    protocol_name: str
    topology_name: str
    node_count: int
    link_count: int
    convergence_time_s: float
    total_control_messages: int
    total_control_bytes: int
    total_route_flaps: int
    loops_detected_count: int
    blackholes_count: int
    average_path_stretch: float
    is_optimal: bool
    packets_delivered: int
    packets_dropped: int
    delivery_ratio: float
    is_converged: bool = True
    per_node_messages: dict[str, int] = field(default_factory=dict)
    per_node_flaps: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MetricsCollector:
    """Collects and exports metrics across simulation runs."""

    @classmethod
    def collect_from_engine(
        cls,
        engine: SimulationEngine,
        protocol_name: str,
        oracle_report: Any | None = None,
    ) -> RunMetrics:
        """Extract and compute performance metrics from a completed simulation engine run."""
        node_count = len(engine.nodes)
        link_count = len(engine.links)

        total_msgs = sum(n.packets_sent for n in engine.nodes.values())
        total_bytes = sum(n.bytes_sent for n in engine.nodes.values())
        total_flaps = sum(n.flaps_count for n in engine.nodes.values())

        per_node_msgs = {nid: n.packets_sent for nid, n in engine.nodes.items()}
        per_node_flaps = {nid: n.flaps_count for nid, n in engine.nodes.items()}

        total_delivered = sum(lnk.stats.packets_delivered for lnk in engine.links.values())
        total_dropped = sum(
            lnk.stats.packets_dropped_down + lnk.stats.packets_dropped_loss
            for lnk in engine.links.values()
        )
        total_traffic = total_delivered + total_dropped
        delivery_ratio = total_delivered / max(1, total_traffic)

        loops_count = len(oracle_report.loops_detected) if oracle_report else 0
        blackholes_count = len(oracle_report.blackholes_detected) if oracle_report else 0
        stretch = oracle_report.average_path_stretch if oracle_report else 1.0
        is_opt = oracle_report.is_optimal if oracle_report else True

        return RunMetrics(
            protocol_name=protocol_name,
            topology_name=engine.topology.name,
            node_count=node_count,
            link_count=link_count,
            convergence_time_s=round(engine.convergence_record.convergence_time_s, 4),
            total_control_messages=total_msgs,
            total_control_bytes=total_bytes,
            total_route_flaps=total_flaps,
            loops_detected_count=loops_count,
            blackholes_count=blackholes_count,
            average_path_stretch=stretch,
            is_optimal=is_opt,
            packets_delivered=total_delivered,
            packets_dropped=total_dropped,
            delivery_ratio=round(delivery_ratio, 4),
            is_converged=engine.convergence_record.is_converged,
            per_node_messages=per_node_msgs,
            per_node_flaps=per_node_flaps,
        )

    @classmethod
    def export_csv(cls, metrics_list: list[RunMetrics], file_path: str | Path | None = None) -> str:
        """Serialize a list of RunMetrics to CSV format."""
        if not metrics_list:
            return ""

        output = io.StringIO()
        fieldnames = [
            "protocol_name",
            "topology_name",
            "node_count",
            "link_count",
            "convergence_time_s",
            "total_control_messages",
            "total_control_bytes",
            "total_route_flaps",
            "loops_detected_count",
            "blackholes_count",
            "average_path_stretch",
            "is_optimal",
            "packets_delivered",
            "packets_dropped",
            "delivery_ratio",
            "is_converged",
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for m in metrics_list:
            writer.writerow(m.to_dict())

        csv_content = output.getvalue()
        if file_path is not None:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(csv_content, encoding="utf-8")

        return csv_content

    @classmethod
    def export_json(
        cls, metrics_list: list[RunMetrics], file_path: str | Path | None = None
    ) -> str:
        """Serialize a list of RunMetrics to JSON format."""
        data = [m.to_dict() for m in metrics_list]
        json_content = json.dumps(data, indent=2)
        if file_path is not None:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json_content, encoding="utf-8")
        return json_content
