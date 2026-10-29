"""Tests for CYP2C19 pharmacogenomics lab."""
import numpy as np

from core.cyp2c19_lab import (
    PHENOTYPES,
    RECOMMENDATIONS,
    predict_platelet_inhibition,
    simulate_time_course,
)


class TestPhenotypes:
    def test_four_phenotypes(self):
        assert set(PHENOTYPES.keys()) == {'UM', 'NM', 'IM', 'PM'}

    def test_activity_scores(self):
        assert PHENOTYPES['UM']['activity_score'] == 3.0
        assert PHENOTYPES['NM']['activity_score'] == 2.0
        assert PHENOTYPES['IM']['activity_score'] == 1.0
        assert PHENOTYPES['PM']['activity_score'] == 0.0

    def test_each_has_genotypes(self):
        for p in PHENOTYPES.values():
            assert len(p['genotypes']) >= 1
            assert 'name_ar' in p
            assert 'color' in p

    def test_prevalence_strings(self):
        for p in PHENOTYPES.values():
            assert '%' in p['prevalence_me']
            assert '%' in p['prevalence_ar']


class TestRecommendations:
    def test_all_phenotypes_have_recommendations(self):
        for key in PHENOTYPES:
            assert key in RECOMMENDATIONS
            rec = RECOMMENDATIONS[key]
            assert 'clopidogrel' in rec
            assert 'alternative' in rec
            assert 'detail' in rec
            assert 'strength' in rec
            assert 'color' in rec

    def test_pm_not_recommended(self):
        rec = RECOMMENDATIONS['PM']
        assert 'غير موصى' in rec['clopidogrel'] or '❌' in rec['clopidogrel']

    def test_um_nm_standard_dose(self):
        for key in ['UM', 'NM']:
            rec = RECOMMENDATIONS[key]
            assert '75 mg' in rec['clopidogrel']

    def test_im_pm_have_alternative(self):
        for key in ['IM', 'PM']:
            rec = RECOMMENDATIONS[key]
            assert 'Ticagrelor' in rec['alternative'] or 'Prasugrel' in rec['alternative']


class TestPredictPlateletInhibition:
    def test_pm_low_inhibition(self):
        val = predict_platelet_inhibition(0.0, 75)
        assert val < 20

    def test_nm_high_inhibition(self):
        val = predict_platelet_inhibition(2.0, 75)
        assert val > 60

    def test_um_highest(self):
        um = predict_platelet_inhibition(3.0, 75)
        nm = predict_platelet_inhibition(2.0, 75)
        im = predict_platelet_inhibition(1.0, 75)
        pm = predict_platelet_inhibition(0.0, 75)
        assert um > nm > im > pm

    def test_dose_increases_inhibition(self):
        low = predict_platelet_inhibition(2.0, 75)
        high = predict_platelet_inhibition(2.0, 300)
        assert high > low

    def test_returns_float(self):
        val = predict_platelet_inhibition(2.0, 75)
        assert isinstance(val, (int, float, np.floating))

    def test_unknown_activity_score(self):
        val = predict_platelet_inhibition(99.0, 75)
        assert val < 30  # defaults to 20 * dose_factor


class TestSimulateTimeCourse:
    def test_returns_arrays(self):
        t, response = simulate_time_course(2.0, 75)
        assert isinstance(t, np.ndarray)
        assert isinstance(response, np.ndarray)
        assert len(t) == 200
        assert len(response) == 200

    def test_time_starts_at_zero(self):
        t, _ = simulate_time_course(2.0, 75)
        assert t[0] == 0.0

    def test_response_non_negative(self):
        _, response = simulate_time_course(0.0, 75)
        assert np.all(response >= 0)

    def test_peak_in_reasonable_range(self):
        _, response = simulate_time_course(2.0, 75)
        assert 50 < response.max() < 100

    def test_custom_duration(self):
        t, _ = simulate_time_course(2.0, 75, duration_hours=24)
        assert t[-1] == 24.0

    def test_pm_peak_lower_than_nm(self):
        _, r_pm = simulate_time_course(0.0, 75)
        _, r_nm = simulate_time_course(2.0, 75)
        assert r_pm.max() < r_nm.max()
