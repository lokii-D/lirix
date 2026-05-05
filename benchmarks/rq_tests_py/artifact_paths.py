from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


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


def lirix_repo_root() -> Path:
    """`benchmarks/rq_tests_py/artifact_paths.py` → Lirix repo root."""
    return Path(__file__).resolve().parents[2]


def tdsc_rq_tests_root(rq_index: int) -> Path:
    return lirix_repo_root() / "tdsc" / f"rq{rq_index}_tests"


def resolve_tdsc_rq_layout(rq_index: int) -> ArtifactLayout:
    """Branch/run root under ``tdsc/rq{N}_tests`` (format subdirs live inside output_dir)."""
    return resolve_artifact_layout(tdsc_rq_tests_root(rq_index))


def relpaths_under(root: Path, paths: Iterable[Path]) -> list[str]:
    return [path.relative_to(root).as_posix() for path in paths]


def newest_file_named(root: Path, filename: str) -> Path | None:
    if not root.exists():
        return None
    hits = list(root.rglob(filename))
    if not hits:
        return None
    return max(hits, key=lambda p: p.stat().st_mtime)
