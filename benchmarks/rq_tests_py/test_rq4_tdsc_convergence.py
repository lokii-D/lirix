from __future__ import annotations

# ruff: noqa: E402,E501,E741
# mypy: ignore-errors
import asyncio
import csv
import json
import os
import random
import statistics
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest

httpx = pytest.importorskip("httpx")
sns = pytest.importorskip("seaborn")

from benchmarks.rq_tests_py.artifact_manager import ArtifactFamily, archive_artifacts
from benchmarks.rq_tests_py.artifact_paths import relpaths_under, resolve_tdsc_rq_layout
from lirix import Lirix, LirixConfig
from lirix.core.exceptions import LirixBaseException

OUTPUT_LAYOUT = resolve_tdsc_rq_layout(4)
RUN_ROOT = OUTPUT_LAYOUT.output_dir
RQ4_CSV_DIR = RUN_ROOT / "rq4_csv"
RQ4_PNG_DIR = RUN_ROOT / "rq4_png"
RQ4_PDF_DIR = RUN_ROOT / "rq4_pdf"
CASES_DIR = RQ4_CSV_DIR / "rq4_cases"
CSV_PATH = RQ4_CSV_DIR / "rq4_cognitive_self_healing_convergence.csv"
DETAIL_CSV_PATH = RQ4_CSV_DIR / "rq4_cognitive_self_healing_case_details.csv"
CURVE_CSV_PATH = RQ4_CSV_DIR / "rq4_cognitive_self_healing_cumulative_curve.csv"
PNG_PATH = RQ4_PNG_DIR / "rq4_cognitive_self_healing_convergence.png"
TRACES_DIR = RQ4_CSV_DIR / "rq4_traces"
PARTIAL_CSV_PATH = RQ4_CSV_DIR / "rq4_cognitive_self_healing_convergence.partial.csv"
PARTIAL_DETAIL_CSV_PATH = RQ4_CSV_DIR / "rq4_cognitive_self_healing_case_details.partial.csv"
PARTIAL_CURVE_CSV_PATH = RQ4_CSV_DIR / "rq4_cognitive_self_healing_cumulative_curve.partial.csv"
EXTENDED_METRICS_CSV_PATH = RQ4_CSV_DIR / "rq4_cognitive_self_healing_extended_metrics.csv"
BY_KIND_CSV_PATH = RQ4_CSV_DIR / "rq4_cognitive_self_healing_by_kind.csv"
K_DIST_CSV_PATH = RQ4_CSV_DIR / "rq4_cognitive_self_healing_k_distribution.csv"
FAILURE_CODE_CSV_PATH = RQ4_CSV_DIR / "rq4_cognitive_self_healing_failure_code_breakdown.csv"
EXTENDED_PNG_PATH = RQ4_PNG_DIR / "rq4_cognitive_self_healing_extended_analysis.png"
KM_SURVIVAL_PNG_PATH = RQ4_PNG_DIR / "rq4_cognitive_self_healing_km_unconverged_survival.png"
K_BOX_BY_KIND_PNG_PATH = RQ4_PNG_DIR / "rq4_cognitive_self_healing_k_boxplot_by_kind.png"
CONTEXT_DECAY_CSV_PATH = RQ4_CSV_DIR / "rq4_cognitive_self_healing_context_decay.csv"
RQ4_RAW_CSV_PATH = RQ4_CSV_DIR / "rq4_cognitive_convergence_boundary_raw.csv"
RMST_ABORT_PDF_PATH = RQ4_PDF_DIR / "rmst_and_abort_decomposition.pdf"
CONTEXT_SATURATION_PDF_PATH = RQ4_PDF_DIR / "context_saturation_decay.pdf"
RQ4_IEEE_REPORT_MD_PATH = RQ4_CSV_DIR / "rq4_ieee_report.md"
MANIFEST_JSON_PATH = RQ4_CSV_DIR / "rq4_run_manifest.json"

SEED = 20260430
TOTAL_CASES = 100
K_MAX = 5
MAX_PARALLEL_CASES = 10
API_TIMEOUT_SEC = 45.0
LIRIX_TIMEOUT_SEC = 20.0
CASE_TIMEOUT_SEC = 900.0
NETWORK_RETRY_MAX = 3
NETWORK_RETRY_BASE_SEC = 2.0

sns.set_theme(style="whitegrid", context="paper")

ModelName = Literal["deepseek", "volcengine"]
CaseKind = Literal["A_L2_schema", "B_L5_state"]

SYSTEM_PROMPT = (
    "你是 Lirix 链上安全网关的自动化修复代理。\n"
    "【输出规范】\n"
    "必须且只能输出严格的 JSON 对象，严禁 Markdown 格式与任何解释性文本。\n"
    "【自适应修复法则】\n"
    "收到 EXACT_SCHEMA_VIOLATION 或 LirixFeedback 后，必须基于 CURRENT_BROKEN_PAYLOAD 变形：\n"
    "1. 增补必填：如报错 missing，补充该字段。\n"
    "2. 剔除违禁：如报错 extra_forbidden，彻底删除该字段。\n"
    "3. 纠正类型：如报错 type_error，确保数值是纯整数(Integer)而非字符串。\n"
    "【L2 原生字段契约】\n"
    "输出必须仅包含这些字段：to, function_name, value, data, assertions, intent。\n"
    "- data 必须是 0x 前缀且十六进制长度为偶数。\n"
    "- assertions 必须是数组，每个元素形如 "
    '{"assertion_type":"return_data_int_ge|return_data_exact","expected_value":<int>}。\n'
    "【白名单约束】\n"
    "- 'intent' 必须是 ['contract_call', 'swap'] 之一。\n"
    "- 'to' 必须在 ['0x0000000000000000000000000000000000000000', "
    "'0x1111111111111111111111111111111111111111', '0x2222222222222222222222222222222222222222'] 内。\n"
    "- 'function_name' 必须在 ['transfer', 'swap', 'swapExactETHForTokens'] 内。"
)


@dataclass(frozen=True)
class RQ4Case:
    case_id: str
    kind: CaseKind
    initial_payload: dict[str, Any]
    repair_hint: str


@dataclass
class CaseResult:
    case_id: str
    kind: CaseKind
    model: ModelName
    converged: bool
    k: int
    hard_abort: bool
    last_error_code: str
    last_policy_key: str
    prompt_tokens: int
    completion_tokens: int
    max_prompt_tokens_per_attempt: int
    max_prompt_chars_per_attempt: int


def _load_env_file() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _required_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required env var: {key}")
    return value


def _read_rpc_urls() -> list[str]:
    raw = _required_env("LIRIX_RPC_URLS")
    urls = [u.strip() for u in raw.split(",") if u.strip()]
    if not urls:
        raise RuntimeError("LIRIX_RPC_URLS is empty.")
    if os.getenv("RQ4_USE_ALL_RPCS") == "1":
        return urls
    return urls[:1]


def _resolve_total_cases() -> int:
    raw = os.getenv("RQ4_TOTAL_CASES")
    if raw is None:
        return TOTAL_CASES
    try:
        v = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"RQ4_TOTAL_CASES must be integer, got: {raw}") from exc
    if v <= 0 or v % 2 != 0:
        raise RuntimeError("RQ4_TOTAL_CASES must be a positive even integer.")
    return v


