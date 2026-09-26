"""Plugin registry: discovers installed plugins through the `formal_lab.plugins` entry-point group.

The core never imports plugin packages directly — built-in and external plugins are registered the same
way (see docs/architecture/plugin-integration.md). Each registration is validated (contract version,
interface version, entrypoint) and recorded in a catalog with its descriptor digest.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from importlib import metadata
from typing import Any

from formal_lab_contracts import CONTRACT_VERSION, PluginDescriptor, PluginInterface, PluginRef, digest_of
from formal_lab_contracts.capabilities import CapabilityNegotiation, CapabilityRequirement, negotiate
from formal_lab_contracts.errors import InvalidInput, NotFound, VersionMismatch
from formal_lab_contracts.interfaces import ENTRY_POINT_GROUP, PluginRegistration
from formal_lab_contracts.objects import INTERFACE_VERSION

log = logging.getLogger(__name__)


@dataclass
class CatalogEntry:
    descriptor: PluginDescriptor
    registration: PluginRegistration
    source: str  # entry point "name = value" or "manual"
    descriptor_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "descriptor": self.descriptor.model_dump(mode="json"),
            "source": self.source,
            "descriptor_digest": self.descriptor_digest,
        }


class PluginRegistry:
    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], CatalogEntry] = {}
        self.load_errors: list[dict[str, str]] = []

    # ------------------------------------------------------------------ registration
    def register(self, reg: PluginRegistration, source: str = "manual") -> CatalogEntry:
        d = reg.descriptor
        if d.contract_version != CONTRACT_VERSION:
            raise VersionMismatch(f"{d.plugin_id} targets {d.contract_version}, platform speaks {CONTRACT_VERSION}")
        if d.interface_version != INTERFACE_VERSION:
            raise VersionMismatch(f"{d.plugin_id} implements interface v{d.interface_version}, "
                                  f"platform supports v{INTERFACE_VERSION}")
        if not callable(reg.factory):
            raise InvalidInput(f"{d.plugin_id}: factory is not callable")
        key = (d.plugin_id, d.version)
        if key in self._entries and self._entries[key].descriptor != d:
            raise InvalidInput(f"conflicting registrations for {d.plugin_id}@{d.version}")
        entry = CatalogEntry(d, reg, source, digest_of(d).value)
        self._entries[key] = entry
        return entry

    def discover(self) -> PluginRegistry:
        for ep in sorted(metadata.entry_points(group=ENTRY_POINT_GROUP), key=lambda e: e.name):
            try:
                provider = ep.load()
                regs = provider() if callable(provider) else provider
                for reg in regs:
                    self.register(reg, source=f"{ep.name} = {ep.value}")
            except Exception as exc:  # a broken plugin must not take the platform down
                log.exception("failed to load plugin entry point %s", ep.name)
                self.load_errors.append({"entry_point": f"{ep.name} = {ep.value}", "error": repr(exc)})
        return self

    # ------------------------------------------------------------------ lookup
    def entries(self, interface: PluginInterface | str | None = None) -> list[CatalogEntry]:
        out = list(self._entries.values())
        if interface is not None:
            out = [e for e in out if e.descriptor.interface == PluginInterface(interface)]
        return sorted(out, key=lambda e: (e.descriptor.interface, e.descriptor.plugin_id, e.descriptor.version))

    def get(self, ref: PluginRef | tuple[str, str]) -> CatalogEntry:
        key = (ref.plugin_id, ref.version) if isinstance(ref, PluginRef) else ref
        if key not in self._entries:
            versions = sorted(v for (pid, v) in self._entries if pid == key[0])
            raise NotFound(f"plugin {key[0]}@{key[1]} is not installed"
                           + (f" (installed versions: {versions})" if versions else ""))
        return self._entries[key]

    def latest(self, plugin_id: str) -> CatalogEntry:
        versions = [e for (pid, _), e in self._entries.items() if pid == plugin_id]
        if not versions:
            raise NotFound(f"plugin {plugin_id} is not installed")
        return max(versions, key=lambda e: tuple(int(x) for x in e.descriptor.version.split("-")[0].split(".")))

    def create(self, ref: PluginRef, config: dict[str, Any] | None, services: Any, *,
               expect: PluginInterface | None = None) -> Any:
        entry = self.get(ref)
        if expect is not None and entry.descriptor.interface != expect:
            raise InvalidInput(f"{ref.plugin_id} is a {entry.descriptor.interface}, expected {expect}")
        return entry.registration.factory(dict(config or {}), services)

    def negotiate(self, ref: PluginRef, requirements: list[CapabilityRequirement]) -> CapabilityNegotiation:
        return negotiate(self.get(ref).descriptor, requirements)

    def catalog(self) -> list[dict[str, Any]]:
        return [e.as_dict() for e in self.entries()]


_default: PluginRegistry | None = None


def default_registry(refresh: bool = False) -> PluginRegistry:
    global _default
    if _default is None or refresh:
        _default = PluginRegistry().discover()
    return _default
