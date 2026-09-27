"""Import an Inspect evaluation into the platform.

    python -m formal_lab_eval.inspect_import var/inspect/logs/<log>.eval --project 生产调度示例

Archives the .eval log as a project artifact, imports each sample's replay bundle as a run, and groups the runs
in a matrix (source=inspect) so the platform's report and Web UI show them next to platform-run matrices.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from formal_lab_sdk import Client

from .inspect_adapter import bundle_paths_from_log, metric_results_from_log, read_log


def import_log(client: Client, project: str, log_path: Path) -> dict:
    log = read_log(log_path)
    project_id = client.find_project(project)["id"]
    bundles = bundle_paths_from_log(log)
    scores = metric_results_from_log(log)
    run_ids = []
    for _sample_id, path in sorted(bundles.items()):
        run = client.import_bundle(project_id, Path(path).read_bytes())
        run_ids.append(run["id"])
    matrix = client.create_imported_matrix(
        project_id, name=f"inspect: {log.eval.task}", run_ids=run_ids, source="inspect",
        spec={"inspect": {"task": log.eval.task, "model": log.eval.model, "created": log.eval.created,
                          "status": log.status, "samples": len(log.samples or []),
                          "log_file": log_path.name, "note": "model not used for decisions by rule/z3 strategies"}})
    ref = client.upload_artifact(project_id, log_path.read_bytes(), name=log_path.name, kind="inspect_log",
                                 format_version="inspect_ai/eval-log", matrix_id=matrix["id"])
    return {"matrix_id": matrix["id"], "runs": run_ids, "log_artifact": ref["digest"]["value"],
            "samples_with_scores": len(scores)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--project", required=True)
    parser.add_argument("--api", default=None)
    args = parser.parse_args()
    client = Client(args.api) if args.api else Client()
    print(json.dumps(import_log(client, args.project, args.log), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