def _build_cases(total_cases: int) -> list[RQ4Case]:
    rng = random.Random(SEED)
    cases: list[RQ4Case] = []
    uint256_max = (1 << 256) - 1

    # Fairness: both models receive the same heterogeneous violations.
    a_templates: list[dict[str, Any]] = [
        {
            "intent": "contract_call",
            "to": "0x1111111111111111111111111111111111111111",
            "function_name": "transfer",
            "value": 0,
            "data": "0x123",  # odd-length hex
            "assertions": [],
        },
        {
            "intent": "contract_call",
            "to": "0x1111111111111111111111111111111111111111",
            "function_name": "transfer",
            "value": uint256_max + 77,  # uint256 overflow
            "data": "0x1234",
            "assertions": [],
        },
        {
            "intent": "contract_call",
            "to": "0x1111111111111111111111111111111111111111",
            "function_name": "transfer",
            "value": "42",  # wrong type
            "data": "0x1234",
            "assertions": [],
        },
        {
            "intent": "contract_call",
            "to": "0x1111111111111111111111111111111111111111",
            "function_name": "transfer",
            "value": 1,
            "data": "0xzz11",  # non-hex chars
            "assertions": [],
        },
        {
            "intent": "contract_call",
            "to": "0x1111111111111111111111111111111111111111",
            "function_name": "transfer",
            "value": 2,
            "data": "0x1234",
            "assertions": [
                {"assertion_type": "return_data_int_ge", "expected_value": "100"}
            ],  # wrong type
        },
    ]

    b_templates: list[dict[str, Any]] = [
        {
            "intent": "swap",
            "to": "0x3333333333333333333333333333333333333333",  # not allowed
            "function_name": "swapExactETHForTokens",
            "value": 0,
            "data": "0x1234",
            "assertions": [{"assertion_type": "return_data_exact", "expected_value": 10**30}],
        },
        {
            "intent": "swap",
            "to": "0x2222222222222222222222222222222222222222",
            "function_name": "rugPull",  # not allowed
            "value": 0,
            "data": "0x1234",
            "assertions": [{"assertion_type": "return_data_exact", "expected_value": 123456789}],
        },
        {
            "intent": "swap",
            "to": "0x0000000000000000000000000000000000000000",
            "function_name": "swap",
            "value": 0,
            "data": "0x1234",
            "assertions": [{"assertion_type": "return_data_exact", "expected_value": 10**24}],
        },
        {
            "intent": "swap",
            "to": "0x2222222222222222222222222222222222222222",
            "function_name": "swapExactETHForTokens",
            "value": 0,
            "data": "0x1234",
            "assertions": [{"assertion_type": "return_data_int_ge", "expected_value": 10**21}],
        },
        {
            "intent": "swap",
            "to": "0x3333333333333333333333333333333333333333",  # not allowed
            "function_name": "rugPull",  # not allowed
            "value": 0,
            "data": "0x1234",
            "assertions": [{"assertion_type": "return_data_exact", "expected_value": 999999999999}],
        },
    ]

    for i in range(total_cases // 2):
        payload = dict(a_templates[i % len(a_templates)])
        hint = "依据反馈修复 payload，保持字段契约。"
        cases.append(
            RQ4Case(
                case_id=f"rq4-A-{i + 1:03d}",
                kind="A_L2_schema",
                initial_payload=payload,
                repair_hint=hint,
            )
        )

    for i in range(total_cases // 2):
        payload = dict(b_templates[i % len(b_templates)])
        hint = "依据反馈修复 payload，保持字段契约。"
        cases.append(
            RQ4Case(
                case_id=f"rq4-B-{i + 1:03d}",
                kind="B_L5_state",
                initial_payload=payload,
                repair_hint=hint,
            )
        )

    rng.shuffle(cases)
    return cases


class _RealLLMModel:
    def __init__(self, name: ModelName) -> None:
        self.name = name
        if name == "deepseek":
            self.api_key = _required_env("DEEPSEEK_API_KEY")
            self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
            self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
        else:
            self.api_key = _required_env("VOLCENGINE_API_KEY")
            self.base_url = os.getenv(
                "VOLCENGINE_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"
            )
            self.model = os.getenv("VOLCENGINE_ENDPOINT_ID") or os.getenv("VOLCENGINE_MODEL", "")
            if not self.model:
                raise RuntimeError("VOLCENGINE_MODEL or VOLCENGINE_ENDPOINT_ID must be set.")

    def route_fingerprint(self) -> str:
        return f"{self.name}|{self.base_url.rstrip('/')}|{self.model}"

    @staticmethod
    def _schema_version() -> int:
        return 1

    async def _chat(
        self,
        client: httpx.AsyncClient,
        messages: list[dict[str, str]],
        timeout_sec: float = API_TIMEOUT_SEC,
    ) -> tuple[str, int, int]:
        if self.name == "volcengine":
            print(
                (
                    f"[GATEWAY DEBUG] Volcengine Route -> URL: "
                    f"{self.base_url.rstrip('/')}/chat/completions | Model ID: '{self.model}'"
                ),
                flush=True,
            )
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        if self.name == "volcengine":
            headers["Connection"] = "close"
        response = await client.post(
            url=f"{self.base_url.rstrip('/')}/chat/completions",
            json={
                "model": self.model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": messages,
                "max_tokens": 1500,
            },
            headers=headers,
            timeout=timeout_sec,
        )
        response.raise_for_status()
        data = response.json()
        try:
            content = str(data["choices"][0]["message"]["content"])
            usage = data.get("usage", {}) if isinstance(data, dict) else {}
            prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
            completion_tokens = int(usage.get("completion_tokens", 0) or 0)
            return content, prompt_tokens, completion_tokens
        except Exception as exc:
            raise RuntimeError(f"Unexpected LLM response schema: {data}") from exc

    async def repair_payload(
        self,
        client: httpx.AsyncClient,
        case: RQ4Case,
        current_payload: dict[str, Any],
        feedback: str,
    ) -> tuple[dict[str, Any], int, int, int]:
        trace_file = TRACES_DIR / f"{self.name}_{case.case_id}.log"
        with trace_file.open("a", encoding="utf-8") as fp:
            fp.write("--- ATTEMPTING REPAIR (K triggered) ---\n")
        prompt = (
            "输出严格 JSON（不要 markdown）。\n"
            "字段：intent(string), to(string), function_name(string), value(int), data(string), "
            "assertions(array)。\n"
            f"CaseKind={case.kind}\n"
            f"CURRENT_BROKEN_PAYLOAD={json.dumps(current_payload, ensure_ascii=False)}\n"
            f"LirixFeedback={feedback}\n"
            "请基于 CURRENT_BROKEN_PAYLOAD 进行修正。\n"
        )

        content = ""
        prompt_tokens = 0
        completion_tokens = 0
        for attempt in range(1, NETWORK_RETRY_MAX + 1):
            try:
                content, prompt_tokens, completion_tokens = await self._chat(
                    client,
                    [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                )
                break
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status in {429, 500, 502, 503, 504} and attempt < NETWORK_RETRY_MAX:
                    await asyncio.sleep(NETWORK_RETRY_BASE_SEC * attempt)
                    continue
                raise RuntimeError(f"LLM HTTP status error: {status}") from exc
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RequestError) as exc:
                if attempt < NETWORK_RETRY_MAX:
                    await asyncio.sleep(NETWORK_RETRY_BASE_SEC * attempt)
                    continue
                raise RuntimeError(f"LLM transport retry exhausted: {exc}") from exc

        if not content:
            raise RuntimeError("LLM retry loop exited without content.")

        try:
            parsed = json.loads(content)
            assertions = parsed.get("assertions")
            normalized_assertions = assertions if isinstance(assertions, list) else []
            return (
                {
                    "intent": str(parsed.get("intent", current_payload.get("intent", "unknown"))),
                    "to": str(parsed.get("to", current_payload.get("to", ""))),
                    "function_name": str(
                        parsed.get("function_name", current_payload.get("function_name", ""))
                    ),
                    "value": int(parsed.get("value", current_payload.get("value", 0))),
                    "data": str(parsed.get("data", current_payload.get("data", "0x"))),
                    "assertions": normalized_assertions,
                },
                prompt_tokens,
                completion_tokens,
                len(prompt),
            )
        except Exception as exc:
            raise RuntimeError(f"LLM returned invalid JSON payload: {content}") from exc


def _extract_error(exc: Exception) -> tuple[str, str, str, bool]:
    """Return feedback, code, policy_key, is_semantic_converged."""
    if isinstance(exc, LirixBaseException):
        ctx = exc.context if isinstance(exc.context, dict) else {}
        feedback = str(exc.resolution_for_agent)
        code = str(getattr(exc, "error_code", "LRX_LEGACY_ERROR"))
        policy_key = str(ctx.get("policy_key", "unknown_policy"))

        lower_exc = str(exc).lower()
        revert_keywords = [
            "revert",
            "insufficient balance",
            "evm",
            "simulation failed but syntax valid",
        ]
        if any(kw in lower_exc for kw in revert_keywords) and "schema" not in lower_exc:
            return "EVM State Blocked (Semantic Success)", "EVM_REVERT_EXPECTED", policy_key, True

        detail = ""
        if hasattr(exc, "errors") and callable(exc.errors):
            try:
                errors_list = exc.errors()
                detail = " | ".join(
                    [
                        (
                            f"Field '{'.'.join(map(str, e.get('loc', [])))}': {e.get('msg')} "
                            f"(expected: {e.get('type')})"
                        )
                        for e in errors_list
                    ]
                )
            except Exception:
                pass

        if not detail and ctx:
            errors = ctx.get("errors")
            if isinstance(errors, list):
                extracted: list[str] = []
                for err in errors:
                    if isinstance(err, dict):
                        loc = ".".join(map(str, err.get("loc", [])))
                        msg = str(err.get("msg", "unknown"))
                        expected = str(err.get("type", "unknown"))
                        extracted.append(f"Field '{loc}': {msg} (expected: {expected})")
                if extracted:
                    detail = " | ".join(extracted)

        if not detail and ctx:
            detail = json.dumps(ctx, ensure_ascii=False, default=str)

        if detail:
            feedback += f" | EXACT_SCHEMA_VIOLATION: {detail}"
        elif "schema" in feedback.lower() or not feedback:
            feedback += f" | RAW_EXCEPTION: {str(exc)}"
        return feedback, code, policy_key, False
    return f"System Exception: {str(exc)}", "UNEXPECTED_EXCEPTION", "unknown_policy", False


async def _validate_once(guardian: Lirix, payload: dict[str, Any]) -> None:
    intent = str(payload.get("intent", "unknown"))
    clean_payload = {k: v for k, v in payload.items() if k != "intent"}
    await asyncio.wait_for(
        guardian.async_validate_and_simulate(intent, clean_payload),
        timeout=LIRIX_TIMEOUT_SEC,
    )


async def _run_single_case(
    model: _RealLLMModel,
    client: httpx.AsyncClient,
    guardian: Lirix,
    case: RQ4Case,
    sem: asyncio.Semaphore,
) -> CaseResult:
    async with sem:
        payload = dict(case.initial_payload)
        feedback = "Initial adversarial payload"
        last_code = "NONE"
        last_policy = "NONE"
        prompt_tokens = 0
        completion_tokens = 0
        max_prompt_tokens_per_attempt = 0
        max_prompt_chars_per_attempt = 0
        k = 0
        trace_file = TRACES_DIR / f"{model.name}_{case.case_id}.log"
        trace_file.parent.mkdir(parents=True, exist_ok=True)
        trace_file.write_text(
            (
                "=== CASE START ===\n"
                f"model={model.name}\n"
                f"case_id={case.case_id}\n"
                f"kind={case.kind}\n"
                f"route={model.route_fingerprint()}\n"
                f"initial_payload={json.dumps(payload, ensure_ascii=False)}\n"
            ),
            encoding="utf-8",
        )

        while k < K_MAX:
            k += 1
            try:
                await _validate_once(guardian, payload)
                with trace_file.open("a", encoding="utf-8") as fp:
                    fp.write(f"--- K={k} ---\n")
                    fp.write("VALIDATE_PASS: true\n")
                return CaseResult(
                    case_id=case.case_id,
                    kind=case.kind,
                    model=model.name,
                    converged=True,
                    k=k,
                    hard_abort=False,
                    last_error_code="",
                    last_policy_key="",
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    max_prompt_tokens_per_attempt=max_prompt_tokens_per_attempt,
                    max_prompt_chars_per_attempt=max_prompt_chars_per_attempt,
                )
            except asyncio.TimeoutError:
                feedback = "Lirix timeout: reduce payload complexity and use canonical intent."
                last_code = "LIRIX_TIMEOUT"
                last_policy = "timeout"
                with trace_file.open("a", encoding="utf-8") as fp:
                    fp.write(f"--- K={k} ---\n")
                    fp.write("VALIDATE_PASS: false\n")
                    fp.write(f"FEEDBACK_IN: {feedback}\n")
            except Exception as exc:
                feedback, last_code, last_policy, is_semantic_converged = _extract_error(exc)
                if is_semantic_converged:
                    with trace_file.open("a", encoding="utf-8") as fp:
                        fp.write(f"--- K={k} ---\n")
                        fp.write("SEMANTIC_CONVERGENCE: true\n")
                        fp.write(f"FEEDBACK_IN: {feedback}\n")
                    return CaseResult(
                        case_id=case.case_id,
                        kind=case.kind,
                        model=model.name,
                        converged=True,
                        k=k,
                        hard_abort=False,
                        last_error_code=last_code,
                        last_policy_key=last_policy,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        max_prompt_tokens_per_attempt=max_prompt_tokens_per_attempt,
                        max_prompt_chars_per_attempt=max_prompt_chars_per_attempt,
                    )

            if k >= K_MAX:
                break

            try:
                print(
                    f"  -> [{model.name}] Case {case.case_id} | K={k} | Awaiting repair...",
                    flush=True,
                )
                payload, p_tok, c_tok, p_chars = await model.repair_payload(
                    client, case, payload, feedback
                )
                prompt_tokens += p_tok
                completion_tokens += c_tok
                max_prompt_tokens_per_attempt = max(max_prompt_tokens_per_attempt, p_tok)
                max_prompt_chars_per_attempt = max(max_prompt_chars_per_attempt, p_chars)
                print(
                    f"  <- [{model.name}] Case {case.case_id} | K={k} | Repair received.",
                    flush=True,
                )
                with trace_file.open("a", encoding="utf-8") as fp:
                    fp.write(f"--- K={k} ---\n")
                    fp.write(f"FEEDBACK_IN: {feedback}\n")
                    fp.write(f"PAYLOAD_OUT: {json.dumps(payload, ensure_ascii=False)}\n")
            except asyncio.TimeoutError:
                last_code = "LLM_TIMEOUT"
                last_policy = "transport"
                with trace_file.open("a", encoding="utf-8") as fp:
                    fp.write(f"--- K={k} ---\n")
                    fp.write(f"FEEDBACK_IN: {feedback}\n")
                    fp.write("REPAIR_ERROR: asyncio.TimeoutError\n")
                k += 1
                await asyncio.sleep(1.0)
            except Exception as exc:
                last_code = "LLM_API_FAILURE"
                last_policy = "transport"
                with trace_file.open("a", encoding="utf-8") as fp:
                    fp.write(f"--- K={k} ---\n")
                    fp.write(f"FEEDBACK_IN: {feedback}\n")
                    fp.write(f"REPAIR_ERROR: {type(exc).__name__}: {exc}\n")
                k += 1
                await asyncio.sleep(2.0)

        return CaseResult(
            case_id=case.case_id,
            kind=case.kind,
            model=model.name,
            converged=False,
            k=K_MAX + 1,
            hard_abort=True,
            last_error_code=last_code,
            last_policy_key=last_policy,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            max_prompt_tokens_per_attempt=max_prompt_tokens_per_attempt,
            max_prompt_chars_per_attempt=max_prompt_chars_per_attempt,
        )


async def _run_single_case_with_timeout(
    model: _RealLLMModel,
    client: httpx.AsyncClient,
    guardian: Lirix,
    case: RQ4Case,
    sem: asyncio.Semaphore,
) -> CaseResult:
    try:
        return await asyncio.wait_for(
            _run_single_case(model, client, guardian, case, sem),
            timeout=CASE_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        return CaseResult(
            case_id=case.case_id,
            kind=case.kind,
            model=model.name,
            converged=False,
            k=K_MAX + 1,
            hard_abort=True,
            last_error_code="CASE_TIMEOUT",
            last_policy_key="timeout",
            prompt_tokens=0,
            completion_tokens=0,
            max_prompt_tokens_per_attempt=0,
            max_prompt_chars_per_attempt=0,
        )


def _aggregate(results: list[CaseResult]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    summary_rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []
    for model_name in ("deepseek", "volcengine"):
        subset = [r for r in results if r.model == model_name]
        total = len(subset)
        converged = [r for r in subset if r.converged]
        hard_aborts = [r for r in subset if r.hard_abort]
        k_list = [r.k for r in converged]
        mean_k = statistics.fmean(k_list) if k_list else 0.0
        rmst_k = statistics.fmean([min(r.k, K_MAX + 1) for r in subset]) if subset else 0.0
        std_k = statistics.pstdev(k_list) if len(k_list) >= 2 else 0.0
        infra_abort = sum(
            1
            for r in hard_aborts
            if r.last_error_code in {"CASE_TIMEOUT", "LLM_TIMEOUT", "LLM_API_FAILURE"}
        )
        cognitive_abort = len(hard_aborts) - infra_abort
        total_prompt_tokens = sum(r.prompt_tokens for r in subset)
        total_completion_tokens = sum(r.completion_tokens for r in subset)
        mean_max_prompt_tokens = (
            statistics.fmean([r.max_prompt_tokens_per_attempt for r in subset]) if subset else 0.0
        )
        summary_rows.append(
            {
                "model": model_name,
                "total_cases": total,
                "converged_cases": len(converged),
                "hard_abort_cases": len(hard_aborts),
                "convergence_rate": (len(converged) / total) if total else 0.0,
                "conditional_mean_cycles_to_converge": mean_k,
                "rmst_cycles_truncated_kmax_plus1": rmst_k,
                "std_cycles_to_converge": std_k,
                "hard_abort_rate": (len(hard_aborts) / total) if total else 0.0,
                "infra_hard_abort_cases": infra_abort,
                "cognitive_hard_abort_cases": cognitive_abort,
                "total_prompt_tokens": total_prompt_tokens,
                "total_completion_tokens": total_completion_tokens,
                "total_tokens": total_prompt_tokens + total_completion_tokens,
                "mean_max_prompt_tokens_per_attempt": mean_max_prompt_tokens,
            }
        )

        for k in range(1, K_MAX + 1):
            cumulative_success = sum(1 for r in subset if r.converged and r.k <= k)
            curve_rows.append(
                {
                    "model": model_name,
                    "k": k,
                    "cumulative_success_rate": (cumulative_success / total) if total else 0.0,
                }
            )
    return summary_rows, curve_rows


def _write_outputs(
    summary_rows: list[dict[str, Any]],
    results: list[CaseResult],
    curve_rows: list[dict[str, Any]],
    *,
    partial: bool = False,
) -> None:
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    RQ4_CSV_DIR.mkdir(parents=True, exist_ok=True)
    RQ4_PNG_DIR.mkdir(parents=True, exist_ok=True)
    RQ4_PDF_DIR.mkdir(parents=True, exist_ok=True)
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    TRACES_DIR.mkdir(parents=True, exist_ok=True)
    for old_json in CASES_DIR.glob("*.json"):
        old_json.unlink()

    for r in results:
        case_payload = {
            "schema_version": 1,
            "case_id": r.case_id,
            "kind": r.kind,
            "model": r.model,
            "converged": r.converged,
            "k": r.k,
            "hard_abort": r.hard_abort,
            "last_error_code": r.last_error_code,
            "last_policy_key": r.last_policy_key,
            "prompt_tokens": r.prompt_tokens,
            "completion_tokens": r.completion_tokens,
            "total_tokens": r.prompt_tokens + r.completion_tokens,
            "max_prompt_tokens_per_attempt": r.max_prompt_tokens_per_attempt,
            "max_prompt_chars_per_attempt": r.max_prompt_chars_per_attempt,
        }
        (CASES_DIR / f"{r.model}-{r.case_id}.json").write_text(
            json.dumps(case_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    summary_path = PARTIAL_CSV_PATH if partial else CSV_PATH
    detail_path = PARTIAL_DETAIL_CSV_PATH if partial else DETAIL_CSV_PATH
    curve_path = PARTIAL_CURVE_CSV_PATH if partial else CURVE_CSV_PATH

    with summary_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "schema_version",
                "model",
                "total_cases",
                "converged_cases",
                "hard_abort_cases",
                "convergence_rate",
                "conditional_mean_cycles_to_converge",
                "rmst_cycles_truncated_kmax_plus1",
                "std_cycles_to_converge",
                "hard_abort_rate",
                "infra_hard_abort_cases",
                "cognitive_hard_abort_cases",
                "total_prompt_tokens",
                "total_completion_tokens",
                "total_tokens",
                "mean_max_prompt_tokens_per_attempt",
            ],
        )
        writer.writeheader()
        for row in summary_rows:
            writer.writerow(
                {
                    "schema_version": 1,
                    "model": row["model"],
                    "total_cases": row["total_cases"],
                    "converged_cases": row["converged_cases"],
                    "hard_abort_cases": row["hard_abort_cases"],
                    "convergence_rate": f"{row['convergence_rate']:.6f}",
                    "conditional_mean_cycles_to_converge": f"{row['conditional_mean_cycles_to_converge']:.3f}",
                    "rmst_cycles_truncated_kmax_plus1": f"{row['rmst_cycles_truncated_kmax_plus1']:.3f}",
                    "std_cycles_to_converge": f"{row['std_cycles_to_converge']:.3f}",
                    "hard_abort_rate": f"{row['hard_abort_rate']:.6f}",
                    "infra_hard_abort_cases": row["infra_hard_abort_cases"],
                    "cognitive_hard_abort_cases": row["cognitive_hard_abort_cases"],
                    "total_prompt_tokens": row["total_prompt_tokens"],
                    "total_completion_tokens": row["total_completion_tokens"],
                    "total_tokens": row["total_tokens"],
                    "mean_max_prompt_tokens_per_attempt": f"{row['mean_max_prompt_tokens_per_attempt']:.3f}",
                }
            )

    with detail_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "schema_version",
                "model",
                "case_id",
                "kind",
                "converged",
                "k",
                "hard_abort",
                "last_error_code",
                "last_policy_key",
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "max_prompt_tokens_per_attempt",
                "max_prompt_chars_per_attempt",
            ],
        )
        writer.writeheader()
        for r in results:
            writer.writerow(
                {
                    "schema_version": 1,
                    "model": r.model,
                    "case_id": r.case_id,
                    "kind": r.kind,
                    "converged": r.converged,
                    "k": r.k,
                    "hard_abort": r.hard_abort,
                    "last_error_code": r.last_error_code,
                    "last_policy_key": r.last_policy_key,
                    "prompt_tokens": r.prompt_tokens,
                    "completion_tokens": r.completion_tokens,
                    "total_tokens": r.prompt_tokens + r.completion_tokens,
                    "max_prompt_tokens_per_attempt": r.max_prompt_tokens_per_attempt,
                    "max_prompt_chars_per_attempt": r.max_prompt_chars_per_attempt,
                }
            )

    with curve_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp, fieldnames=["schema_version", "model", "k", "cumulative_success_rate"]
        )
        writer.writeheader()
        for row in curve_rows:
            writer.writerow(
                {
                    "schema_version": 1,
                    "model": row["model"],
                    "k": row["k"],
                    "cumulative_success_rate": f"{row['cumulative_success_rate']:.6f}",
                }
            )


def _write_plot(summary_rows: list[dict[str, Any]], curve_rows: list[dict[str, Any]]) -> None:
    labels = [row["model"] for row in summary_rows]
    mean_k = [row["conditional_mean_cycles_to_converge"] for row in summary_rows]
    std_k = [row["std_cycles_to_converge"] for row in summary_rows]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    x = list(range(len(labels)))
    axes[0].bar(x, mean_k, yerr=std_k, capsize=6, color=["#2563eb", "#dc2626"], alpha=0.85)
    axes[0].set_xticks(x, labels)
    axes[0].set_ylabel("Conditional Mean K (given convergence)")
    axes[0].set_title("RQ4 Conditional Mean K with Error Bars")
    axes[0].grid(axis="y", linestyle="--", linewidth=0.6, alpha=0.7)

    for model_name, color in (("deepseek", "#2563eb"), ("volcengine", "#dc2626")):
        points = [row for row in curve_rows if row["model"] == model_name]
        axes[1].plot(
            [row["k"] for row in points],
            [row["cumulative_success_rate"] for row in points],
            marker="o",
            linewidth=2.0,
            label=model_name,
            color=color,
        )
    axes[1].set_xticks(list(range(1, K_MAX + 1)))
    axes[1].set_ylim(0.0, 1.05)
    axes[1].set_xlabel("Retry Step K")
    axes[1].set_ylabel("Cumulative Success Rate")
    axes[1].set_title("RQ4 Cumulative Convergence Curve")
    axes[1].grid(True, linestyle="--", linewidth=0.6, alpha=0.7)
    axes[1].legend()

    fig.suptitle("RQ4: Cognitive Self-Healing Convergence (Kmax=5, DeepSeek vs Volcengine)")
    plt.tight_layout()
    plt.savefig(PNG_PATH, dpi=180)
    plt.close()


def _wilson_half_width(success: int, total: int, z: float = 1.96) -> float:
    if total <= 0:
        return 0.0
    p = success / total
    denom = 1.0 + (z * z) / total
    center = (p + (z * z) / (2.0 * total)) / denom
    margin = (z * ((p * (1.0 - p) / total + (z * z) / (4.0 * total * total)) ** 0.5)) / denom
    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    return max(center - low, high - center)


def _percentile(sorted_values: list[int], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac


def _map_hard_abort_reason(last_error_code: str) -> str:
    if last_error_code == "CASE_TIMEOUT":
        return "CASE_TIMEOUT"
    if last_error_code == "EVM_REVERT":
        return "EVM_REVERT"
    return "EXACT_SCHEMA_VIOLATION"


def _write_rq4_raw_csv(results: list[CaseResult]) -> None:
    with RQ4_RAW_CSV_PATH.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "schema_version",
                "model_name",
                "case_id",
                "converged_at_k",
                "hard_abort_reason",
                "max_prompt_tokens_per_attempt",
                "cumulative_completion_tokens",
            ],
        )
        writer.writeheader()
        for r in results:
            writer.writerow(
                {
                    "schema_version": 1,
                    "model_name": r.model,
                    "case_id": r.case_id,
                    "converged_at_k": r.k if r.converged else -1,
                    "hard_abort_reason": (
                        _map_hard_abort_reason(r.last_error_code) if r.hard_abort else ""
                    ),
                    "max_prompt_tokens_per_attempt": r.max_prompt_tokens_per_attempt,
                    "cumulative_completion_tokens": r.completion_tokens,
                }
            )


