"""
Multi-Objective Oracle: hERG toxicity + LDL-C efficacy scoring.
"""
import numpy as np


class MultiObjectiveOracle:
    """Oracle that scores molecules on hERG toxicity and LDL-C reduction."""

    def __init__(self, seed=42):
        self.rng = np.random.default_rng(seed)
        self.weights = np.array([0.5, 0.5])

    def herg_toxicity(self, features):
        """Predict hERG IC50 (lower = more toxic)."""
        mw, logp, _hbd, _hba, tpsa, _rot = features
        base = 10.0 + 0.02 * mw + 0.5 * logp - 0.01 * tpsa
        noise = self.rng.normal(0, 0.5)
        return max(0.1, base + noise)

    def ldl_reduction(self, features):
        """Predict LDL-C reduction percentage."""
        mw, logp, _hbd, _hba, tpsa, _rot = features
        base = 20.0 + 0.05 * mw - 0.3 * logp + 0.1 * tpsa
        noise = self.rng.normal(0, 2.0)
        return max(0, min(80, base + noise))

    def score(self, features):
        """Combined score: lower hERG + higher LDL = better."""
        h = self.herg_toxicity(features)
        l = self.ldl_reduction(features)
        return l / (h + 1e-6)

    def batch_score(self, X):
        return np.array([self.score(x) for x in X])
