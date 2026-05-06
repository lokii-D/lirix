from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

LOGGER = logging.getLogger("lirix.cli")
ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

ENV_DEFAULTS: Dict[str, str] = {
    "LIRIX_RPC_URLS": '"url1,url2,url3"',
    "LIRIX_BFT_THRESHOLD": "2",
    "LIRIX_MAX_PROXY_DEPTH": "3",
}

POLICY_TEMPLATE = """from typing import List, Optional

from lirix.layers import ShadowPolicySchema


FORBIDDEN_METHODS: List[str] = ["approve", "setApprovalForAll"]
ALLOWED_TARGET_CONTRACTS: Optional[List[str]] = None


DEFAULT_STRICT_POLICY = ShadowPolicySchema(
    max_slippage_bps=50,
    allowed_target_contracts=ALLOWED_TARGET_CONTRACTS or "ANY",
    forbidden_methods=FORBIDDEN_METHODS,
)
"""

AGENT_TEMPLATE = """from __future__ import annotations

import os
from typing import Dict, List, Optional
from typing import cast

from lirix.integrations.autogen.tool import lirix_validate_intent
from lirix.integrations.langchain import LirixSecurityValidator

from lirix_policy import DEFAULT_STRICT_POLICY  # type: ignore[import-not-found]


def _rpc_urls() -> List[str]:
    raw = os.getenv("LIRIX_RPC_URLS", "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _security_policy() -> Dict[str, object]:
    result = DEFAULT_STRICT_POLICY.model_dump(mode="python")
    return cast(Dict[str, object], result)


VALIDATOR = LirixSecurityValidator(
    rpc_urls=_rpc_urls(),
    default_intent="swap",
    security_policy=_security_policy(),
)


def run_langchain_dummy_agent(user_prompt: str) -> str:
    \"\"\"Minimal agent loop stub for LangChain-style tool invocation.\"\"\"
    return VALIDATOR._run(user_prompt, intent="swap")


def run_autogen_dummy_agent(user_prompt: str, intent: Optional[str] = None) -> str:
    \"\"\"Minimal AutoGen-style tool bridge using the same strict policy.\"\"\"
    return lirix_validate_intent(
        raw_intent_or_calldata=user_prompt,
        rpc_urls=_rpc_urls(),
        intent=intent or "swap",
        security_policy=_security_policy(),
    )


def main() -> None:
    sample_prompt = "swap 1 ETH for USDC on Uniswap"
    print(run_langchain_dummy_agent(sample_prompt))


if __name__ == "__main__":
    main()
"""


def _parse_env_lines(text: str) -> List[Tuple[Optional[str], str]]:
    parsed_lines: List[Tuple[Optional[str], str]] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw_line:
            parsed_lines.append((None, raw_line))
            continue
        key, _value = raw_line.split("=", 1)
        normalized_key = key.strip()
        if not ENV_KEY_RE.match(normalized_key):
            parsed_lines.append((None, raw_line))
            continue
        parsed_lines.append((normalized_key, raw_line))

    deduplicated: List[Tuple[Optional[str], str]] = []
    seen_keys: set[str] = set()
    for parsed_key, raw_line in reversed(parsed_lines):
        dedupe_key = parsed_key
        if dedupe_key is not None:
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
        deduplicated.append((dedupe_key, raw_line))
    deduplicated.reverse()
    return deduplicated


def _merge_env_defaults(env_path: Path, *, force: bool) -> None:
    existing_text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    parsed_lines = _parse_env_lines(existing_text)
    existing_keys = {key for key, _raw_line in parsed_lines if key is not None}
    updated_lines: List[str] = []
    touched_keys: List[str] = []

    for key, raw_line in parsed_lines:
        if key in ENV_DEFAULTS and force:
            updated_lines.append(f"{key}={ENV_DEFAULTS[key]}")
            touched_keys.append(key)
            continue
        updated_lines.append(raw_line)

    missing_keys = [key for key in ENV_DEFAULTS if key not in existing_keys]
    for key in missing_keys:
        updated_lines.append(f"{key}={ENV_DEFAULTS[key]}")
        touched_keys.append(key)

    if not touched_keys:
        LOGGER.info("Skipping .env merge; all Lirix keys already exist.")
        return

    env_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(updated_lines) + "\n"
    env_path.write_text(content, encoding="utf-8")
    if force:
        LOGGER.info("Force-updated Lirix keys in .env.")
    else:
        LOGGER.info("Merged missing Lirix keys into .env.")


def _write_scaffold(path: Path, content: str, *, force: bool) -> None:
    if path.exists() and not force:
        LOGGER.warning("Skipping existing file: %s", path.name)
        return
    path.write_text(content, encoding="utf-8")
    if force:
        LOGGER.info("Force-generated %s.", path.name)
    else:
        LOGGER.info("Generated %s.", path.name)


def scaffold_init(target_dir: Path, *, force: bool = False) -> List[Path]:
    generated: list[Path] = []
    env_path = target_dir / ".env"
    _merge_env_defaults(env_path, force=force)

    for filename, content in (
        ("lirix_policy.py", POLICY_TEMPLATE),
        ("agent_entry.py", AGENT_TEMPLATE),
    ):
        path = target_dir / filename
        existed = path.exists()
        _write_scaffold(path, content, force=force)
        if (force or not existed) and path.exists():
            generated.append(path)
    return generated


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lirix", description="Lirix DX scaffold CLI.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser(
        "init",
        help="Generate idempotent Lirix starter files in the current directory.",
    )
    init_parser.add_argument(
        "--dir",
        default=".",
        help="Target directory for scaffold output. Defaults to the current working directory.",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite generated Lirix files and refresh Lirix-managed .env keys.",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "init":
        scaffold_init(Path(args.dir).resolve(), force=args.force)
        return 0
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
