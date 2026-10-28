"""اختبارات MultiObjectiveOracle."""
import numpy as np
import pytest
from core.oracle import MultiObjectiveOracle


def test_score_positive(oracle):
    features = np.array([450.0, 3.0, 2, 6, 80.0, 5])
    score = oracle.score(features)
    assert score > 0


def test_batch_score(oracle):
    X = np.array([[450.0, 3.0, 2, 6, 80.0, 5],
                  [300.0, 2.0, 1, 4, 60.0, 3]])
    scores = oracle.batch_score(X)
    assert len(scores) == 2
    assert (scores > 0).all()


def test_herg_toxicity_range(oracle):
    features = np.array([450.0, 3.0, 2, 6, 80.0, 5])
    h = oracle.herg_toxicity(features)
    assert h > 0


def test_ldl_reduction_range(oracle):
    features = np.array([450.0, 3.0, 2, 6, 80.0, 5])
    l = oracle.ldl_reduction(features)
    assert 0 <= l <= 80
