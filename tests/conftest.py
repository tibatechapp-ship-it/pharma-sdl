"""Fixtures مشتركة لكل الاختبارات."""
import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.oracle import MultiObjectiveOracle
from core.maker import MoleculeMaker
from core.agent import MultiObjectiveAgent


@pytest.fixture
def sample_features():
    return np.array([450.0, 3.0, 2, 6, 80.0, 5])


@pytest.fixture
def sample_library():
    np.random.seed(42)
    return np.column_stack([
        np.random.normal(450, 100, 20),
        np.random.normal(3, 1.5, 20),
        np.random.randint(0, 6, 20),
        np.random.randint(0, 12, 20),
        np.random.normal(80, 30, 20),
        np.random.randint(0, 8, 20),
    ])


@pytest.fixture
def oracle():
    return MultiObjectiveOracle(seed=42)


@pytest.fixture
def maker():
    return MoleculeMaker(n=20, seed=42)


@pytest.fixture
def agent(sample_library, oracle):
    return MultiObjectiveAgent(sample_library, oracle)
