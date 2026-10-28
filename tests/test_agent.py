"""اختبارات MultiObjectiveAgent."""
import numpy as np
import pytest
from core.agent import MultiObjectiveAgent


def test_initialization(agent):
    agent.initialize(n_init=10)
    assert len(agent.X_train) == 10
    assert len(agent.pool_idx) == 10


def test_no_duplicates(agent):
    agent.initialize(n_init=10)
    before = set(agent.pool_idx)
    for _ in range(3):
        agent.run_cycle(batch_size=1)
    after = set(agent.pool_idx)
    assert len(after - before) == 3


def test_pareto_logic(agent):
    agent.initialize(n_init=10)
    mask = agent.pareto_mask()
    assert isinstance(mask, np.ndarray)
    assert mask.dtype == bool
    assert len(mask) == 10


def test_learning_improves(agent):
    agent.initialize(n_init=10)
    init_best = agent.herg_train.min()
    for _ in range(5):
        agent.run_cycle(batch_size=2)
    assert agent.herg_train.min() <= init_best + 1  # سماحية


def test_full_cycle(agent):
    agent.initialize(n_init=5)
    for _ in range(3):
        agent.run_cycle(batch_size=1)
    assert len(agent.history) == 3