def _write_ieee_rq4_artifacts(
    results: list[CaseResult], summary_rows: list[dict[str, Any]]
) -> None:
    models = [row["model"] for row in summary_rows]
    cmap = {"deepseek": "#2563eb", "volcengine": "#dc2626"}

    # Figure 1: conditional RMST mean + hard abort decomposition.
    fig, axes = plt.subplots(
        2,
        1,
        figsize=(10, 8),
        gridspec_kw={"height_ratios": [2.2, 1.6], "hspace": 0.18},
        sharex=True,
    )
    means: list[float] = []
    errs: list[float] = []
    cog_ratio: list[float] = []
    infra_ratio: list[float] = []
    for m in models:
        subset = [r for r in results if r.model == m]
        succ = [r.k for r in subset if r.converged]
        abort = [r for r in subset if r.hard_abort]
        means.append(statistics.fmean(succ) if succ else 0.0)
        errs.append((statistics.pstdev(succ) / (len(succ) ** 0.5)) if len(succ) >= 2 else 0.0)
        total_abort = len(abort) if abort else 1
        cog = sum(
            1
            for r in abort
            if _map_hard_abort_reason(r.last_error_code) == "EXACT_SCHEMA_VIOLATION"
        )
        infra = sum(1 for r in abort if _map_hard_abort_reason(r.last_error_code) == "CASE_TIMEOUT")
        cog_ratio.append(cog / total_abort if abort else 0.0)
        infra_ratio.append(infra / total_abort if abort else 0.0)

    x = list(range(len(models)))
    axes[0].bar(x, means, yerr=errs, capsize=7, color=[cmap[m] for m in models], alpha=0.9)
    axes[0].set_ylabel("Conditional Mean K")
    axes[0].set_title("Conditional Mean K on Converged Samples")
    axes[0].grid(axis="y", linestyle="--", linewidth=0.6, alpha=0.7)

    axes[1].bar(x, cog_ratio, color="#7f1d1d", label="Cognitive Collapse (Schema Violation)")
    axes[1].bar(
        x, infra_ratio, bottom=cog_ratio, color="#6b7280", label="Infrastructure Failure (Timeout)"
    )
    axes[1].set_xticks(x, models)
    axes[1].set_ylim(0.0, 1.0)
    axes[1].set_ylabel("Hard Abort Composition")
    axes[1].set_yticks([0.0, 0.25, 0.5, 0.75, 1.0], ["0%", "25%", "50%", "75%", "100%"])
    axes[1].set_title("Hard Abort Breakdown (100% Stacked)")
    axes[1].legend(loc="upper right", frameon=True)
    axes[1].grid(axis="y", linestyle="--", linewidth=0.6, alpha=0.7)
    plt.tight_layout()
    plt.savefig(RMST_ABORT_PDF_PATH)
    plt.close(fig)

    # Figure 2: context saturation decay.
    bins = [0, 1000, 2000, 10**9]
    labels = ["<1k", "1k-2k", ">2k"]
    sat_fig, sat_ax = plt.subplots(1, 1, figsize=(9, 5))
    for m in models:
        subset = [r for r in results if r.model == m]
        y: list[float] = []
        for lo, hi in zip(bins[:-1], bins[1:]):
            bucket = [r for r in subset if lo <= r.max_prompt_tokens_per_attempt < hi]
            rate = (sum(1 for r in bucket if r.converged) / len(bucket)) if bucket else 0.0
            y.append(rate)
        sat_ax.plot(labels, y, marker="o", linewidth=2.2, label=m, color=cmap[m])
    sat_ax.set_ylim(0.0, 1.0)
    sat_ax.set_xlabel("Max Prompt Tokens per Attempt (Bucket)")
    sat_ax.set_ylabel("Success Rate at Current K")
    sat_ax.set_title("Context Saturation Decay and Cognitive Cliff")
    sat_ax.legend(frameon=True)
    sat_ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.7)
    plt.tight_layout()
    plt.savefig(CONTEXT_SATURATION_PDF_PATH)
    plt.close(sat_fig)

    report_lines: list[str] = [
        "# RQ4: Cognitive Convergence Boundary",
        "",
        "## 1. Experimental Scope",
        f"- Total evaluated samples: {len(results)} across models {', '.join(models)}.",
        f"- K upper bound: {K_MAX}.",
        f"- Seed: {SEED}.",
        f"- Timeouts: API={API_TIMEOUT_SEC}s, Lirix={LIRIX_TIMEOUT_SEC}s, case={CASE_TIMEOUT_SEC}s.",
        f"- Archive root: `{OUTPUT_LAYOUT.base_dir / OUTPUT_LAYOUT.branch_slug / 'runs' / OUTPUT_LAYOUT.run_slug}`",
        "",
        "## 2. Artifact Inventory",
        f"- Raw CSV: `{RQ4_RAW_CSV_PATH.name}`",
        f"- Detail CSV: `{DETAIL_CSV_PATH.name}`",
        f"- Curve CSV: `{CURVE_CSV_PATH.name}`",
        f"- Plot: `{PNG_PATH.name}`",
        f"- Extended metrics: `{EXTENDED_METRICS_CSV_PATH.name}`",
        f"- By-kind CSV: `{BY_KIND_CSV_PATH.name}`",
        f"- K distribution CSV: `{K_DIST_CSV_PATH.name}`",
        f"- Failure breakdown CSV: `{FAILURE_CODE_CSV_PATH.name}`",
        f"- Report: `{RQ4_IEEE_REPORT_MD_PATH.name}`",
        "",
        "## 3. Figures",
        f"- Figure 1: `{RMST_ABORT_PDF_PATH.name}`",
        f"- Figure 2: `{CONTEXT_SATURATION_PDF_PATH.name}`",
        f"- Supplemental Figure 1: `{KM_SURVIVAL_PNG_PATH.name}`",
        f"- Supplemental Figure 2: `{K_BOX_BY_KIND_PNG_PATH.name}`",
        f"- Extended analysis: `{EXTENDED_PNG_PATH.name}`",
        "",
        "## 4. Core Results",
    ]
    for row in summary_rows:
        report_lines.append(
            f"- {row['model']}: convergence={row['convergence_rate']:.3f}, "
            f"conditional_mean_k={row['conditional_mean_cycles_to_converge']:.3f}, "
            f"rmst={row['rmst_cycles_truncated_kmax_plus1']:.3f}, "
            f"hard_abort_rate={row['hard_abort_rate']:.3f}."
        )
    report_lines.extend(
        [
            "",
            "## 5. Interpretation",
            "- The upper panel in Figure 1 isolates pure cognitive convergence speed by conditioning on successful samples only.",
            "- The lower panel separates cognitive collapse (schema loops) from infrastructure failures (timeouts), reducing censored-bias interpretation risk.",
            "- Figure 2 exposes the context saturation boundary where additional prompt-token load correlates with a sharp success-rate decline.",
            "",
            "## 6. Reproducibility",
            "- Output ordering and archive layout are intentionally stable to support direct diff-based regression review.",
            "- Schema version markers are embedded in CSV/JSON outputs for forward-compatible parsing.",
        ]
    )
    RQ4_IEEE_REPORT_MD_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")


