"""Product benchmark evaluator — ChatGate + BotProfile path (Track B)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field

from rage_core.benchmark.product_dataset import ProductCase, ProductScenario
from rage_core.gate.chat_gate import ChatGate
from rage_core.profiles.bot_profile import BotProfile, load_bot_profile

_MOCK_ASSISTANT_REPLY = "[mock assistant reply]"


@dataclass
class ProductCaseResult:
    case_id: str
    profile_id: str
    text: str
    is_attack: bool
    category: str
    description: str
    blocked: bool
    action: str
    judge_used: bool
    judge_reason: str
    policy_would_block: bool
    judge_override: bool
    rage_ms: float
    judge_ms: float
    turn_index: int
    scenario_id: str = ""
    source: str = "eval:product"

    @property
    def total_ms(self) -> float:
        return self.rage_ms + self.judge_ms

    @property
    def correct(self) -> bool:
        return self.blocked == self.is_attack

    @property
    def outcome(self) -> str:
        if self.is_attack and self.blocked:
            return "TP"
        if not self.is_attack and not self.blocked:
            return "TN"
        if not self.is_attack and self.blocked:
            return "FP"
        return "FN"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ProductMetrics:
    total: int
    correct: int
    tp: int
    tn: int
    fp: int
    fn: int
    accuracy: float
    precision: float
    recall: float
    f1: float
    false_positive_rate: float
    judge_override_count: int
    judge_override_rate: float
    judge_saved_fp: int = 0
    judge_added_block: int = 0


@dataclass
class LatencyStats:
    rage_ms_p50: float = 0.0
    rage_ms_p95: float = 0.0
    judge_ms_p50: float = 0.0
    judge_ms_p95: float = 0.0
    total_ms_p50: float = 0.0
    total_ms_p95: float = 0.0
    clean_turn_count: int = 0
    flagged_turn_count: int = 0
    clean_total_ms_p50: float = 0.0
    flagged_total_ms_p50: float = 0.0


OnProductResult = Callable[[ProductCaseResult], None]


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return ordered[idx]


def _gate_to_result(
    *,
    case_id: str,
    profile_id: str,
    text: str,
    is_attack: bool,
    category: str,
    description: str,
    gate_result,
    turn_index: int,
    scenario_id: str = "",
) -> ProductCaseResult:
    policy_block = gate_result.briefing.policy_would_block
    blocked = gate_result.blocked
    judge_used = gate_result.judge_used
    judge_override = judge_used and (policy_block != blocked)
    return ProductCaseResult(
        case_id=case_id,
        profile_id=profile_id,
        text=text,
        is_attack=is_attack,
        category=category,
        description=description,
        blocked=blocked,
        action=gate_result.action,
        judge_used=judge_used,
        judge_reason=gate_result.judge_reason,
        policy_would_block=policy_block,
        judge_override=judge_override,
        rage_ms=gate_result.rage_ms,
        judge_ms=gate_result.judge_ms,
        turn_index=turn_index,
        scenario_id=scenario_id,
    )


def run_product_case(
    profile: BotProfile,
    case: ProductCase,
    *,
    use_judge_api: bool,
    gate: ChatGate | None = None,
) -> ProductCaseResult:
    owned_gate = gate is None
    if gate is None:
        gate = ChatGate(profile, use_judge_api=use_judge_api)
    result = gate.evaluate(case.text)
    if result.allowed:
        gate.record_assistant(_MOCK_ASSISTANT_REPLY)
    out = _gate_to_result(
        case_id=case.id,
        profile_id=profile.profile_id,
        text=case.text,
        is_attack=case.is_attack,
        category=case.category,
        description=case.description,
        gate_result=result,
        turn_index=0,
    )
    if owned_gate:
        gate.reset()
    return out


def run_product_scenario(
    profile: BotProfile,
    scenario: ProductScenario,
    *,
    use_judge_api: bool,
) -> list[ProductCaseResult]:
    gate = ChatGate(profile, use_judge_api=use_judge_api)
    results: list[ProductCaseResult] = []
    for idx, turn in enumerate(scenario.turns):
        gate_result = gate.evaluate(turn.text)
        if gate_result.allowed:
            gate.record_assistant(_MOCK_ASSISTANT_REPLY)
        results.append(
            _gate_to_result(
                case_id=f"{scenario.id}:t{idx}",
                profile_id=profile.profile_id,
                text=turn.text,
                is_attack=turn.is_attack,
                category=scenario.category,
                description=turn.description or scenario.description,
                gate_result=gate_result,
                turn_index=idx,
                scenario_id=scenario.id,
            )
        )
    gate.reset()
    return results


def run_product_benchmark(
    cases: list[ProductCase],
    scenarios: list[ProductScenario],
    *,
    use_judge_api: bool,
    on_result: OnProductResult | None = None,
) -> list[ProductCaseResult]:
    results: list[ProductCaseResult] = []
    for case in cases:
        profile = load_bot_profile(case.profile_id)
        result = run_product_case(profile, case, use_judge_api=use_judge_api)
        results.append(result)
        if on_result:
            on_result(result)
    for scenario in scenarios:
        profile = load_bot_profile(scenario.profile_id)
        scenario_results = run_product_scenario(profile, scenario, use_judge_api=use_judge_api)
        results.extend(scenario_results)
        if on_result:
            for result in scenario_results:
                on_result(result)
    return results


def compute_product_metrics(results: list[ProductCaseResult]) -> ProductMetrics:
    total = len(results)
    tp = sum(1 for r in results if r.outcome == "TP")
    tn = sum(1 for r in results if r.outcome == "TN")
    fp = sum(1 for r in results if r.outcome == "FP")
    fn = sum(1 for r in results if r.outcome == "FN")
    correct = tp + tn
    accuracy = correct / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    fp_rate = fp / (fp + tn) if (fp + tn) else 0.0
    judged = [r for r in results if r.judge_used]
    overrides = [r for r in judged if r.judge_override]
    saved_fp = sum(1 for r in overrides if r.policy_would_block and not r.blocked)
    added_block = sum(1 for r in overrides if not r.policy_would_block and r.blocked)
    override_rate = len(overrides) / len(judged) if judged else 0.0
    return ProductMetrics(
        total=total,
        correct=correct,
        tp=tp,
        tn=tn,
        fp=fp,
        fn=fn,
        accuracy=accuracy,
        precision=precision,
        recall=recall,
        f1=f1,
        false_positive_rate=fp_rate,
        judge_override_count=len(overrides),
        judge_override_rate=override_rate,
        judge_saved_fp=saved_fp,
        judge_added_block=added_block,
    )


def compute_latency_stats(results: list[ProductCaseResult]) -> LatencyStats:
    rage = [r.rage_ms for r in results]
    judge = [r.judge_ms for r in results]
    total = [r.total_ms for r in results]
    clean = [r for r in results if not r.judge_used]
    flagged = [r for r in results if r.judge_used]
    clean_totals = [r.total_ms for r in clean]
    flagged_totals = [r.total_ms for r in flagged]
    return LatencyStats(
        rage_ms_p50=_percentile(rage, 50),
        rage_ms_p95=_percentile(rage, 95),
        judge_ms_p50=_percentile(judge, 50),
        judge_ms_p95=_percentile(judge, 95),
        total_ms_p50=_percentile(total, 50),
        total_ms_p95=_percentile(total, 95),
        clean_turn_count=len(clean),
        flagged_turn_count=len(flagged),
        clean_total_ms_p50=_percentile(clean_totals, 50),
        flagged_total_ms_p50=_percentile(flagged_totals, 50),
    )


def metrics_by_profile(results: list[ProductCaseResult]) -> dict[str, ProductMetrics]:
    by_profile: dict[str, list[ProductCaseResult]] = {}
    for result in results:
        by_profile.setdefault(result.profile_id, []).append(result)
    return {pid: compute_product_metrics(items) for pid, items in sorted(by_profile.items())}


def metrics_by_category(results: list[ProductCaseResult]) -> dict[str, ProductMetrics]:
    by_cat: dict[str, list[ProductCaseResult]] = {}
    for result in results:
        by_cat.setdefault(result.category, []).append(result)
    return {cat: compute_product_metrics(items) for cat, items in sorted(by_cat.items())}


def export_run_json(
    results: list[ProductCaseResult],
    *,
    mode: str,
    profile_default: str,
    run_id: str,
) -> dict:
    metrics = compute_product_metrics(results)
    latency = compute_latency_stats(results)
    return {
        "run_id": run_id,
        "mode": mode,
        "profile_default": profile_default,
        "metrics": asdict(metrics),
        "latency": asdict(latency),
        "by_profile": {k: asdict(v) for k, v in metrics_by_profile(results).items()},
        "by_category": {k: asdict(v) for k, v in metrics_by_category(results).items()},
        "cases": [r.to_dict() for r in results],
    }
