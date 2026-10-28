"""
MultiObjectiveAgent: Active learning with UCB + Pareto optimization.
"""
import numpy as np
from scipy.stats import norm


class MultiObjectiveAgent:
    """Agent that learns molecule properties via active learning."""

    def __init__(self, library, oracle):
        self.library = library
        self.oracle = oracle
        self.X_train = np.array([]).reshape(0, 6)
        self.herg_train = np.array([])
        self.ldl_train = np.array([])
        self.pool_idx = []
        self.history = []

    def initialize(self, n_init=10):
        """Initialize with n_init random molecules."""
        idx = np.random.choice(len(self.library), size=n_init, replace=False)
        self.pool_idx = list(idx)
        self.X_train = self.library[idx]
        scores = self.oracle.batch_score(self.X_train)
        self.herg_train = np.array([self.oracle.herg_toxicity(x) for x in self.X_train])
        self.ldl_train = np.array([self.oracle.ldl_reduction(x) for x in self.X_train])

    def ucb_score(self, x, kappa=2.0):
        """Upper Confidence Bound for exploration."""
        mean = self.oracle.score(x)
        std = 1.0 / (1 + len(self.X_train))
        return mean + kappa * std

    def pareto_mask(self):
        """Boolean mask of Pareto-optimal points (maximize LDL, minimize hERG)."""
        if len(self.herg_train) == 0:
            return np.array([], dtype=bool)
        mask = np.ones(len(self.herg_train), dtype=bool)
        for i in range(len(self.herg_train)):
            for j in range(len(self.herg_train)):
                if i == j:
                    continue
                if (self.herg_train[j] <= self.herg_train[i] and
                        self.ldl_train[j] >= self.ldl_train[i] and
                        (self.herg_train[j] < self.herg_train[i] or
                         self.ldl_train[j] > self.ldl_train[i])):
                    mask[i] = False
                    break
        return mask

    def run_cycle(self, batch_size=1):
        """Run one active learning cycle."""
        remaining = [i for i in range(len(self.library)) if i not in self.pool_idx]
        if not remaining:
            return
        scores = [self.ucb_score(self.library[i]) for i in remaining]
        chosen = np.argsort(scores)[-batch_size:]
        for c in chosen:
            idx = remaining[c]
            self.pool_idx.append(idx)
            x = self.library[idx]
            self.X_train = np.vstack([self.X_train, x.reshape(1, -1)])
            self.herg_train = np.append(self.herg_train, self.oracle.herg_toxicity(x))
            self.ldl_train = np.append(self.ldl_train, self.oracle.ldl_reduction(x))
        self.history.append({"batch": batch_size, "pool_size": len(self.pool_idx)})
