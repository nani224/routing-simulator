"""Plugin management, dynamic inspection, and sandboxed upload router."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from routelab.api.models import PluginSummary
from routelab.api.state import session_manager
from routelab.attacks.mitigation import SecureDistanceVectorProtocol
from routelab.attacks.poisoning import PoisoningAttackProtocol
from routelab.plugins.interface import RoutingProtocol
from routelab.plugins.loader import PluginLoader
from routelab.protocols.bgp_lite import BGPLiteProtocol
from routelab.protocols.dv import DistanceVectorProtocol
from routelab.protocols.flooding import FloodingProtocol
from routelab.protocols.ls import LinkStateProtocol

router = APIRouter(prefix="/plugins", tags=["plugins"])

BUILTIN_PROTOCOLS = [
    DistanceVectorProtocol,
    LinkStateProtocol,
    BGPLiteProtocol,
    FloodingProtocol,
    PoisoningAttackProtocol,
    SecureDistanceVectorProtocol,
]


@router.get("", response_model=list[PluginSummary])
def list_plugins() -> list[PluginSummary]:
    """List all registered and built-in protocol plugins."""
    plugins: list[PluginSummary] = []
    for proto in BUILTIN_PROTOCOLS:
        plugins.append(
            PluginSummary(
                name=proto.name,
                version=proto.version,
                author=proto.author,
                description=proto.__doc__ or "",
                config_schema=proto.config_schema,
                is_builtin=True,
            )
        )
    return plugins


@router.get("/{name}", response_model=PluginSummary)
def get_plugin_details(name: str) -> PluginSummary:
    """Retrieve metadata and schema for a specific plugin."""
    for proto in BUILTIN_PROTOCOLS:
        if proto.name == name:
            return PluginSummary(
                name=proto.name,
                version=proto.version,
                author=proto.author,
                description=proto.__doc__ or "",
                config_schema=proto.config_schema,
                is_builtin=True,
            )
    raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")


@router.post("/upload", response_model=PluginSummary)
async def upload_plugin(file: UploadFile = File(...)) -> PluginSummary:
    """Upload, sandbox-validate, and register a new custom Python protocol plugin."""
    if not file.filename or not file.filename.endswith(".py"):
        raise HTTPException(
            status_code=400,
            detail="Uploaded plugin must be a valid Python (.py) file",
        )

    content = await file.read()

    # Save to temp file and load through PluginLoader
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        report = PluginLoader.load_from_file(tmp_path)
        if not report.is_valid or report.protocol_class is None:
            err_msg = "; ".join(report.errors) if report.errors else "Unknown validation error"
            raise ValueError(f"Plugin failed validation: {err_msg}")

        plugin_class = report.protocol_class
        target_cls = plugin_class

        def _custom_factory(cfg: dict[str, Any]) -> RoutingProtocol:
            return target_cls(cfg)

        session_manager.PROTOCOL_MAP[report.plugin_name] = _custom_factory

        return PluginSummary(
            name=report.plugin_name,
            version=report.version,
            author=getattr(plugin_class, "author", "Custom Author"),
            description=plugin_class.__doc__ or "",
            config_schema=report.config_schema,
            is_builtin=False,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Plugin failed sandbox validation: {exc}",
        ) from exc
    finally:
        if tmp_path.exists():
            tmp_path.unlink()
