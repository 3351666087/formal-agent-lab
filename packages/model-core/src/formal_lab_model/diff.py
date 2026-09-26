"""Structural diff between two model versions (shown in the model workbench)."""

from __future__ import annotations

from typing import Any, Literal

from formal_lab_contracts import ModelIR
from pydantic import BaseModel

SECTIONS = ("enums", "entity_sets", "constants", "state", "actions", "properties")


class ModelChange(BaseModel):
    section: str
    name: str
    kind: Literal["added", "removed", "changed"]
    before: Any | None = None
    after: Any | None = None


def _key(section: str, item: dict[str, Any]) -> str:
    return item["id"] if section == "properties" else item["name"]


def diff_models(old: ModelIR, new: ModelIR) -> list[ModelChange]:
    a, b = old.model_dump(mode="json"), new.model_dump(mode="json")
    changes: list[ModelChange] = []
    for field in ("name", "description", "semantic_profile", "features"):
        if a[field] != b[field]:
            changes.append(ModelChange(section="model", name=field, kind="changed", before=a[field], after=b[field]))
    for section in SECTIONS:
        before = {_key(section, x): x for x in a[section]}
        after = {_key(section, x): x for x in b[section]}
        for name in before.keys() - after.keys():
            changes.append(ModelChange(section=section, name=name, kind="removed", before=before[name]))
        for name in after.keys() - before.keys():
            changes.append(ModelChange(section=section, name=name, kind="added", after=after[name]))
        for name in before.keys() & after.keys():
            if before[name] != after[name]:
                changes.append(ModelChange(section=section, name=name, kind="changed", before=before[name],
                                           after=after[name]))
        order_a = [n for n in before if n in after]
        order_b = [n for n in after if n in before]
        if order_a != order_b and section in ("actions", "entity_sets", "enums"):
            changes.append(ModelChange(section=section, name="(order)", kind="changed", before=order_a, after=order_b))
    return sorted(changes, key=lambda c: (SECTIONS.index(c.section) if c.section in SECTIONS else -1, c.name))
