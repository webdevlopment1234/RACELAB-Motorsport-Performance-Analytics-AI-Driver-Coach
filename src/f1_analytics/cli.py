"""f1-analytics console commands.

Available commands:

    data-status     Show which data files are present and how to obtain
                    any that are missing (never modifies the filesystem).
    validate-data   Run the full data validation / drift suite.
    models-status   Dry-run readiness check for all model artifacts (does
                    not train anything).
    train           Train finish / dnf / podium / winner artifacts and write
                    them to models/ (or F1_MODELS_DIR).
    doctor          data-status + models-status + source summary in one shot.

Examples
--------
    f1-analytics data-status      # is my data ready?
    f1-analytics models-status    # are my models ready?
    f1-analytics train            # train all model artifacts
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def _print_header(title: str) -> None:
    print(f"\n=== {title} ===")


def cmd_data_status(_: argparse.Namespace) -> int:
    from .data import asset_status
    _print_header("Data readiness")
    rows = []
    bad = 0
    for asset in asset_status().values():
        state = "ok" if asset.ok else "MISSING"
        flag = " " if asset.ok else "!"
        print(f"[{state}] {asset.name}")
        print(f"          path: {asset.path}")
        print(f"          role: {asset.role}")
        if not asset.ok:
            bad += 1
            print(f"          fix:  {asset.fix}")
        rows.append({"asset": asset.name, "ok": asset.ok, "path": str(asset.path)})
    print(f"\n{len(rows) - bad} present, {bad} missing.")
    return 0


def cmd_validate_data(_: argparse.Namespace) -> int:
    from .preprocessing import run_all_validations
    _print_header("Data validation & drift")
    failed = 0
    for report in run_all_validations():
        print(f"- {report.source}: {len(report.checks)} checks, "
              f"{len(report.failures)} failures, {len(report.warnings)} warnings")
        for check in report.checks:
            mark = {"ok": "ok", "warn": "~", "fail": "FAIL"}[check.status]
            print(f"    [{mark}] {check.name}: {check.message}")
        if report.failures:
            failed += len(report.failures)
    print(f"\n{failed} failing checks." if failed else "\nAll data checks passed.")
    return 1 if failed else 0


def cmd_models_status(args: argparse.Namespace) -> int:
    from .models import models_status
    _print_header("Model artifacts")
    status = models_status(args.directory)
    for task, info in status["models"].items():
        if info["ok"]:
            print(f"[ok]   {task}: {info['path']}")
            print(f"        inputs={len(info['input_columns'])} data_version={info['data_version']} "
                  f"split={info['split']} seed={info['seed']}")
        else:
            print(f"[FAIL] {task}: {info['error']}")
    if not status["ok"]:
        print("\nModels are not ready. Train them with: f1-analytics train")
    else:
        print("\nAll model artifacts are ready and schema-compatible.")
    return 0 if status["ok"] else 1


def cmd_train(args: argparse.Namespace) -> int:
    from .data import asset_status
    from .models import models_status, train_all_years

    parquet = asset_status()["training_dataset.parquet"]
    if not parquet.ok:
        print("Cannot train: training_dataset.parquet is missing.")
        print(f"  expected at: {parquet.path}")
        return 1

    directory = args.directory
    _print_header("Training models")
    print(f"Writing artifacts to: {directory or 'models/'}")
    artifacts = train_all_years(output_dir=directory, save=True)
    for artifact in artifacts:
        print(f"  {artifact.task}: trained ({len(artifact.input_columns)} inputs, "
              f"split={artifact.split}, seed={artifact.seed})")
        print(f"      metrics: {json.dumps(artifact.metrics, default=str)}")

    status = models_status(directory)
    _print_header("Verification")
    for task, info in status["models"].items():
        print(f"[{'ok' if info['ok'] else 'FAIL'}] {task}: "
              f"{'validated' if info['ok'] else info['error']}")
    return 0 if status["ok"] else 1


def cmd_doctor(_: argparse.Namespace) -> int:
    code1 = cmd_data_status(argparse.Namespace())
    _source_summary()
    code2 = cmd_models_status(argparse.Namespace(directory=None))
    return 0 if (code1 == 0 and code2 == 0) else 1


def _source_summary() -> tuple[str, dict[str, Any]]:
    from .database import data_source
    src = data_source()
    if src["mode"] == "sqlite":
        print(f"Query source: SQLite ({src['db_path']})")
    else:
        print("Query source: CSV fallback (read-only, in-memory, 1950-2024)")
        print(f"  note: {src['note']}")
    return src["mode"], src


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="f1-analytics", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("data-status", help="show data file status (never modifies files)")
    sub.add_parser("validate-data", help="run the full data validation/drift suite")
    m = sub.add_parser("models-status", help="dry-run readiness check for model artifacts")
    m.add_argument("--directory", default=None, help="models directory (default: models/)")
    t = sub.add_parser("train", help="train all model artifacts")
    t.add_argument("--directory", default=None, help="output models directory (default: models/)")
    sub.add_parser("doctor", help="data-status + models-status + query-source summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {
        "data-status": cmd_data_status,
        "validate-data": cmd_validate_data,
        "models-status": cmd_models_status,
        "train": cmd_train,
        "doctor": cmd_doctor,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())