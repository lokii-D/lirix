#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import tempfile
from contextlib import suppress
from pathlib import Path

from huggingface_hub import HfApi

SPACE_README = """---
title: Lirix
emoji: 🛡️
colorFrom: blue
colorTo: indigo
sdk: docker
app_file: app.py
pinned: false
license: mit
---

# Lirix

Lirix is a fail-closed validation and simulation control plane for AI
agent payloads that may touch EVM value flows.

## What this Space does

This Hugging Face Space runs the Lirix demo application with the
Docker-based setup defined in this repository.
"""


def build_staging(root: Path) -> Path:
    staging = Path(tempfile.mkdtemp(prefix="lirix-space-"))
    skip = {".git", ".github", ".cursor", "terminals"}

    for item in root.iterdir():
        if item.name in skip:
            continue
        dest = staging / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)

    (staging / "README.md").write_text(SPACE_README, encoding="utf-8")
    return staging


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
    with suppress(Exception):
        api.create_repo(
            repo_id=repo_id,
            repo_type="space",
            space_sdk="docker",
            exist_ok=True,
            private=False,
        )
    api.upload_folder(
        folder_path=str(staging),
        repo_id=repo_id,
        repo_type="space",
        commit_message="sync: update from GitHub Actions",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
