from __future__ import annotations

import ast
from pathlib import Path


def _read(rel: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / rel).read_text(encoding="utf-8")


def _module_ast(rel: str) -> ast.AST:
    return ast.parse(_read(rel), filename=rel)


def _contains_agent_feedback_dataclass_usage(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "AgentFeedbackEnvelope":
            return True
        if isinstance(node, ast.Attribute) and node.attr == "AgentFeedbackEnvelope":
            return True
    return False


def test_business_paths_do_not_use_agent_feedback_dataclass_directly() -> None:
    root = Path(__file__).resolve().parents[2]
    business_paths = ["lirix/core/failure_protocol.py"] + sorted(
        str(p.relative_to(root)) for p in (root / "lirix" / "_client_core").rglob("*.py")
    )
    violations: list[str] = []
    for rel in business_paths:
        tree = _module_ast(rel)
        if _contains_agent_feedback_dataclass_usage(tree):
            violations.append(rel)
    assert not violations, (
        "AgentFeedbackEnvelope dataclass must not be used in business paths; "
        f"use lirix.core.contracts builders instead: {violations}"
    )


def test_evidence_module_still_declares_agent_feedback_dataclass() -> None:
    tree = _module_ast("lirix/core/evidence.py")
    class_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    assert "AgentFeedbackEnvelope" in class_names
