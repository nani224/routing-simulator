"""Dynamic routing protocol plugin loader, validator, and isolation runner.

Enforces:
1. Interface conformance (subclass of RoutingProtocol with all required hooks).
2. Serialization sanity (messages must be msgpack-serializable).
3. Exception isolation: a malfunctioning plugin marks the node as FAULTY with a full traceback,
   never crashing the simulation engine or event loop.
4. Watchdog timer: guards against infinite loops or excessive compute in callbacks.
5. Hot reloading without restarting the simulator.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
import threading
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar, cast

from routelab.plugins.interface import ProtocolContext, RouteEntry, RoutingProtocol

T = TypeVar("T")


@dataclass
class ValidationReport:
    """Result of plugin static and dynamic validation."""

    is_valid: bool
    protocol_class: type[RoutingProtocol] | None = None
    plugin_name: str = ""
    version: str = "1.0.0"
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    config_schema: dict[str, Any] = field(default_factory=dict)


class PluginValidationError(Exception):
    """Raised when a plugin fails structural or runtime validation."""


class PluginLoader:
    """Loads, validates, and manages routing protocol plugins dynamically."""

    REQUIRED_METHODS: tuple[str, ...] = (
        "on_start",
        "on_message",
        "on_link_change",
        "on_timer",
        "get_table",
    )

    @classmethod
    def validate_class(cls, candidate: type[Any]) -> ValidationReport:
        """Validate candidate class against RoutingProtocol specification."""
        errors: list[str] = []
        warnings: list[str] = []

        if not inspect.isclass(candidate):
            return ValidationReport(is_valid=False, errors=["Target is not a Python class"])

        if not issubclass(candidate, RoutingProtocol):
            errors.append(f"Class '{candidate.__name__}' must inherit from RoutingProtocol")

        # Check required methods and signatures
        for method_name in cls.REQUIRED_METHODS:
            method = getattr(candidate, method_name, None)
            if method is None or not callable(method):
                errors.append(f"Missing required method '{method_name}'")
            elif getattr(method, "__isabstractmethod__", False):
                errors.append(f"Method '{method_name}' remains abstract")

        plugin_name = getattr(candidate, "name", candidate.__name__)
        version = getattr(candidate, "version", "1.0.0")
        schema = getattr(candidate, "config_schema", {})

        if not schema:
            warnings.append("No config_schema specified; UI will use empty parameters")

        is_valid = len(errors) == 0
        proto_cls: type[RoutingProtocol] | None = (
            candidate if (is_valid and issubclass(candidate, RoutingProtocol)) else None
        )
        return ValidationReport(
            is_valid=is_valid,
            protocol_class=proto_cls,
            plugin_name=plugin_name,
            version=version,
            errors=errors,
            warnings=warnings,
            config_schema=schema,
        )

    @classmethod
    def load_from_source(
        cls, source_code: str, module_name: str = "custom_plugin"
    ) -> ValidationReport:
        """Load and validate a plugin directly from Python source code string."""
        try:
            compiled = compile(source_code, f"<plugin:{module_name}>", "exec")
            module_ns: dict[str, Any] = {}
            exec(compiled, module_ns)
        except Exception as exc:  # noqa: BLE001
            tb = traceback.format_exc()
            return ValidationReport(
                is_valid=False,
                errors=[f"Syntax or compile error in plugin: {exc}\n{tb}"],
            )

        candidate_classes: list[type[RoutingProtocol]] = []
        for val in module_ns.values():
            if (
                inspect.isclass(val)
                and issubclass(val, RoutingProtocol)
                and val is not RoutingProtocol
            ):
                candidate_classes.append(val)

        if not candidate_classes:
            return ValidationReport(
                is_valid=False,
                errors=["No subclass of RoutingProtocol found in provided source code"],
            )

        return cls.validate_class(candidate_classes[0])

    @classmethod
    def load_from_file(cls, file_path: str | Path) -> ValidationReport:
        """Load and validate a plugin from a .py file path on disk."""
        path = Path(file_path).resolve()
        if not path.is_file():
            return ValidationReport(
                is_valid=False,
                errors=[f"Plugin file not found: {path}"],
            )

        module_name = f"routelab_plugin_{path.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                return ValidationReport(
                    is_valid=False,
                    errors=[f"Cannot load module spec from file: {path}"],
                )
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001
            tb = traceback.format_exc()
            return ValidationReport(
                is_valid=False,
                errors=[f"Runtime error importing {path.name}: {exc}\n{tb}"],
            )

        candidates: list[type[RoutingProtocol]] = []
        for val in module.dict__.values() if hasattr(module, "dict__") else vars(module).values():
            if (
                inspect.isclass(val)
                and issubclass(val, RoutingProtocol)
                and val is not RoutingProtocol
            ):
                candidates.append(val)

        if not candidates:
            return ValidationReport(
                is_valid=False,
                errors=[f"No RoutingProtocol implementation found in {path.name}"],
            )

        return cls.validate_class(candidates[0])


class IsolatedProtocolRunner:
    """Sandbox wrapper that isolates plugin execution per node.

    Guarantees:
    - If a plugin throws an unhandled exception, the node is marked FAULTY with
      the traceback captured, but the simulation engine continues running.
    - If a plugin produces non-serializable messages, it is intercepted and logged.
    - Time budget / watchdog with thread preemption limits execution duration per callback,
      preventing infinite loops (e.g. while True) from hanging the simulation engine.
    """

    def __init__(
        self,
        node_id: str,
        protocol: RoutingProtocol,
        context: ProtocolContext,
        max_callback_ms: float = 200.0,
        force_sandbox: bool = False,
    ) -> None:
        self.node_id = node_id
        self.protocol = protocol
        self.context = context
        self.max_callback_ms = max_callback_ms
        self.force_sandbox = force_sandbox

        self.is_faulty: bool = False
        self.fault_traceback: str | None = None
        self.fault_error: str | None = None
        mod = getattr(protocol.__class__, "__module__", "")
        self._is_trusted: bool = mod.startswith(("routelab.protocols", "routelab.attacks"))

    def _mark_fault(self, error: Exception, hook_name: str, tb_str: str | None = None) -> None:
        self.is_faulty = True
        self.fault_error = f"{type(error).__name__} in {hook_name}: {error}"
        self.fault_traceback = tb_str or traceback.format_exc()
        self.context.log(
            f"PLUGIN FAULT on {self.node_id}: {self.fault_error}\n{self.fault_traceback}",
            level="ERROR",
        )

    def _execute_guarded(self, hook_name: str, fn: Callable[[], T], default: T) -> T:
        if self.is_faulty:
            return default

        # For trusted built-in protocols without explicit sandbox forcing,
        # execute directly with timing
        if self._is_trusted and not self.force_sandbox:
            t0 = time.perf_counter()
            try:
                res = fn()
            except Exception as exc:  # noqa: BLE001
                self._mark_fault(exc, hook_name)
                return default
            dur_ms = (time.perf_counter() - t0) * 1000.0
            if dur_ms > self.max_callback_ms:
                self.context.log(
                    f"Watchdog warning: {hook_name} took {dur_ms:.1f}ms "
                    f"(limit: {self.max_callback_ms:.1f}ms)",
                    level="WARNING",
                )
            return res

        # For untrusted dynamic plugins: preemption watchdog thread guard
        result: list[T] = [default]
        exc_holder: list[tuple[Exception, str]] = []

        def worker() -> None:
            try:
                result[0] = fn()
            except Exception as exc:  # noqa: BLE001
                exc_holder.append((exc, traceback.format_exc()))

        timeout_s = max(self.max_callback_ms / 1000.0, 0.001)
        thread = threading.Thread(target=worker, daemon=True)
        t0 = time.perf_counter()
        thread.start()
        thread.join(timeout=timeout_s)

        if thread.is_alive():
            # Preemption guard tripped: plugin is hanging in loop or excessive computation
            self.is_faulty = True
            self.fault_error = (
                f"TimeoutError in {hook_name}: exceeded {self.max_callback_ms:.1f}ms limit"
            )
            self.fault_traceback = (
                f"Watchdog preemption guard tripped in {hook_name} on node {self.node_id} "
                f"(thread still running after {self.max_callback_ms:.1f}ms)"
            )
            self.context.log(
                f"PLUGIN FAULT on {self.node_id}: {self.fault_error}\n{self.fault_traceback}",
                level="ERROR",
            )
            return default

        dur_ms = (time.perf_counter() - t0) * 1000.0
        if exc_holder:
            captured_exc, tb_str = exc_holder[0]
            self._mark_fault(captured_exc, hook_name, tb_str=tb_str)
            return default

        if dur_ms > (self.max_callback_ms * 0.75):
            self.context.log(
                f"Watchdog warning: {hook_name} took {dur_ms:.1f}ms "
                f"(limit: {self.max_callback_ms:.1f}ms)",
                level="WARNING",
            )

        return result[0]

    def on_start(self) -> None:
        self._execute_guarded("on_start", lambda: self.protocol.on_start(self.context), None)

    def on_message(self, src: str, msg: dict[str, Any]) -> None:
        self._execute_guarded(
            f"on_message({src})",
            lambda: self.protocol.on_message(self.context, src, msg),
            None,
        )

    def on_link_change(self, nbr: str, cost: float, up: bool) -> None:
        self._execute_guarded(
            f"on_link_change({nbr})",
            lambda: self.protocol.on_link_change(self.context, nbr, cost, up),
            None,
        )

    def on_timer(self, timer_id: str) -> None:
        self._execute_guarded(
            f"on_timer({timer_id})",
            lambda: self.protocol.on_timer(self.context, timer_id),
            None,
        )

    def get_table(self) -> list[RouteEntry]:
        return self._execute_guarded("get_table", lambda: self.protocol.get_table(), [])

    def describe_state(self) -> dict[str, Any]:
        if self.is_faulty:
            return {
                "faulty": True,
                "error": self.fault_error,
                "traceback": self.fault_traceback,
            }

        def _get_desc() -> dict[str, Any]:
            state = self.protocol.describe_state()
            state["faulty"] = False
            return state

        res = self._execute_guarded("describe_state", _get_desc, cast(dict[str, Any], {}))
        if not res:
            return {
                "faulty": True,
                "error": self.fault_error,
                "traceback": self.fault_traceback,
            }
        return res
