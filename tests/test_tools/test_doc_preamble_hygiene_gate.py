from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run_gate(
    root: Path, rel_paths: list[str], *, enforce: bool = True, quiet: bool = False
) -> subprocess.CompletedProcess[str]:
    tool = root / "tools" / "harness.py"
    cmd = [sys.executable, str(tool), "doc-preamble-hygiene"]
    if enforce:
        cmd.append("--enforce")
    if quiet:
        cmd.append("--quiet")
    cmd.extend(rel_paths)
    return subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )


def test_doc_preamble_hygiene_gate_valid_fixture_passes() -> None:
    root = Path(__file__).resolve().parents[2]
    rel = "tests/fixtures/doc_preamble/valid_preamble.md"
    proc = _run_gate(root, [rel], enforce=True, quiet=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_doc_preamble_hygiene_gate_zh_before_en_fails() -> None:
    root = Path(__file__).resolve().parents[2]
    rel = "tests/fixtures/doc_preamble/bad_zh_before_en.md"
    proc = _run_gate(root, [rel], enforce=True)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "first `## 中文`" in proc.stderr


def test_doc_preamble_hygiene_gate_ch_label_before_en_fails() -> None:
    root = Path(__file__).resolve().parents[2]
    rel = "tests/fixtures/doc_preamble/bad_ch_label_before_en.md"
    proc = _run_gate(root, [rel], enforce=True)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "**中文：**" in proc.stderr


def test_doc_preamble_hygiene_gate_cjk_before_en_fails() -> None:
    root = Path(__file__).resolve().parents[2]
    rel = "tests/fixtures/doc_preamble/bad_cjk_before_en.md"
    proc = _run_gate(root, [rel], enforce=True)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "CJK" in proc.stderr


def test_doc_preamble_hygiene_gate_warn_only_default_exits_zero_on_violation() -> None:
    root = Path(__file__).resolve().parents[2]
    rel = "tests/fixtures/doc_preamble/bad_cjk_before_en.md"
    proc = _run_gate(root, [rel], enforce=False, quiet=False)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "CJK" in proc.stderr
