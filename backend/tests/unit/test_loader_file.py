"""Tests for PluginLoader file loading, syntax error isolation, and schema introspection."""

import tempfile
from pathlib import Path

from routelab.plugins.loader import PluginLoader


def test_plugin_load_from_valid_file() -> None:
    code = """
from routelab.plugins.interface import RoutingProtocol, ProtocolContext, RouteEntry

class FileBasedProtocol(RoutingProtocol):
    name = "file_based"
    version = "2.1.0"
    config_schema = {"interval": {"type": "number", "default": 1.0}}

    def on_start(self, ctx: ProtocolContext) -> None:
        pass

    def on_message(self, ctx: ProtocolContext, src: str, msg: dict) -> None:
        pass

    def on_link_change(self, ctx: ProtocolContext, nbr: str, cost: float, up: bool) -> None:
        pass

    def on_timer(self, ctx: ProtocolContext, timer_id: str) -> None:
        pass

    def get_table(self) -> list[RouteEntry]:
        return []
"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        plugin_file = Path(tmp_dir) / "custom_proto.py"
        plugin_file.write_text(code, encoding="utf-8")

        report = PluginLoader.load_from_file(plugin_file)
        assert report.is_valid is True
        assert report.plugin_name == "file_based"
        assert report.version == "2.1.0"
        assert "interval" in report.config_schema


def test_plugin_load_from_invalid_syntax_file() -> None:
    code = "def this is broken python syntax"
    with tempfile.TemporaryDirectory() as tmp_dir:
        plugin_file = Path(tmp_dir) / "broken.py"
        plugin_file.write_text(code, encoding="utf-8")

        report = PluginLoader.load_from_file(plugin_file)
        assert report.is_valid is False
        assert len(report.errors) > 0


def test_plugin_load_non_existent_file() -> None:
    report = PluginLoader.load_from_file("does_not_exist_xyz.py")
    assert report.is_valid is False
    assert "not found" in report.errors[0]
