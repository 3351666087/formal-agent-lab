#!/usr/bin/env python3
"""Local platform data: backup, restore, reset, status (P2-108).

A backup is one directory with
  database.sql      pg_dump of the platform database (plain SQL, taken inside the fal-dev PostgreSQL container)
  artifacts.tar.gz  the local artifact store (FAL_ARTIFACT_ROOT, default ./var/artifacts)
  backup.json       what was saved: database, alembic revision, row counts, artifact files, source revision, time

    python scripts/local_data.py backup  --out var/backups/2026-09-27        [--database fal]
    python scripts/local_data.py restore --from var/backups/2026-09-27       [--database fal] --yes
    python scripts/local_data.py reset   [--database fal] --yes               (empty database + artifacts, migrated)
    python scripts/local_data.py status  [--database fal]

Restore and reset replace the database's contents and the artifact store; they refuse without --yes. Temporal's own
state (running workflows) is not part of a backup: restore when no run is in flight; interrupted runs are resumed by
starting their workflows again (the database holds their state). The S3 artifact backend (compose / Helm) is backed
up with the store's own tools; this script covers the local-development profile.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PG = ["docker", "compose", "-p", "fal-dev", "-f", str(ROOT / "deploy/compose/services.dev.yaml"), "exec", "-T",
      "postgres"]
TABLES = ["projects", "model_versions", "scenarios", "runs", "run_events", "operation_records", "model_releases",
          "regression_cases", "matrices", "matrix_cells", "artifacts"]


def artifact_root() -> Path:
    return Path(os.environ.get("FAL_ARTIFACT_ROOT", str(ROOT / "var" / "artifacts"))).resolve()


def psql(db: str, sql: str) -> str:
    res = subprocess.run([*PG, "psql", "-U", "fal", "-d", db, "-At", "-c", sql], capture_output=True, text=True)
    if res.returncode != 0:
        raise SystemExit(f"psql failed: {res.stderr.strip()}")
    return res.stdout.strip()


def counts(db: str) -> dict[str, int]:
    out = {}
    for t in TABLES:
        try:
            out[t] = int(psql(db, f"select count(*) from {t}") or 0)
        except SystemExit:
            out[t] = -1
    return out


def status(db: str) -> dict:
    root = artifact_root()
    files = [p for p in root.rglob("*") if p.is_file()] if root.exists() else []
    return {"database": db, "alembic_revision": psql(db, "select version_num from alembic_version"),
            "rows": counts(db), "artifact_root": str(root), "artifact_files": len(files),
            "artifact_bytes": sum(p.stat().st_size for p in files)}


def backup(db: str, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    with (out / "database.sql").open("wb") as fh:
        res = subprocess.run([*PG, "pg_dump", "-U", "fal", "--clean", "--if-exists", "--no-owner", db], stdout=fh,
                             stderr=subprocess.PIPE)
    if res.returncode != 0:
        raise SystemExit(f"pg_dump failed: {res.stderr.decode()[:500]}")
    root = artifact_root()
    with tarfile.open(out / "artifacts.tar.gz", "w:gz") as tar:
        if root.exists():
            tar.add(root, arcname="artifacts")
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    info = {**status(db), "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source_revision": rev,
            "files": {p.name: p.stat().st_size for p in out.iterdir() if p.is_file()}}
    (out / "backup.json").write_text(json.dumps(info, indent=2) + "\n")
    return info


def restore(db: str, src: Path) -> dict:
    info = json.loads((src / "backup.json").read_text())
    with (src / "database.sql").open("rb") as fh:
        res = subprocess.run([*PG, "psql", "-U", "fal", "-d", db, "-q", "-v", "ON_ERROR_STOP=1"], stdin=fh,
                             capture_output=True)
    if res.returncode != 0:
        raise SystemExit(f"restore failed: {res.stderr.decode()[:500]}")
    root = artifact_root()
    if root.exists():
        subprocess.run(["rm", "-rf", str(root)], check=True)
    root.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(src / "artifacts.tar.gz") as tar:
        tar.extractall(root.parent, filter="data")
    extracted = root.parent / "artifacts"
    if extracted != root and extracted.exists():
        extracted.rename(root)
    now = status(db)
    same = now["rows"] == info["rows"] and now["artifact_files"] == info["artifact_files"]
    return {"restored_from": str(src), "matches_backup": same, "backup": info["rows"], "now": now["rows"],
            "artifacts": [info["artifact_files"], now["artifact_files"]]}


def reset(db: str) -> dict:
    psql(db, "drop schema public cascade; create schema public;")
    root = artifact_root()
    if root.exists():
        subprocess.run(["rm", "-rf", str(root)], check=True)
    subprocess.run([sys.executable, "-m", "formal_lab_api.migrate", "upgrade"], cwd=ROOT, check=True,
                   env={**os.environ, "FAL_DATABASE_URL": f"postgresql+psycopg://fal:fal@127.0.0.1:5432/{db}"})
    return status(db)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["backup", "restore", "reset", "status"])
    ap.add_argument("--database", default="fal")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--from", dest="src", type=Path)
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    if a.command in ("restore", "reset") and not a.yes:
        print(f"{a.command} replaces the contents of database {a.database!r} and {artifact_root()}; pass --yes")
        return 2
    if a.command == "backup":
        out = a.out or ROOT / "var" / "backups" / time.strftime("%Y%m%d-%H%M%S")
        result = backup(a.database, out)
    elif a.command == "restore":
        if not a.src:
            raise SystemExit("--from is required")
        result = restore(a.database, a.src)
    elif a.command == "reset":
        result = reset(a.database)
    else:
        result = status(a.database)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
