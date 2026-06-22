"""Tests for the RAGE product demo orchestrator and CLI."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from rage_core.demo.attacks import ALL_SCENARIOS, SCENARIO_BENIGN, SCENARIO_DROP_TABLE
from rage_core.demo.demo_scenarios import ALL_DEMO_SCENARIOS, CORE_DEMO_SCENARIOS
from rage_core.demo.orchestrator import ScenarioOrchestrator
from rage_core.metrics.auc_degradation import compute_auc

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestScenarioOrchestrator:
    def test_defended_beats_undefended_on_drop_table(self) -> None:
        orch = ScenarioOrchestrator(use_judge=False)
        undef = orch.run("drop_table_escalation", SCENARIO_DROP_TABLE, defended=False)
        defended = orch.run("drop_table_escalation", SCENARIO_DROP_TABLE, defended=True)
        auc_u = compute_auc("without", undef.gt_scores)
        auc_d = compute_auc("with", defended.gt_scores)
        assert auc_d.auc_normalized < auc_u.auc_normalized

    def test_benign_low_auc_both_modes(self) -> None:
        orch = ScenarioOrchestrator(use_judge=False)
        for defended in (True, False):
            run = orch.run("benign", SCENARIO_BENIGN, defended=defended)
            auc = compute_auc("benign", run.gt_scores)
            assert auc.auc_normalized <= 0.2

    def test_all_core_scenarios_run_without_crash(self) -> None:
        orch = ScenarioOrchestrator(use_judge=False)
        for name in CORE_DEMO_SCENARIOS:
            turns = ALL_DEMO_SCENARIOS[name]
            for defended in (True, False):
                run = orch.run(name, turns, defended=defended)
                assert len(run.records) == len(turns)

    def test_extended_demo_has_many_cases(self) -> None:
        assert len(ALL_DEMO_SCENARIOS) >= 30
        assert len(CORE_DEMO_SCENARIOS) >= 14
        assert len(ALL_SCENARIOS) >= 6


class TestRageDemoCli:
    def test_list_scenarios(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-m", "rage_core.demo.cli", "--list"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=120,
        )
        assert proc.returncode == 0
        assert "drop_table_escalation" in proc.stdout
        assert "probe_subtle_board" in proc.stdout

    def test_offline_demo_runs(self) -> None:
        proc = subprocess.run(
            [sys.executable, "-m", "rage_core.demo.cli", "--offline", "--core", "--no-plot"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=120,
        )
        assert proc.returncode == 0, proc.stderr
        assert "AUC OF DEGRADATION REPORT" in proc.stdout
