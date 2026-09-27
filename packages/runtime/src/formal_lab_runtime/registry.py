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

import jsonschema
from formal_lab_contracts import (
    CONTRACT_VERSION,
    SUPPORTED_CONTRACT_VERSIONS,
    PluginDescriptor,
    PluginInterface,
    PluginRef,
    digest_of,
)
from formal_lab_contracts.capabilities import CapabilityNegotiation, CapabilityRequirement, negotiate
from formal_lab_contracts.errors import FieldError, InvalidInput, NotFound, VersionMismatch
from formal_lab_contracts.interfaces import ENTRY_POINT_GROUP, PluginRegistration
from formal_lab_contracts.objects import SUPPORTED_INTERFACE_VERSIONS, V2_ONLY_INTERFACES

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
        """Validate and record a plugin. Accepted: contract v1 or v2, interface version 1 or 2 (v1 plugins keep
        working for the interfaces that existed in v1); the config schema must itself be a valid JSON Schema —
        the same check runs in the API and in every worker at start-up (P2-017)."""
        d = reg.descriptor
        if d.contract_version not in SUPPORTED_CONTRACT_VERSIONS:
            raise VersionMismatch(f"{d.plugin_id} targets {d.contract_version}, platform speaks "
                                  f"{', '.join(SUPPORTED_CONTRACT_VERSIONS)}")
        if d.interface_version not in SUPPORTED_INTERFACE_VERSIONS:
            raise VersionMismatch(f"{d.plugin_id} implements interface v{d.interface_version}, "
                                  f"platform supports v{', '.join(SUPPORTED_INTERFACE_VERSIONS)}")
        if d.interface in V2_ONLY_INTERFACES and (d.interface_version != "2" or d.contract_version != CONTRACT_VERSION):
            raise VersionMismatch(f"{d.plugin_id}: {PluginInterface(d.interface).value} plugins must declare interface version 2 "
                                  f"and {CONTRACT_VERSION}")
        try:
            jsonschema.validators.validator_for(d.config_schema).check_schema(d.config_schema)
        except jsonschema.SchemaError as exc:
            raise InvalidInput(f"{d.plugin_id}: config_schema is not a valid JSON Schema: {exc.message}") from exc
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

    def resolve(self, ref: PluginRef | tuple[str, str]) -> CatalogEntry:
        """The installed plugin for `ref`: the exact version, else the highest installed version with the same
        major version that is not older (semver-compatible). Run manifests record the resolved version."""
        key = (ref.plugin_id, ref.version) if isinstance(ref, PluginRef) else ref
        if key in self._entries:
            return self._entries[key]
        want = _semver(key[1])
        compatible = [e for (pid, v), e in self._entries.items()
                      if pid == key[0] and _semver(v)[0] == want[0] and _semver(v) >= want]
        if compatible:
            return max(compatible, key=lambda e: _semver(e.descriptor.version))
        return self.get(ref)

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
        return max(versions, key=lambda e: _semver(e.descriptor.version))

    def driver_for(self, semantic_profile: str) -> CatalogEntry:
        """The semantic driver for a profile (latest version); UNSUPPORTED-style NotFound when there is none."""
        drivers = [e for e in self.entries(PluginInterface.SEMANTIC_DRIVER)
                   if semantic_profile in e.descriptor.semantic_profiles]
        if not drivers:
            from formal_lab_contracts.errors import Unsupported

            raise Unsupported(f"no semantic driver is installed for profile {semantic_profile!r}",
                              details={"extension_point": "SEMANTIC_DRIVER plugin declaring the profile"})
        return max(drivers, key=lambda e: (e.descriptor.plugin_id == "formal-lab.driver.ir-finite",
                                           _semver(e.descriptor.version)))

    def validate_config(self, ref: PluginRef, config: dict[str, Any], *, path: str = "/config") -> None:
        """Validate a plugin configuration against its descriptor's config schema (field-level errors)."""
        schema = self.resolve(ref).descriptor.config_schema
        errors = sorted(jsonschema.validators.validator_for(schema)(schema).iter_errors(config),
                        key=lambda e: list(e.absolute_path))
        if errors:
            raise InvalidInput(f"invalid config for {ref.plugin_id}: {errors[0].message}",
                               field_errors=[FieldError(path=path + "".join(f"/{p}" for p in e.absolute_path),
                                                        message=e.message) for e in errors])

    def create(self, ref: PluginRef, config: dict[str, Any] | None, services: Any, *,
               expect: PluginInterface | None = None) -> Any:
        entry = self.resolve(ref)
        if expect is not None and entry.descriptor.interface != expect:
            raise InvalidInput(f"{ref.plugin_id} is a {entry.descriptor.interface}, expected {expect}")
        return entry.registration.factory(dict(config or {}), services)

    def negotiate(self, ref: PluginRef, requirements: list[CapabilityRequirement], *, role: str | None = None,
                  why: dict[str, str] | None = None) -> CapabilityNegotiation:
        return negotiate(self.resolve(ref).descriptor, requirements, role=role, why=why)

    def catalog(self) -> list[dict[str, Any]]:
        return [e.as_dict() for e in self.entries()]


def _semver(v: str) -> tuple[int, ...]:
    core = v.split("-")[0].split("+")[0]
    return tuple(int(x) for x in core.split(".") if x.isdigit())


_default: PluginRegistry | None = None


def default_registry(refresh: bool = False) -> PluginRegistry:
    global _default
    if _default is None or refresh:
        _default = PluginRegistry().discover()
    return _default
