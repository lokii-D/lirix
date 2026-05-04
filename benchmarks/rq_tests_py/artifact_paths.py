from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArtifactLayout:
    base_dir: Path
    branch_slug: str
    run_number: int

    @property
    def run_slug(self) -> str:
        return f"run-{self.run_number:03d}"

    @property
    def output_dir(self) -> Path:
        return self.base_dir / self.branch_slug / "runs" / self.run_slug


_BRANCH_FALLBACK = os.getenv("LIRIX_BENCHMARK_BRANCH", "local")


def _git_branch_name() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return _BRANCH_FALLBACK
    branch = result.stdout.strip() or _BRANCH_FALLBACK
    if branch == "HEAD":
        return _BRANCH_FALLBACK
    return branch


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-")
    return slug.lower() or "local"


def _next_run_number(base_dir: Path, branch_slug: str) -> int:
    runs_dir = base_dir / branch_slug / "runs"
    if not runs_dir.exists():
        return 1
    max_id = 0
    for child in runs_dir.iterdir():
        match = re.fullmatch(r"run-(\d{3})", child.name)
        if match:
            max_id = max(max_id, int(match.group(1)))
    return max_id + 1


def resolve_artifact_layout(base_dir: Path) -> ArtifactLayout:
    branch_slug = _slugify(_git_branch_name())
    run_number = _next_run_number(base_dir, branch_slug)
    layout = ArtifactLayout(base_dir=base_dir, branch_slug=branch_slug, run_number=run_number)
    layout.output_dir.mkdir(parents=True, exist_ok=True)
    return layout
