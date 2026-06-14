#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from huggingface_hub import HfApi
from huggingface_hub.errors import RepositoryNotFoundError

SPACE_README = """---
title: Lirix
emoji: 🛡️
colorFrom: blue
colorTo: indigo
sdk: streamlit
app_file: mantle_TT/app.py
pinned: false
license: mit
---

# Lirix

Lirix is a fail-closed validation and simulation control plane for AI
agent payloads that may touch EVM value flows.

## What this Space does

This Hugging Face Space runs the Lirix demo application with the
smallest practical runtime surface.
"""

# Minimal runtime-only surface for the Space.
SYNC_FILES = [
    "mantle_TT/app.py",
    "requirements_submission.txt",
]


def _copy_file(root: Path, staging: Path, relative_path: str) -> None:
    src = root / relative_path
    if not src.exists():
        return
    dest = staging / relative_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def build_staging(root: Path) -> Path:
    staging = Path(tempfile.mkdtemp(prefix="lirix-space-"))

    for relative_path in SYNC_FILES:
        _copy_file(root, staging, relative_path)

    (staging / "README.md").write_text(SPACE_README, encoding="utf-8")
    return staging


def upload_space(api: HfApi, staging: Path, repo_id: str) -> None:
    api.upload_folder(
        folder_path=str(staging),
        repo_id=repo_id,
        repo_type="space",
        commit_message="sync: update from GitHub Actions",
    )


def main() -> int:
    token = os.environ.get("HF_TOKEN", "").strip()
    repo_id = os.environ.get("HF_SPACE_REPO", "").strip()
    if not token:
        raise SystemExit("HF_TOKEN is required")
    if not repo_id:
        raise SystemExit("HF_SPACE_REPO is required")

    root = Path(__file__).resolve().parents[1]
    staging = build_staging(root)
    api = HfApi(token=token)

    try:
        upload_space(api, staging, repo_id)
    except RepositoryNotFoundError:
        api.create_repo(
            repo_id=repo_id,
            repo_type="space",
            space_sdk="docker",
            exist_ok=True,
            private=False,
        )
        upload_space(api, staging, repo_id)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
