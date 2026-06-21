"""
Tests for the AUC of Degradation metric.

Validates:
  - AUC computation is correct for known score sequences.
  - Normalization maps to [0, 1].
  - AUC without defense > AUC with defense for attack scenarios.
  - Compromise turn is detected correctly.
  - Benign AUC ≈ 0 (H4: no over-refusal).
  - Empty input raises ValueError.
"""
import pytest

from rage_core.metrics.auc_degradation import compute_auc


class TestAUCComputation:
    def test_all_zeros_gives_auc_zero(self):
        result = compute_auc("test", [0, 0, 0, 0])
        assert result.auc_normalized == pytest.approx(0.0)

    def test_all_max_score_gives_auc_one(self):
        result = compute_auc("test", [5, 5, 5, 5])
        assert result.auc_normalized == pytest.approx(1.0)

    def test_known_trapz_value(self):
        # trapz([0,0,5,5], [0,1,2,3]) = 0.5*(0+0)*1 + 0.5*(0+5)*1 + 0.5*(5+5)*1 = 0+2.5+5 = 7.5
        # normalize: 7.5 / (5 * (4-1)) = 7.5 / 15 = 0.5
        result = compute_auc("test", [0, 0, 5, 5])
        assert result.auc_raw == pytest.approx(7.5, rel=1e-3)
        assert result.auc_normalized == pytest.approx(0.5, rel=1e-3)

    def test_single_element_does_not_crash(self):
        result = compute_auc("test", [3])
        assert result.auc_normalized == pytest.approx(0.0)  # 0 / (5*max(0,1)) = 0

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            compute_auc("test", [])


class TestCompromiseTurn:
    def test_compromise_detected_at_correct_index(self):
        result = compute_auc("test", [0, 1, 2, 4, 5])
        assert result.compromise_turn == 3  # first index where score >= 4

    def test_no_compromise_when_all_low(self):
        result = compute_auc("test", [0, 1, 2, 3, 3])
        assert result.compromise_turn is None

    def test_compromise_at_first_turn(self):
        result = compute_auc("test", [5, 0, 0])
        assert result.compromise_turn == 0


class TestDefenseVsNoDefense:
    """H1: AUC(no defense) > AUC(with defense) in attack scenarios."""

    def test_attack_auc_greater_than_defended_auc(self):
        # Undefended: attack succeeds at turn 3, 4, 5
        gt_undefended = [0, 0, 2, 4, 5, 5]
        # Defended: attack blocked at turn 3, contained
        gt_defended   = [0, 0, 1, 1, 1, 0]

        auc_no_def = compute_auc("without defense", gt_undefended)
        auc_def    = compute_auc("with defense",    gt_defended)

        assert auc_no_def.auc_normalized > auc_def.auc_normalized

    def test_benign_auc_near_zero(self):
        """H4: benign conversation should have AUC ≈ 0."""
        gt_benign = [0, 0, 0, 0, 0]
        result = compute_auc("benign", gt_benign)
        assert result.auc_normalized == pytest.approx(0.0)

    def test_auc_normalized_bounded(self):
        import random
        random.seed(42)
        for _ in range(20):
            scores = [random.randint(0, 5) for _ in range(random.randint(2, 10))]
            result = compute_auc("random", scores)
            assert 0.0 <= result.auc_normalized <= 1.0


class TestAUCLabels:
    def test_label_stored_correctly(self):
        result = compute_auc("my scenario", [1, 2, 3])
        assert result.label == "my scenario"

    def test_turns_aligned_with_scores(self):
        scores = [0, 1, 2, 3, 4]
        result = compute_auc("t", scores)
        assert result.turns == list(range(len(scores)))
        assert result.gt_scores == scores


# --------------------------------------------------------------------------- #
# Temporal Resistance Index (TRI) — Crescendo-hardening metric                #
# --------------------------------------------------------------------------- #

class TestTemporalResistanceIndex:
    """Validates compute_tri() introduced in the Crescendo-hardening audit."""

    def test_tri_zero_when_same_compromise_turn(self):
        from rage_core.metrics.auc_degradation import compute_tri
        # Both compromised at turn 2 → no extra resistance → TRI = 0
        undef = compute_auc("without defense", [0, 0, 5, 5])
        defd  = compute_auc("with defense",    [0, 0, 5, 5])
        assert compute_tri(defd, undef) == pytest.approx(0.0)

    def test_tri_positive_when_defense_delays_compromise(self):
        from rage_core.metrics.auc_degradation import compute_tri
        # Undefended: compromise at T2; defended: held until T4 → TRI = (4-2)/5 = 0.4
        undef = compute_auc("without defense", [0, 0, 5, 5, 5])
        defd  = compute_auc("with defense",    [0, 0, 1, 1, 5])
        tri = compute_tri(defd, undef)
        assert tri > 0.0

    def test_tri_maximum_when_defense_never_compromised(self):
        from rage_core.metrics.auc_degradation import compute_tri
        # Undefended: compromise at T0; defended: never compromised → TRI = (N-0)/N = 1.0
        n = 5
        undef = compute_auc("without defense", [5] * n)
        defd  = compute_auc("with defense",    [1] * n)  # blocked every turn, never ≥ 4
        tri = compute_tri(defd, undef)
        # T_defended = N (never compromised), T_undefended = 0 → TRI = N/N = 1.0
        assert tri == pytest.approx(1.0)

    def test_tri_bounded_for_random_sequences(self):
        import random
        from rage_core.metrics.auc_degradation import compute_tri
        random.seed(0)
        for _ in range(20):
            n = random.randint(3, 10)
            undef_scores = [random.randint(0, 5) for _ in range(n)]
            def_scores   = [random.randint(0, 3) for _ in range(n)]  # capped lower
            undef = compute_auc("without defense", undef_scores)
            defd  = compute_auc("with defense",    def_scores)
            tri = compute_tri(defd, undef)
            # TRI is in [-1, 1] for these bounded inputs
            assert -1.0 <= tri <= 1.0
