"""Tests for MIC Lab and PROTAC Lab modules (pure math functions)."""
import numpy as np

from core.mic_lab import DRUGS, compute_metrics, compute_pk
from core.protac_lab import (
    degradation_fraction,
    ternary_fraction,
    traditional_inhibition,
)


class TestComputePK:
    def test_output_shapes(self):
        t, c = compute_pk(350, 17.5, 5.25)
        assert len(t) == 500
        assert len(c) == 500
        assert (c >= 0).all()

    def test_cmax_positive(self):
        _t, c = compute_pk(350, 17.5, 5.25)
        assert c.max() > 0

    def test_decay_after_infusion(self):
        t, c = compute_pk(350, 17.5, 5.25)
        # after infusion ends (t > 0.5), concentration should decay
        post_mask = t > 1.0
        assert c[post_mask].max() > c[post_mask].min()

    def test_zero_dose(self):
        _t, c = compute_pk(0, 17.5, 5.25)
        assert np.allclose(c, 0)


class TestComputeMetrics:
    def test_gentamicin_active(self):
        t, c = compute_pk(350, 17.5, 5.25)
        m = compute_metrics(t, c, 2.0, index='cmax_mic', target=10)
        assert m['verdict'] in ('active', 'warning')
        assert m['cmax_mic'] > 0

    def test_returns_all_keys(self):
        t, c = compute_pk(350, 17.5, 5.25)
        m = compute_metrics(t, c, 2.0)
        assert 'cmax' in m
        assert 'tmax' in m
        assert 'auc' in m
        assert 'verdict' in m
        assert 'governing_value' in m

    def test_failed_when_mic_too_high(self):
        t, c = compute_pk(350, 17.5, 5.25)
        m = compute_metrics(t, c, 100.0, index='cmax_mic', target=10)
        assert m['verdict'] == 'failed'


class TestDRUGS:
    def test_three_drugs(self):
        assert len(DRUGS) == 3
        assert 'gentamicin' in DRUGS
        assert 'ceftriaxone' in DRUGS
        assert 'vancomycin' in DRUGS

    def test_drug_structure(self):
        for drug in DRUGS.values():
            assert 'name' in drug
            assert 'index' in drug
            assert 'dose' in drug
            assert drug['index'] in ('cmax_mic', 'ft_mic', 'auc_mic')


class TestPROTACDegradation:
    def test_output_shape(self):
        conc = np.logspace(-2, 5, 100)
        deg = degradation_fraction(conc, 0.94, 95, 1.0, 100.0)
        assert deg.shape == conc.shape

    def test_max_le_dmax(self):
        conc = np.logspace(-2, 5, 100)
        deg = degradation_fraction(conc, 0.94, 95, 1.0, 100.0)
        assert deg.max() <= 95.1

    def test_hook_effect(self):
        conc = np.logspace(-2, 5, 100)
        deg = degradation_fraction(conc, 0.94, 95, 1.0, 100.0)
        # Hook effect: after peak, degradation should decrease
        peak_idx = np.argmax(deg)
        assert peak_idx < len(deg) - 1
        assert deg[-1] < deg[peak_idx]

    def test_zero_conc(self):
        conc = np.array([0.0])
        deg = degradation_fraction(conc, 0.94, 95, 1.0, 100.0)
        assert deg[0] == 0 or np.isnan(deg[0]) is False


class TestTernaryFraction:
    def test_range(self):
        conc = np.logspace(-2, 5, 100)
        tern = ternary_fraction(conc, 1.0, 100.0)
        assert tern.max() <= 100.1
        assert tern.min() >= 0


class TestTraditionalInhibition:
    def test_monotonic(self):
        conc = np.logspace(-2, 5, 100)
        inh = traditional_inhibition(conc, 10.0, 60.0)
        # traditional inhibition should be monotonically increasing
        assert inh[-1] > inh[0]
