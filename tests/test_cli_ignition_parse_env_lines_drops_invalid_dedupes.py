from __future__ import annotations

import pytest
from lirix.cli import _merge_env_defaults, _parse_env_lines, build_parser


def test_test_v15_cli_ignition_parse_env_lines_drops_invalid_dedupes() -> None:
    lines = _parse_env_lines("# comment\nBAD KEY=1\nA=1\nA=2\nB=3\n")
    assert lines == [(None, "# comment"), (None, "BAD KEY=1"), ("A", "A=2"), ("B", "B=3")]


def test_test_v15_cli_ignition_parse_env_lines_drops_invalid_dedupes_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["nope"])


def test_test_v15_cli_ignition_parse_env_lines_drops_invalid_dedupes_3(tmp_path) -> None:
    p = tmp_path / ".env"
    p.write_text('LIRIX_RPC_URLS="x"\n', encoding="utf-8")
    _merge_env_defaults(p, force=False)
    assert 'LIRIX_RPC_URLS="x"' in p.read_text(encoding="utf-8")