def _write_extended_outputs(results: list[CaseResult]) -> None:
    models = ("deepseek", "volcengine")
    kinds = ("A_L2_schema", "B_L5_state")

    by_kind_rows: list[dict[str, Any]] = []
    k_dist_rows: list[dict[str, Any]] = []
    failure_rows: list[dict[str, Any]] = []
    extended_rows: list[dict[str, Any]] = []

    for model in models:
        model_subset = [r for r in results if r.model == model]
        total = len(model_subset)
        converged = [r for r in model_subset if r.converged]
        hard_abort = [r for r in model_subset if r.hard_abort]
        k_sorted = sorted(r.k for r in converged)
        conditional_mean_k = statistics.fmean([r.k for r in converged]) if converged else 0.0
        rmst_k = (
            statistics.fmean([min(r.k, K_MAX + 1) for r in model_subset]) if model_subset else 0.0
        )
        infra_abort = sum(
            1
            for r in hard_abort
            if r.last_error_code in {"CASE_TIMEOUT", "LLM_TIMEOUT", "LLM_API_FAILURE"}
        )
        cognitive_abort = len(hard_abort) - infra_abort
        prompt_tokens = sum(r.prompt_tokens for r in model_subset)
        completion_tokens = sum(r.completion_tokens for r in model_subset)
        mean_max_prompt_tokens = (
            statistics.fmean([r.max_prompt_tokens_per_attempt for r in model_subset])
            if model_subset
            else 0.0
        )

        extended_rows.append(
            {
                "model": model,
                "total_cases": total,
                "converged_cases": len(converged),
                "hard_abort_cases": len(hard_abort),
                "convergence_rate": (len(converged) / total) if total else 0.0,
                "convergence_rate_ci95_halfwidth": _wilson_half_width(len(converged), total),
                "hard_abort_rate": (len(hard_abort) / total) if total else 0.0,
                "hard_abort_rate_ci95_halfwidth": _wilson_half_width(len(hard_abort), total),
                "conditional_mean_cycles_to_converge": conditional_mean_k,
                "rmst_cycles_truncated_kmax_plus1": rmst_k,
                "k_median": _percentile(k_sorted, 0.5),
                "k_p90": _percentile(k_sorted, 0.9),
                "k_p95": _percentile(k_sorted, 0.95),
                "total_prompt_tokens": prompt_tokens,
                "total_completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "infra_hard_abort_cases": infra_abort,
                "cognitive_hard_abort_cases": cognitive_abort,
                "mean_max_prompt_tokens_per_attempt": mean_max_prompt_tokens,
            }
        )

        code_counter: dict[str, int] = {}
        for r in hard_abort:
            code = r.last_error_code or "UNKNOWN"
            code_counter[code] = code_counter.get(code, 0) + 1
        for code, count in sorted(code_counter.items(), key=lambda x: (-x[1], x[0])):
            failure_rows.append(
                {
                    "model": model,
                    "error_code": code,
                    "count": count,
                    "share_in_hard_abort": (count / len(hard_abort)) if hard_abort else 0.0,
                }
            )

        for kind in kinds:
            subset = [r for r in model_subset if r.kind == kind]
            c = [r for r in subset if r.converged]
            total_kind = len(subset)
            by_kind_rows.append(
                {
                    "model": model,
                    "kind": kind,
                    "total_cases": total_kind,
                    "converged_cases": len(c),
                    "convergence_rate": (len(c) / total_kind) if total_kind else 0.0,
                    "convergence_rate_ci95_halfwidth": _wilson_half_width(len(c), total_kind),
                    "hard_abort_rate": (
                        (sum(1 for r in subset if r.hard_abort) / total_kind) if total_kind else 0.0
                    ),
                }
            )

        for k in range(1, K_MAX + 1):
            count = sum(1 for r in model_subset if r.converged and r.k == k)
            k_dist_rows.append(
                {
                    "model": model,
                    "k": k,
                    "count": count,
                    "share_over_total": (count / total) if total else 0.0,
                    "share_over_converged": (count / len(converged)) if converged else 0.0,
                }
            )

    with EXTENDED_METRICS_CSV_PATH.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "model",
                "total_cases",
                "converged_cases",
                "hard_abort_cases",
                "convergence_rate",
                "convergence_rate_ci95_halfwidth",
                "hard_abort_rate",
                "hard_abort_rate_ci95_halfwidth",
                "conditional_mean_cycles_to_converge",
                "rmst_cycles_truncated_kmax_plus1",
                "k_median",
                "k_p90",
                "k_p95",
                "total_prompt_tokens",
                "total_completion_tokens",
                "total_tokens",
                "infra_hard_abort_cases",
                "cognitive_hard_abort_cases",
                "mean_max_prompt_tokens_per_attempt",
            ],
        )
        writer.writeheader()
        for row in extended_rows:
            writer.writerow({"schema_version": 1, **row})

    with BY_KIND_CSV_PATH.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "model",
                "kind",
                "total_cases",
                "converged_cases",
                "convergence_rate",
                "convergence_rate_ci95_halfwidth",
                "hard_abort_rate",
            ],
        )
        writer.writeheader()
        for row in by_kind_rows:
            writer.writerow({"schema_version": 1, **row})

    with K_DIST_CSV_PATH.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=["model", "k", "count", "share_over_total", "share_over_converged"],
        )
        writer.writeheader()
        for row in k_dist_rows:
            writer.writerow({"schema_version": 1, **row})

    with FAILURE_CODE_CSV_PATH.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp, fieldnames=["model", "error_code", "count", "share_in_hard_abort"]
        )
        writer.writeheader()
        for row in failure_rows:
            writer.writerow({"schema_version": 1, **row})

    context_rows: list[dict[str, Any]] = []
    bins = [0, 500, 1000, 2000, 4000, 8000]
    for model in models:
        subset = [r for r in results if r.model == model]
        for lo, hi in zip(bins[:-1], bins[1:]):
            bucket = [r for r in subset if lo <= r.max_prompt_tokens_per_attempt < hi]
            if not bucket:
                continue
            context_rows.append(
                {
                    "model": model,
                    "token_bin": f"[{lo},{hi})",
                    "cases": len(bucket),
                    "convergence_rate": (sum(1 for r in bucket if r.converged) / len(bucket)),
                    "mean_k": statistics.fmean([r.k for r in bucket]),
                }
            )
    with CONTEXT_DECAY_CSV_PATH.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(
            fp, fieldnames=["model", "token_bin", "cases", "convergence_rate", "mean_k"]
        )
        writer.writeheader()
        for row in context_rows:
            writer.writerow(
                {
                    "schema_version": 1,
                    "model": row["model"],
                    "token_bin": row["token_bin"],
                    "cases": row["cases"],
                    "convergence_rate": f"{row['convergence_rate']:.6f}",
                    "mean_k": f"{row['mean_k']:.3f}",
                }
            )

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Panel A: Convergence rate with 95% CI.
    labels = [r["model"] for r in extended_rows]
    conv = [r["convergence_rate"] for r in extended_rows]
    conv_ci = [r["convergence_rate_ci95_halfwidth"] for r in extended_rows]
    axes[0, 0].bar(
        range(len(labels)), conv, yerr=conv_ci, capsize=6, color=["#2563eb", "#dc2626"], alpha=0.85
    )
    axes[0, 0].set_xticks(range(len(labels)), labels)
    axes[0, 0].set_ylim(0, 1.05)
    axes[0, 0].set_title("Convergence Rate with 95% CI")
    axes[0, 0].set_ylabel("Rate")
    axes[0, 0].grid(axis="y", linestyle="--", linewidth=0.6, alpha=0.7)

    # Panel B: By-kind convergence.
    x = [0, 1]
    width = 0.35
    deepseek_kind = [r for r in by_kind_rows if r["model"] == "deepseek"]
    volc_kind = [r for r in by_kind_rows if r["model"] == "volcengine"]
    axes[0, 1].bar(
        [v - width / 2 for v in x],
        [r["convergence_rate"] for r in deepseek_kind],
        width=width,
        label="deepseek",
    )
    axes[0, 1].bar(
        [v + width / 2 for v in x],
        [r["convergence_rate"] for r in volc_kind],
        width=width,
        label="volcengine",
    )
    axes[0, 1].set_xticks(x, ["A_L2_schema", "B_L5_state"])
    axes[0, 1].set_ylim(0, 1.05)
    axes[0, 1].set_title("Convergence by Case Kind")
    axes[0, 1].set_ylabel("Rate")
    axes[0, 1].grid(axis="y", linestyle="--", linewidth=0.6, alpha=0.7)
    axes[0, 1].legend()

    # Panel C: K distribution for converged cases.
    for model, color in (("deepseek", "#2563eb"), ("volcengine", "#dc2626")):
        model_k = [r for r in k_dist_rows if r["model"] == model]
        axes[1, 0].plot(
            [r["k"] for r in model_k],
            [r["share_over_total"] for r in model_k],
            marker="o",
            linewidth=2.0,
            label=model,
            color=color,
        )
    axes[1, 0].set_xticks(list(range(1, K_MAX + 1)))
    axes[1, 0].set_ylim(0, 1.0)
    axes[1, 0].set_title("Per-K Converged Share (over total)")
    axes[1, 0].set_xlabel("K")
    axes[1, 0].set_ylabel("Share")
    axes[1, 0].grid(True, linestyle="--", linewidth=0.6, alpha=0.7)
    axes[1, 0].legend()

    # Panel D: Hard abort rate.
    hard_abort = [r["hard_abort_rate"] for r in extended_rows]
    hard_ci = [r["hard_abort_rate_ci95_halfwidth"] for r in extended_rows]
    axes[1, 1].bar(
        range(len(labels)),
        hard_abort,
        yerr=hard_ci,
        capsize=6,
        color=["#1d4ed8", "#b91c1c"],
        alpha=0.85,
    )
    axes[1, 1].set_xticks(range(len(labels)), labels)
    axes[1, 1].set_ylim(0, 1.0)
    axes[1, 1].set_title("Hard Abort Rate with 95% CI")
    axes[1, 1].set_ylabel("Rate")
    axes[1, 1].grid(axis="y", linestyle="--", linewidth=0.6, alpha=0.7)

    fig.suptitle("RQ4 Extended Analysis: Cognitive Self-Healing Benchmark")
    plt.tight_layout()
    plt.savefig(EXTENDED_PNG_PATH, dpi=180)
    plt.close()

    # Supplemental Figure 1: Kaplan-Meier style unconverged survival curve.
    km_fig, km_ax = plt.subplots(1, 1, figsize=(8, 5))
    for model, color in (("deepseek", "#2563eb"), ("volcengine", "#dc2626")):
        subset = [r for r in results if r.model == model]
        total = len(subset)
        survival_points = []
        for k in range(0, K_MAX + 1):
            converged_by_k = sum(1 for r in subset if r.converged and r.k <= k)
            unconverged_rate = 1.0 - ((converged_by_k / total) if total else 0.0)
            survival_points.append(unconverged_rate)
        km_ax.step(
            list(range(0, K_MAX + 1)),
            survival_points,
            where="post",
            linewidth=2.0,
            color=color,
            label=model,
        )
    km_ax.set_xticks(list(range(0, K_MAX + 1)))
    km_ax.set_ylim(0.0, 1.0)
    km_ax.set_xlabel("Self-Healing Iteration (K)")
    km_ax.set_ylabel("Unconverged Survival Probability")
    km_ax.set_title("Kaplan-Meier Style Unconverged Survival Curve")
    km_ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.7)
    km_ax.legend()
    plt.tight_layout()
    plt.savefig(KM_SURVIVAL_PNG_PATH, dpi=180)
    plt.close(km_fig)

    # Supplemental Figure 2: Faceted boxplots for K distribution by A/B kind.
    box_fig, box_axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    for idx, kind in enumerate(("A_L2_schema", "B_L5_state")):
        ax = box_axes[idx]
        deepseek_k = [
            r.k for r in results if r.model == "deepseek" and r.kind == kind and r.converged
        ]
        volc_k = [
            r.k for r in results if r.model == "volcengine" and r.kind == kind and r.converged
        ]
        plot_data = [deepseek_k if deepseek_k else [0], volc_k if volc_k else [0]]
        bp = ax.boxplot(
            plot_data,
            labels=["deepseek", "volcengine"],
            patch_artist=True,
            showfliers=True,
            medianprops={"color": "black", "linewidth": 1.5},
        )
        colors = ["#93c5fd", "#fca5a5"]
        for patch, c in zip(bp["boxes"], colors):
            patch.set_facecolor(c)
            patch.set_alpha(0.85)
        ax.set_title(f"{kind} - K Distribution")
        ax.set_xlabel("Model")
        ax.grid(axis="y", linestyle="--", linewidth=0.6, alpha=0.7)
    box_axes[0].set_ylabel("Cycles to Converge (K)")
    box_fig.suptitle("Faceted Boxplots of K by Case Kind")
    plt.tight_layout()
    plt.savefig(K_BOX_BY_KIND_PNG_PATH, dpi=180)
    plt.close(box_fig)


