from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from lirix.cli import build_parser, main, scaffold_init

# Frozen public CLI subcommands (must stay aligned with README quickstart `lirix <cmd>`).
_EXPECTED_CLI_SUBCOMMANDS: tuple[str, ...] = ("init",)


def test_cli_parser_exposes_init_subcommand() -> None:
    parser = build_parser()
    args = parser.parse_args(["init", "--dir", "."])
    assert args.command == "init"
    assert args.dir == "."


def test_frozen_cli_subcommands_match_parser() -> None:
    """Guard against accidental subcommand drift vs README / packaging expectations."""
    parser = build_parser()
    names: list[str] = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction) and action.choices is not None:
            names = sorted(action.choices.keys())
            break
    assert tuple(names) == tuple(sorted(_EXPECTED_CLI_SUBCOMMANDS))


def test_readme_documents_lirix_init_in_en_and_zh_sections() -> None:
    """README bilingual quickstart must keep the `lirix init` one-liner in sync with the CLI."""
    readme = Path(__file__).resolve().parents[2] / "README.md"
    text = readme.read_text(encoding="utf-8")
    assert text.count("lirix init") >= 2


def test_scaffold_init_writes_expected_files(tmp_path: Path) -> None:
    generated = scaffold_init(tmp_path, force=True)
    names = {p.name for p in generated}
    assert "lirix_policy.py" in names
    assert "agent_entry.py" in names
    assert (tmp_path / ".env").exists()


def test_main_init_zero_exit(tmp_path: Path) -> None:
    assert main(["init", "--dir", str(tmp_path), "--force"]) == 0


def test_console_script_entrypoint_smoke(tmp_path: Path) -> None:
    """``python -m lirix.cli`` mirrors installed ``lirix`` console_script."""
    repo_root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "PYTHONPATH": str(repo_root)}
    out_dir = tmp_path / "scaffold_out"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "lirix.cli",
            "init",
            "--dir",
            str(out_dir),
            "--force",
        ],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
