from __future__ import annotations

import ast
import importlib
from pathlib import Path


def _read(rel: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / rel).read_text(encoding="utf-8")


def _module_ast(rel: str) -> ast.AST:
    return ast.parse(_read(rel), filename=rel)


def _python_files_under(rel_dir: str) -> list[str]:
    root = Path(__file__).resolve().parents[2] / rel_dir
    return sorted(
        str(p.relative_to(Path(__file__).resolve().parents[2])) for p in root.rglob("*.py")
    )


def _imported_modules(tree: ast.AST) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.add(str(alias.name))
        elif isinstance(node, ast.ImportFrom):
            base = str(node.module or "")
            out.add(base)
            for alias in node.names:
                out.add(f"{base}.{alias.name}" if base else str(alias.name))
    return out


def _used_symbols(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    attrs: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            attrs.add(node.attr)
    return names | attrs


def test_schema_module_does_not_depend_on_client_mixins() -> None:
    imported = _imported_modules(_module_ast("lirix/core/evidence.py"))
    assert not any(mod.startswith("lirix._client_core") for mod in imported)


def test_failure_protocol_does_not_depend_on_client_mixins() -> None:
    imported = _imported_modules(_module_ast("lirix/core/failure_protocol.py"))
    assert not any(mod.startswith("lirix._client_core") for mod in imported)


def test_failure_protocol_projection_only_depends_on_contracts_projection_helpers() -> None:
    imported = _imported_modules(_module_ast("lirix/core/failure_protocol.py"))
    assert "lirix.core.contracts.build_failure_protocol_from_agent_feedback_projection" in imported
    assert "lirix.core.contracts.resolve_failure_protocol_to_agent_feedback_projection" in imported
    assert "lirix.core.constants.canonicalize_reason_code" not in imported
    assert "lirix.core.constants.canonicalize_failure_type" not in imported
    assert "lirix.core.canonical_taxonomy.lookup_reason_taxon" not in imported


def test_chain_adapter_does_not_import_config_resolver() -> None:
    imported = _imported_modules(_module_ast("lirix/core/chain_adapter.py"))
    assert "lirix.core.config_authority.resolve_config" not in imported
    assert "lirix.core.config.resolve_config" not in imported


def test_forensic_verifier_does_not_depend_on_session_private_symbols() -> None:
    imported = _imported_modules(_module_ast("lirix/core/forensic_verifier.py"))
    assert "lirix.core.session._is_hex_digest" not in imported


def test_forensic_verifier_symbol_usage_does_not_reference_session_private_digest_helpers() -> None:
    tree = _module_ast("lirix/core/forensic_verifier.py")
    symbols = _used_symbols(tree)
    assert "_is_hex_digest" not in symbols
    assert "_stable_digest" not in symbols


def test_runtime_contract_forensic_verifier_uses_contracts_digest_guards() -> None:
    mod = importlib.import_module("lirix.core.forensic_verifier")
    assert getattr(mod, "is_hex_digest", None) is not None
    assert mod.is_hex_digest("f" * 64) is True
    assert mod.is_hex_digest("x" * 64) is False


def test_contracts_module_does_not_depend_on_evidence_module() -> None:
    imported = _imported_modules(_module_ast("lirix/core/contracts.py"))
    assert "lirix.core.evidence" not in imported
    assert not any(mod.startswith("lirix.core.evidence.") for mod in imported)


def test_config_authority_does_not_import_client_core() -> None:
    imported = _imported_modules(_module_ast("lirix/core/config_authority.py"))
    assert not any(mod.startswith("lirix._client_core") for mod in imported)


def test_examples_and_tools_do_not_import_client_core_package() -> None:
    scanned = _python_files_under("examples") + _python_files_under("tools")
    violations: list[str] = []
    for rel in scanned:
        imports = _imported_modules(_module_ast(rel))
        if any(
            mod == "lirix._client_core" or mod.startswith("lirix._client_core.") for mod in imports
        ):
            violations.append(rel)
    assert not violations, f"direct _client_core imports are forbidden: {violations}"
