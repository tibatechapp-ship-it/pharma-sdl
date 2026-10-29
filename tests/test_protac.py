"""اختبارات PROTAC."""
import numpy as np

from core.protac import VEPDEGESTRANT


def test_degradation_range():
    conc = np.logspace(-3, 4, 100)
    deg = VEPDEGESTRANT.degradation_fraction(conc)
    assert (deg >= 0).all()
    assert (deg <= VEPDEGESTRANT.dmax + 0.1).all()


def test_dc50_definition():
    """عند DC50، التحلل = Dmax/2."""
    deg_at_dc50 = VEPDEGESTRANT.degradation_fraction([VEPDEGESTRANT.dc50])[0]
    assert abs(deg_at_dc50 - VEPDEGESTRANT.dmax / 2) < 0.1


def test_simulation():
    sol = VEPDEGESTRANT.simulate(t_days=7)
    assert sol.success
    assert len(sol.t) > 0
    assert sol.y[2].min() >= 0


def test_ternary_formation():
    conc = np.logspace(-2, 3, 50)
    ternary = VEPDEGESTRANT.ternary_formation(conc)
    assert (ternary >= 0).all()
    assert (ternary <= 100).all()
