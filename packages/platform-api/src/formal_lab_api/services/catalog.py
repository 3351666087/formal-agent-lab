"""Plugin catalog: registry entries mirrored into the database so every entry point sees one directory."""

from __future__ import annotations

from typing import Any

from formal_lab_contracts import utcnow
from sqlalchemy.orm import Session

from ..db import PluginRow
from .common import registry


def sync_catalog(s: Session) -> int:
    reg = registry()
    seen = set()
    for entry in reg.entries():
        d = entry.descriptor
        key = (d.plugin_id, d.version)
        seen.add(key)
        row = s.get(PluginRow, key)
        data = d.model_dump(mode="json")
        if row is None:
            s.add(PluginRow(plugin_id=d.plugin_id, version=d.version, interface=d.interface.value, descriptor=data,
                            descriptor_digest=entry.descriptor_digest, source=entry.source))
        else:
            row.descriptor, row.descriptor_digest, row.source = data, entry.descriptor_digest, entry.source
            row.interface, row.loaded_at = d.interface.value, utcnow()
    return len(seen)


def catalog(interface: str | None = None) -> list[dict[str, Any]]:
    reg = registry()
    out = []
    for entry in reg.entries(interface):
        item = entry.as_dict()
        item["available"] = True
        if entry.descriptor.plugin_id == "formal-lab.planner.llm":
            from formal_lab_runtime.settings import llm_configured

            item["available"] = llm_configured()
            item["availability_note"] = ("real model configured" if item["available"]
                                         else "no FAL_LLM_API_KEY: use client=stub (labelled LLM_STUB)")
        out.append(item)
    return out


def load_errors() -> list[dict[str, str]]:
    return registry().load_errors
