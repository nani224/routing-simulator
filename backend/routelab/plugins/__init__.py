"""Routing protocol plugin interfaces, loader, and isolation sandboxes."""

from routelab.plugins.interface import NeighborInfo, ProtocolContext, RouteEntry, RoutingProtocol
from routelab.plugins.loader import (
    IsolatedProtocolRunner,
    PluginLoader,
    PluginValidationError,
    ValidationReport,
)

__all__ = [
    "RoutingProtocol",
    "ProtocolContext",
    "RouteEntry",
    "NeighborInfo",
    "PluginLoader",
    "PluginValidationError",
    "ValidationReport",
    "IsolatedProtocolRunner",
]
