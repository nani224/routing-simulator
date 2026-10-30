"""Unit tests for plugin loader, validation, and sandbox exception isolation.

Includes 2 deliberately buggy plugins to prove that faulty plugins are cleanly
isolated, recorded with tracebacks, and never crash the simulator engine.
"""

from typing import Any

from routelab.core.clock import VirtualClock
from routelab.core.node import RouterNode
from routelab.plugins.interface import ProtocolContext, RouteEntry, RoutingProtocol
from routelab.plugins.loader import PluginLoader


# 1. Valid Plugin for testing
class DummyValidProtocol(RoutingProtocol):
    name = "dummy_valid"
    version = "1.0.0"
    config_schema = {"hello": {"type": "string", "default": "world"}}

    def on_start(self, ctx: ProtocolContext) -> None:
        ctx.broadcast({"type": "hello"})

    def on_message(self, ctx: ProtocolContext, src: str, msg: dict[str, Any]) -> None:
        pass

    def on_link_change(self, ctx: ProtocolContext, nbr: str, cost: float, up: bool) -> None:
        pass

    def on_timer(self, ctx: ProtocolContext, timer_id: str) -> None:
        pass

    def get_table(self) -> list[RouteEntry]:
        return [RouteEntry(destination="X", next_hop="Y", cost=1.0)]


# 2. Deliberately Buggy Plugin A: raises ZeroDivisionError in on_start
class BuggyCrashOnStartProtocol(RoutingProtocol):
    name = "buggy_crash_on_start"
    version = "1.0.0"

    def on_start(self, _ctx: ProtocolContext) -> None:
        # Deliberate crash
        _ = 1 / 0

    def on_message(self, _ctx: ProtocolContext, _src: str, _msg: dict[str, Any]) -> None:
        pass

    def on_link_change(self, _ctx: ProtocolContext, _nbr: str, _cost: float, _up: bool) -> None:
        pass

    def on_timer(self, _ctx: ProtocolContext, _timer_id: str) -> None:
        pass

    def get_table(self) -> list[RouteEntry]:
        return []


# 3. Deliberately Buggy Plugin B: raises KeyError in on_message
class BuggyKeyErrorOnMessageProtocol(RoutingProtocol):
    name = "buggy_key_error_on_message"
    version = "1.0.0"

    def on_start(self, _ctx: ProtocolContext) -> None:
        pass

    def on_message(self, _ctx: ProtocolContext, _src: str, msg: dict[str, Any]) -> None:
        # Deliberate access to missing key
        _ = msg["non_existent_key_that_triggers_crash"]

    def on_link_change(self, _ctx: ProtocolContext, _nbr: str, _cost: float, _up: bool) -> None:
        pass

    def on_timer(self, _ctx: ProtocolContext, _timer_id: str) -> None:
        pass

    def get_table(self) -> list[RouteEntry]:
        return []


def test_plugin_validation_valid_class() -> None:
    report = PluginLoader.validate_class(DummyValidProtocol)
    assert report.is_valid is True
    assert report.plugin_name == "dummy_valid"
    assert len(report.errors) == 0


def test_plugin_validation_missing_abstract_methods() -> None:
    class IncompleteProtocol(RoutingProtocol):
        name = "incomplete"
        # missing on_message, on_start, etc.

    report = PluginLoader.validate_class(IncompleteProtocol)
    assert report.is_valid is False
    assert len(report.errors) > 0


def test_plugin_load_from_source() -> None:
    source = """
from routelab.plugins.interface import RoutingProtocol, ProtocolContext, RouteEntry

class SourceCodePlugin(RoutingProtocol):
    name = "source_code_plugin"
    def on_start(self, ctx): pass
    def on_message(self, ctx, src, msg): pass
    def on_link_change(self, ctx, nbr, cost, up): pass
    def on_timer(self, ctx, timer_id): pass
    def get_table(self): return []
"""
    report = PluginLoader.load_from_source(source, "test_source")
    assert report.is_valid is True
    assert report.plugin_name == "source_code_plugin"
    assert report.protocol_class is not None


def test_buggy_plugin_a_isolation_on_start() -> None:
    vclock = VirtualClock()
    node = RouterNode("R_BUG_A", clock=vclock)
    plugin = BuggyCrashOnStartProtocol()
    node.set_protocol(plugin)

    runner = node._runner
    assert runner is not None
    assert not runner.is_faulty

    # Running on_start should NOT raise an unhandled exception
    runner.on_start()

    # Node is isolated and marked faulty
    assert runner.is_faulty is True
    assert "ZeroDivisionError" in (runner.fault_error or "")
    assert runner.fault_traceback is not None
    assert runner.get_table() == []
    desc = runner.describe_state()
    assert desc["faulty"] is True


def test_buggy_plugin_b_isolation_on_message() -> None:
    vclock = VirtualClock()
    node = RouterNode("R_BUG_B", clock=vclock)
    plugin = BuggyKeyErrorOnMessageProtocol()
    node.set_protocol(plugin)

    runner = node._runner
    assert runner is not None
    runner.on_start()
    assert not runner.is_faulty

    # Deliver message missing expected key
    runner.on_message("R_SRC", {"valid_key": 123})

    assert runner.is_faulty is True
    assert "KeyError" in (runner.fault_error or "")
    assert runner.fault_traceback is not None


class MaliciousHangProtocol(RoutingProtocol):
    name = "malicious_hang"
    version = "1.0.0"

    def on_start(self, _ctx: ProtocolContext) -> None:
        pass

    def on_message(self, _ctx: ProtocolContext, _src: str, _msg: dict[str, Any]) -> None:
        import time

        time.sleep(0.5)

    def on_link_change(self, _ctx: ProtocolContext, _nbr: str, _cost: float, _up: bool) -> None:
        pass

    def on_timer(self, _ctx: ProtocolContext, _timer_id: str) -> None:
        pass

    def get_table(self) -> list[RouteEntry]:
        return []


def test_malicious_plugin_preemption_guard() -> None:
    vclock = VirtualClock()
    node = RouterNode("R_MAL", clock=vclock)
    plugin = MaliciousHangProtocol()
    node.set_protocol(plugin)

    runner = node._runner
    assert runner is not None
    # Set short watchdog budget for test
    runner.max_callback_ms = 40.0
    runner.on_start()
    assert not runner.is_faulty

    # Trigger hanging on_message callback
    runner.on_message("R_SRC", {"type": "probe"})

    # Must be preempted and marked faulty with TimeoutError
    assert runner.is_faulty is True
    assert "TimeoutError" in (runner.fault_error or "")
    assert runner.fault_traceback is not None
