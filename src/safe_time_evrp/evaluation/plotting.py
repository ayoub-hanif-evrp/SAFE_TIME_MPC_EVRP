"""Optional route and state-of-charge figure for a development episode."""

from __future__ import annotations

from pathlib import Path

from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import LogRecord


def write_route_soc_plot(instance: Instance, log: list[LogRecord], path: Path) -> str:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return "matplotlib_not_installed"
    positions: dict[str, list[tuple[float, float]]] = {}
    soc: dict[str, list[tuple[float, float]]] = {}
    for record in log:
        if record.vehicle_id is None:
            continue
        if record.kind == "vehicle_init":
            node = instance.node(record.data["node"])
            positions.setdefault(record.vehicle_id, []).append((node.x, node.y))
            soc.setdefault(record.vehicle_id, []).append((record.time, record.data["soc"]))
        elif record.kind == "arrive":
            node = instance.node(record.data["destination"])
            positions.setdefault(record.vehicle_id, []).append((node.x, node.y))
            soc.setdefault(record.vehicle_id, []).append((record.time, record.data["soc"]))
        elif record.kind == "charge_end":
            soc.setdefault(record.vehicle_id, []).append((record.time, record.data["soc"]))
    figure, axes = plt.subplots(1, 2, figsize=(9, 4))
    for vehicle_id, points in positions.items():
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        axes[0].plot(xs, ys, marker="o", label=vehicle_id)
    for node in instance.nodes.values():
        axes[0].scatter(node.x, node.y, s=12)
    axes[0].set_title("Executed positions")
    axes[0].set_aspect("equal", adjustable="datalim")
    axes[0].legend()
    for vehicle_id, series in soc.items():
        axes[1].plot([item[0] for item in series], [item[1] for item in series], label=vehicle_id)
    axes[1].set_title("State of charge")
    axes[1].set_xlabel("time")
    axes[1].legend()
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=120)
    plt.close(figure)
    return "written"
