"""
MultiObjectiveAgent: Active learning with real UCB via Gaussian Process.

Uses two GPs (hERG + LDL) to estimate per-molecule uncertainty.
UCB score combines GP mean ± kappa * GP std (real epistemic uncertainty).
"""
import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel


class MultiObjectiveAgent:
    """Agent that learns molecule properties via active learning (GP-based UCB)."""

    def __init__(self, library, oracle, random_state=42):
        self.library = library
        self.oracle = oracle
        self.random_state = random_state
        self.rng = np.random.default_rng(random_state)

        self.X_train = np.empty((0, library.shape[1]))
        self.herg_train = np.array([])
        self.ldl_train = np.array([])
        self.pool_idx = []
        self.history = []

        kernel = RBF(length_scale=1.0) + WhiteKernel(noise_level=0.1)
        self.gp_herg = GaussianProcessRegressor(
            kernel=kernel, optimizer=None, random_state=random_state, normalize_y=True
        )
        self.gp_ldl = GaussianProcessRegressor(
            kernel=kernel, optimizer=None, random_state=random_state, normalize_y=True
        )

    def initialize(self, n_init=10):
        """Initialize with n_init random molecules."""
        idx = self.rng.choice(len(self.library), size=n_init, replace=False)
        self.pool_idx = list(idx)
        self.X_train = self.library[idx]
        self.herg_train = np.array([self.oracle.herg_toxicity(x) for x in self.X_train])
        self.ldl_train = np.array([self.oracle.ldl_reduction(x) for x in self.X_train])

    def _fit_gps(self):
        if len(self.X_train) >= 2:
            self.gp_herg.fit(self.X_train, self.herg_train)
            self.gp_ldl.fit(self.X_train, self.ldl_train)

    def ucb_score(self, x, kappa=2.0):
        """Real UCB for a single molecule: -mean(herg) + kappa*std(herg) + mean(ldl) + kappa*std(ldl)."""
        if len(self.X_train) < 2:
            return float(-self.oracle.herg_toxicity(x) + self.oracle.ldl_reduction(x))

        self._fit_gps()
        x_2d = np.atleast_2d(x)
        herg_mean, herg_std = self.gp_herg.predict(x_2d, return_std=True)
        ldl_mean, ldl_std = self.gp_ldl.predict(x_2d, return_std=True)
        return float((-herg_mean[0] + kappa * herg_std[0]) + (ldl_mean[0] + kappa * ldl_std[0]))

    def run_cycle(self, batch_size=1, kappa=2.0):
        """One active learning cycle: fit GP once, predict all remaining, pick top."""
        remaining = [i for i in range(len(self.library)) if i not in self.pool_idx]
        if not remaining:
            return

        if len(self.X_train) >= 2:
            self._fit_gps()
            X_remaining = self.library[remaining]
            herg_mean, herg_std = self.gp_herg.predict(X_remaining, return_std=True)
            ldl_mean, ldl_std = self.gp_ldl.predict(X_remaining, return_std=True)
            scores = (-herg_mean + kappa * herg_std) + (ldl_mean + kappa * ldl_std)
        else:
            scores = np.array([
                -self.oracle.herg_toxicity(self.library[i]) + self.oracle.ldl_reduction(self.library[i])
                for i in remaining
            ])

        chosen_positions = np.argsort(scores)[-batch_size:]
        for pos in chosen_positions:
            idx = remaining[pos]
            if idx in self.pool_idx:
                continue
            self.pool_idx.append(idx)
            x = self.library[idx]
            self.X_train = np.vstack([self.X_train, x.reshape(1, -1)])
            self.herg_train = np.append(self.herg_train, self.oracle.herg_toxicity(x))
            self.ldl_train = np.append(self.ldl_train, self.oracle.ldl_reduction(x))

        self.history.append({"batch": batch_size, "pool_size": len(self.pool_idx)})

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
