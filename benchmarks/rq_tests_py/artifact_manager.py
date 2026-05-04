from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from shutil import copy2
from typing import Iterable


@dataclass(frozen=True)
class ArtifactFamily:
    name: str
    output_dir: Path


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-")
    return slug.lower() or "local"


def _git_branch_name() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return _slugify(os.getenv("LIRIX_BENCHMARK_BRANCH", "local"))
    branch = result.stdout.strip() or os.getenv("LIRIX_BENCHMARK_BRANCH", "local")
    if branch == "HEAD":
        branch = os.getenv("LIRIX_BENCHMARK_BRANCH", "local")
    return _slugify(branch)


def _next_run_name(runs_dir: Path) -> str:
    runs_dir.mkdir(parents=True, exist_ok=True)
    existing = []
    for child in runs_dir.iterdir():
        if child.is_dir() and child.name.startswith("run-"):
            try:
                existing.append(int(child.name.split("-", 1)[1]))
            except ValueError:
                continue
    next_id = max(existing, default=0) + 1
    return f"run-{next_id:03d}"


def archive_artifacts(family: ArtifactFamily, artifact_names: Iterable[str]) -> Path:
    """Copy refreshed artifacts into `<branch>/runs/run-###/` folders."""

    branch_dir = family.output_dir / _git_branch_name()
    branch_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = branch_dir / "runs"
    run_dir = runs_dir / _next_run_name(runs_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    for artifact_name in artifact_names:
        source = family.output_dir / artifact_name
        if source.exists():
            copy2(source, run_dir / artifact_name)
    return run_dir