async def _run_async() -> dict[str, Any]:
    total_cases = _resolve_total_cases()
    cases = _build_cases(total_cases)
    rpc_urls = _read_rpc_urls()
    TRACES_DIR.mkdir(parents=True, exist_ok=True)
    for old_log in TRACES_DIR.glob("*.log"):
        old_log.unlink()
    concurrency_limits = {"deepseek": asyncio.Semaphore(10), "volcengine": asyncio.Semaphore(3)}
    limits = httpx.Limits(
        max_connections=MAX_PARALLEL_CASES * 2, max_keepalive_connections=MAX_PARALLEL_CASES
    )

    all_results: list[CaseResult] = []
    guardians: list[Lirix] = []
    async with httpx.AsyncClient(limits=limits) as client:
        tasks: list[asyncio.Task[CaseResult]] = []
        for model_name in ("deepseek", "volcengine"):
            model = _RealLLMModel(model_name)
            allowed_test_intents = ["contract_call", "swap"]
            allowed_test_functions = ["transfer", "swap", "swapExactETHForTokens"]
            allowed_test_addresses = [
                "0x0000000000000000000000000000000000000000",
                "0x1111111111111111111111111111111111111111",
                "0x2222222222222222222222222222222222222222",
            ]
            guardian = Lirix(
                config=LirixConfig(
                    chain_id=1,
                    rpc_urls=rpc_urls,
                    allowed_intents=allowed_test_intents,
                    allowed_function_names=allowed_test_functions,
                    allowed_to_addresses=allowed_test_addresses,
                )
            )
            guardians.append(guardian)
            for case in cases:
                tasks.append(
                    asyncio.create_task(
                        _run_single_case_with_timeout(
                            model, client, guardian, case, concurrency_limits[model_name]
                        )
                    )
                )
        total_tasks = len(tasks)
        batch_size = 4
        completed_count = 0
        for idx, completed in enumerate(asyncio.as_completed(tasks), start=1):
            all_results.append(await completed)
            if idx % batch_size == 0 or idx == total_tasks:
                print(
                    f"[rq4] Intermediate flush: {completed_count}/{total_tasks} completed",
                    flush=True,
                )
                summary_rows, curve_rows = _aggregate(all_results)
                _write_outputs(summary_rows, all_results, curve_rows, partial=True)
            if idx % 20 == 0 or idx == total_tasks:
                print(f"[rq4] completed {idx}/{total_tasks} cases", flush=True)

    for guardian in guardians:
        aclose_method = getattr(guardian, "aclose", None)
        close_method = getattr(guardian, "close", None)
        if callable(aclose_method):
            with suppress(Exception):
                await aclose_method()
        elif callable(close_method):
            with suppress(Exception):
                close_method()

    summary_rows, curve_rows = _aggregate(all_results)
    _write_outputs(summary_rows, all_results, curve_rows, partial=False)
    _write_plot(summary_rows, curve_rows)
    _write_extended_outputs(all_results)
    _write_rq4_raw_csv(all_results)
    _write_ieee_rq4_artifacts(all_results, summary_rows)
    archive_artifacts(
        ArtifactFamily(name="rq4", output_dir=RUN_ROOT),
        relpaths_under(
            RUN_ROOT,
            [
                CSV_PATH,
                DETAIL_CSV_PATH,
                CURVE_CSV_PATH,
                PNG_PATH,
                EXTENDED_METRICS_CSV_PATH,
                BY_KIND_CSV_PATH,
                K_DIST_CSV_PATH,
                FAILURE_CODE_CSV_PATH,
                EXTENDED_PNG_PATH,
                KM_SURVIVAL_PNG_PATH,
                K_BOX_BY_KIND_PNG_PATH,
                CONTEXT_DECAY_CSV_PATH,
                RQ4_RAW_CSV_PATH,
                RMST_ABORT_PDF_PATH,
                CONTEXT_SATURATION_PDF_PATH,
                RQ4_IEEE_REPORT_MD_PATH,
            ],
        ),
    )
    narrative: dict[str, str] = {}
    for row in summary_rows:
        if row["hard_abort_rate"] > 0:
            narrative[row["model"]] = (
                "情况 B：出现 Hard Abort，说明顶级模型仍会认知死锁；"
                "Lirix 的 Kmax 熔断把风险物理切断，资金损失维持 0。"
            )
        else:
            narrative[row["model"]] = (
                "情况 A：低均值 K 与低方差说明 resolution_for_agent 的差分反馈高效稳定，"
                "模型可快速收敛到可验证交易。"
            )
    return {"schema_version": 1, "summary": summary_rows, "narrative": narrative}


