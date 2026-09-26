"""Programmatic Alembic entry point: `python -m formal_lab_api.migrate [upgrade|current|revision -m msg]`."""

from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from .settings import get_settings

HERE = Path(__file__).parent


def alembic_config(url: str | None = None) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(HERE / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url or get_settings().database_url)
    return cfg


def upgrade(url: str | None = None) -> None:
    command.upgrade(alembic_config(url), "head")


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv) or ["upgrade"]
    cfg = alembic_config()
    if args[0] == "upgrade":
        command.upgrade(cfg, args[1] if len(args) > 1 else "head")
    elif args[0] == "current":
        command.current(cfg, verbose=True)
    elif args[0] == "revision":
        message = args[args.index("-m") + 1] if "-m" in args else "change"
        command.revision(cfg, message=message, autogenerate=True)
    elif args[0] == "downgrade":
        command.downgrade(cfg, args[1] if len(args) > 1 else "-1")
    else:
        raise SystemExit(f"unknown migrate command {args[0]}")


if __name__ == "__main__":
    main()
