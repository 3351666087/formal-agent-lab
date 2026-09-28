"""Probabilistic checks through the optional PRISM-games extension (P2-X04).

The game comes from the model version's typed extension (`extensions["org.formal-lab.prism-games"]`, schema
`…/allocation-game@1`) or from the request. The result is a `ProbabilisticCheckRecord` (`…/result@1`): stored with
the version's checks but under its own verdict `PROBABILISTIC`, listed by its own endpoint and never mixed into the
deterministic Z3 check list. Without a local PRISM-games installation the endpoint answers UNSUPPORTED with the
reason — the platform never substitutes another answer.
"""

from __future__ import annotations

import uuid
from typing import Any

from formal_lab_contracts.errors import InvalidInput, Unsupported
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import CheckRow, Model, ModelVersion
from .common import get_or_404
from .modeling import package_of

VERDICT = "PROBABILISTIC"


def availability() -> dict[str, Any]:
    from formal_lab_solver_prism import (
        ASSUMPTIONS,
        CAPABILITIES,
        EXAMPLE,
        GAME_SCHEMA,
        PINNED,
        PROFILE,
        RESULT_SCHEMA,
        AllocationGame,
        Unavailable,
        version,
    )

    info: dict[str, Any] = {"extension": "org.formal-lab.prism-games", "profile": PROFILE, "game_schema": GAME_SCHEMA,
                            "result_schema": RESULT_SCHEMA, "pinned": PINNED, "assumptions": ASSUMPTIONS,
                            "capabilities": CAPABILITIES, "example": EXAMPLE.model_dump(mode="json"),
                            "game_json_schema": AllocationGame.model_json_schema(),
                            "distribution": "PRISM-games (GPL-2.0) is not shipped with the platform; it runs as a "
                                            "separate, locally installed program (FAL_PRISM_GAMES_HOME)"}
    try:
        info.update(available=True, backend=version())
    except Unavailable as exc:
        info.update(available=False, reason=str(exc))
    return info


def _game_of(v: ModelVersion) -> dict[str, Any] | None:
    from formal_lab_solver_prism import GAME_SCHEMA, NAMESPACE

    ext = package_of(v).extensions.get(NAMESPACE)
    return ext.data if ext is not None and ext.schema_id == GAME_SCHEMA else None


def run(s: Session, version_id: str, body: dict[str, Any]) -> dict[str, Any]:
    from formal_lab_solver_prism import AllocationGame, Unavailable, check

    v = get_or_404(s, ModelVersion, version_id, "model version")
    raw = body.get("game") or _game_of(v)
    if raw is None:
        raise InvalidInput("no game: this model version has no org.formal-lab.prism-games extension; send one as "
                           "`game` (schema org.formal-lab.prism-games/allocation-game@1)")
    try:
        game = AllocationGame.model_validate(raw)
    except ValueError as exc:
        raise InvalidInput(f"game: {exc}") from exc
    try:
        record = check(game)
    except Unavailable as exc:
        raise Unsupported(str(exc)) from exc
    model = s.get(Model, v.model_id)
    row = CheckRow(id=f"pchk_{uuid.uuid4().hex[:20]}", project_id=model.project_id, model_version_id=v.id,
                   query={"kind": VERDICT, "backend": "prism-games", "game_id": game.game_id,
                          "properties": [p.property for p in record.properties],
                          "source": "request" if body.get("game") else "model version extension"},
                   result=record.model_dump(mode="json"), verdict=VERDICT)
    s.add(row)
    s.flush()
    return as_dict(row)


def as_dict(c: CheckRow) -> dict[str, Any]:
    return {"check_id": c.id, "model_version_id": c.model_version_id, "query": c.query, "record": c.result,
            "created_at": c.created_at.isoformat() if c.created_at else None}


def listing(s: Session, version_id: str) -> list[dict[str, Any]]:
    get_or_404(s, ModelVersion, version_id, "model version")
    return [as_dict(c) for c in s.scalars(select(CheckRow).where(
        CheckRow.model_version_id == version_id, CheckRow.verdict == VERDICT).order_by(CheckRow.created_at.desc()))]