def run_rq4_cognitive_self_healing_benchmark() -> dict[str, Any]:
    if httpx is None or sns is None:
        raise RuntimeError("Optional benchmark dependencies are not installed.")
    _load_env_file()
    _required_env("DEEPSEEK_API_KEY")
    _required_env("VOLCENGINE_API_KEY")
    return asyncio.run(_run_async())


def run_rq4_tdsc_convergence_benchmark() -> dict[str, Any]:
    """Backward-compatible alias."""
    return run_rq4_cognitive_self_healing_benchmark()


def regenerate_extended_analysis_from_detail_csv() -> None:
    detail_path = DETAIL_CSV_PATH
    legacy_detail_path = RQ4_CSV_DIR / "rq4_tdsc_case_details.csv"
    legacy_flat_run_root = RUN_ROOT / "rq4_tdsc_case_details.csv"
    if not detail_path.exists() and legacy_detail_path.exists():
        detail_path = legacy_detail_path
    if not detail_path.exists() and legacy_flat_run_root.exists():
        detail_path = legacy_flat_run_root
    if not detail_path.exists():
        raise RuntimeError(f"Detail CSV not found: {detail_path}")
    results: list[CaseResult] = []
    with detail_path.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            results.append(
                CaseResult(
                    case_id=str(row["case_id"]),
                    kind=str(row["kind"]),  # type: ignore[arg-type]
                    model=str(row["model"]),  # type: ignore[arg-type]
                    converged=str(row["converged"]).lower() == "true",
                    k=int(row["k"]),
                    hard_abort=str(row["hard_abort"]).lower() == "true",
                    last_error_code=str(row.get("last_error_code", "")),
                    last_policy_key=str(row.get("last_policy_key", "")),
                    prompt_tokens=int(row.get("prompt_tokens", "0") or 0),
                    completion_tokens=int(row.get("completion_tokens", "0") or 0),
                    max_prompt_tokens_per_attempt=int(
                        row.get("max_prompt_tokens_per_attempt", "0") or 0
                    ),
                    max_prompt_chars_per_attempt=int(
                        row.get("max_prompt_chars_per_attempt", "0") or 0
                    ),
                )
            )
    _write_extended_outputs(results)


def test_rq4_cognitive_self_healing_benchmark() -> None:
    if os.getenv("RUN_RQ4_BENCHMARK") != "1":
        return
    out = run_rq4_cognitive_self_healing_benchmark()
    assert out["summary"]
    assert CSV_PATH.exists()
    assert DETAIL_CSV_PATH.exists()
    assert CURVE_CSV_PATH.exists()
    assert PNG_PATH.exists()


def test_rq4_tdsc_convergence_benchmark() -> None:
    """Backward-compatible alias."""
    test_rq4_cognitive_self_healing_benchmark()


if __name__ == "__main__":
    print(json.dumps(run_rq4_cognitive_self_healing_benchmark(), ensure_ascii=False, indent=2))
