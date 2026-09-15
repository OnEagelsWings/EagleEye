from __future__ import annotations

import importlib
import threading
from dataclasses import dataclass
from typing import Any, Callable, Iterable


class ServiceRegistryError(RuntimeError):
    pass


class UnknownServiceError(ServiceRegistryError, KeyError):
    pass


class CircularServiceDependencyError(ServiceRegistryError):
    pass


@dataclass(frozen=True, slots=True)
class ServiceDescriptor:
    name: str
    import_path: str
    lifecycle: str = "singleton"
    status: str = "active"
    group: str = "legacy"


Factory = Callable[["ServiceRegistry"], Any]
PostCreate = Callable[["ServiceRegistry", Any], None]


class ServiceRegistry:
    """Thread-safe lazy dependency container with cycle detection and test overrides."""

    def __init__(self) -> None:
        self._factories: dict[str, Factory] = {}
        self._descriptors: dict[str, ServiceDescriptor] = {}
        self._instances: dict[str, Any] = {}
        self._post_create: dict[str, PostCreate] = {}
        self._resolving = threading.local()
        self._lock = threading.RLock()
        self._closed = False

    def register(
        self,
        name: str,
        factory: Factory,
        *,
        import_path: str,
        lifecycle: str = "singleton",
        status: str = "active",
        group: str = "legacy",
        post_create: PostCreate | None = None,
    ) -> None:
        if not name or name.startswith("_"):
            raise ValueError("service name must be public and non-empty")
        if lifecycle not in {"singleton", "factory"}:
            raise ValueError(f"unsupported lifecycle: {lifecycle}")
        with self._lock:
            if self._closed:
                raise ServiceRegistryError("registry is closed")
            if name in self._factories:
                raise ServiceRegistryError(f"service already registered: {name}")
            self._factories[name] = factory
            self._descriptors[name] = ServiceDescriptor(name, import_path, lifecycle, status, group)
            if post_create is not None:
                self._post_create[name] = post_create

    def get(self, name: str) -> Any:
        with self._lock:
            if self._closed:
                raise ServiceRegistryError("registry is closed")
            try:
                descriptor = self._descriptors[name]
                factory = self._factories[name]
            except KeyError as exc:
                raise UnknownServiceError(name) from exc
            if descriptor.lifecycle == "singleton" and name in self._instances:
                return self._instances[name]

            stack = list(getattr(self._resolving, "stack", []))
            if name in stack:
                chain = " -> ".join([*stack, name])
                raise CircularServiceDependencyError(f"circular service dependency: {chain}")
            stack.append(name)
            self._resolving.stack = stack
            try:
                instance = factory(self)
                callback = self._post_create.get(name)
                if callback is not None:
                    callback(self, instance)
                if descriptor.lifecycle == "singleton":
                    self._instances[name] = instance
                return instance
            finally:
                stack.pop()
                self._resolving.stack = stack

    def construct(self, import_path: str, /, *args: Any, **kwargs: Any) -> Any:
        module_name, separator, object_name = import_path.partition(":")
        if not separator or not module_name or not object_name:
            raise ValueError(f"invalid import path: {import_path!r}")
        module = importlib.import_module(module_name)
        constructor = getattr(module, object_name)
        return constructor(*args, **kwargs)

    def override(self, name: str, instance: Any) -> None:
        with self._lock:
            if name not in self._factories:
                raise UnknownServiceError(name)
            self._instances[name] = instance

    def is_registered(self, name: str) -> bool:
        return name in self._factories

    def is_initialized(self, name: str) -> bool:
        return name in self._instances

    def peek(self, name: str, default: Any = None) -> Any:
        return self._instances.get(name, default)

    def initialized_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._instances))

    def descriptors(self) -> tuple[ServiceDescriptor, ...]:
        return tuple(self._descriptors[name] for name in sorted(self._descriptors))

    def close(self, preferred_order: Iterable[str] = ()) -> None:
        with self._lock:
            if self._closed:
                return
            seen: set[str] = set()
            ordered = [*preferred_order, *reversed(tuple(self._instances))]
            for name in ordered:
                if name in seen:
                    continue
                seen.add(name)
                instance = self._instances.get(name)
                close = getattr(instance, "close", None)
                if callable(close):
                    close()
            self._instances.clear()
            self._factories.clear()
            self._post_create.clear()
            self._descriptors.clear()
            self._closed = True
