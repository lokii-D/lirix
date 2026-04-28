from __future__ import annotations

import ast
from pathlib import Path

from lirix.cli import main


def test_cli_init_preserves_existing_env_and_appends_lirix_defaults(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=123\n", encoding="utf-8")

    exit_code = main(["init", "--dir", str(tmp_path)])

    assert exit_code == 0
    env_text = env_path.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=123" in env_text
    assert 'LIRIX_RPC_URLS="url1,url2,url3"' in env_text
    assert "LIRIX_BFT_THRESHOLD=2" in env_text
    assert "LIRIX_MAX_PROXY_DEPTH=3" in env_text


def test_init_env_no_duplicates(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        'LIRIX_RPC_URLS="custom-a,custom-b"\nLIRIX_BFT_THRESHOLD=7\nLIRIX_MAX_PROXY_DEPTH=8\n',
        encoding="utf-8",
    )

    exit_code = main(["init", "--dir", str(tmp_path)])
    env_text = env_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert env_text.count("LIRIX_RPC_URLS=") == 1
    assert env_text.count("LIRIX_BFT_THRESHOLD=") == 1
    assert env_text.count("LIRIX_MAX_PROXY_DEPTH=") == 1
    assert 'LIRIX_RPC_URLS="custom-a,custom-b"' in env_text
    assert "LIRIX_BFT_THRESHOLD=7" in env_text
    assert "LIRIX_MAX_PROXY_DEPTH=8" in env_text


def test_cli_init_is_idempotent_for_generated_python_files(tmp_path: Path) -> None:
    first_exit_code = main(["init", "--dir", str(tmp_path)])
    policy_before = (tmp_path / "lirix_policy.py").read_text(encoding="utf-8")
    agent_before = (tmp_path / "agent_entry.py").read_text(encoding="utf-8")

    second_exit_code = main(["init", "--dir", str(tmp_path)])
    policy_after = (tmp_path / "lirix_policy.py").read_text(encoding="utf-8")
    agent_after = (tmp_path / "agent_entry.py").read_text(encoding="utf-8")

    assert first_exit_code == 0
    assert second_exit_code == 0
    assert policy_before == policy_after
    assert agent_before == agent_after


def test_init_force_flag(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    main(["init", "--dir", str(tmp_path)])

    (tmp_path / "lirix_policy.py").write_text("# user modified\n", encoding="utf-8")
    (tmp_path / "agent_entry.py").write_text("# broken\n", encoding="utf-8")
    env_path.write_text(
        'OPENAI_API_KEY=123\nLIRIX_RPC_URLS="wrong"\nLIRIX_BFT_THRESHOLD=99\nLIRIX_MAX_PROXY_DEPTH=77\n',
        encoding="utf-8",
    )

    exit_code = main(["init", "--dir", str(tmp_path), "--force"])

    assert exit_code == 0
    assert (tmp_path / "lirix_policy.py").read_text(encoding="utf-8") != "# user modified\n"
    assert (tmp_path / "agent_entry.py").read_text(encoding="utf-8") != "# broken\n"
    env_text = env_path.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY=123" in env_text
    assert 'LIRIX_RPC_URLS="url1,url2,url3"' in env_text
    assert "LIRIX_BFT_THRESHOLD=2" in env_text
    assert "LIRIX_MAX_PROXY_DEPTH=3" in env_text


def test_cli_init_deduplicates_lirix_env_keys_keeping_last_value(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        'LIRIX_RPC_URLS="first"\n'
        'LIRIX_RPC_URLS="second"\n'
        "OPENAI_API_KEY=123\n"
        "LIRIX_BFT_THRESHOLD=1\n"
        "LIRIX_BFT_THRESHOLD=9\n",
        encoding="utf-8",
    )

    exit_code = main(["init", "--dir", str(tmp_path)])
    env_text = env_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert env_text.count("LIRIX_RPC_URLS=") == 1
    assert env_text.count("LIRIX_BFT_THRESHOLD=") == 1
    assert 'LIRIX_RPC_URLS="second"' in env_text
    assert "LIRIX_BFT_THRESHOLD=9" in env_text
    assert "OPENAI_API_KEY=123" in env_text
    assert "LIRIX_MAX_PROXY_DEPTH=3" in env_text


def test_init_missing_env_creation(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"

    exit_code = main(["init", "--dir", str(tmp_path)])

    assert exit_code == 0
    assert env_path.exists()
    env_text = env_path.read_text(encoding="utf-8")
    assert 'LIRIX_RPC_URLS="url1,url2,url3"' in env_text
    assert "LIRIX_BFT_THRESHOLD=2" in env_text
    assert "LIRIX_MAX_PROXY_DEPTH=3" in env_text


def test_cli_init_generates_syntax_valid_agent_entry(tmp_path: Path) -> None:
    exit_code = main(["init", "--dir", str(tmp_path)])
    generated = (tmp_path / "agent_entry.py").read_text(encoding="utf-8")
    policy_text = (tmp_path / "lirix_policy.py").read_text(encoding="utf-8")

    assert exit_code == 0
    ast.parse(generated)
    assert "from typing import List, Optional" in policy_text
    assert "from typing import Dict, List, Optional" in generated
