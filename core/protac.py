"""
PROTAC Model: نمذجة رياضية لكيميرا استهداف التحلل.
الأساس: Vepdegestrant (Veppanu) — أول PROTAC معتمد من FDA (1 مايو 2026).
"""
import numpy as np
from scipy.integrate import solve_ivp


class PROTAC:
    """
    تمثيل رياضي لكيميرا PROTAC.

    Args:
        name: اسم المركب
        dc50: تركيز نصف التحلل (nM)
        dmax: أقصى نسبة تحلل (%)
        hill_n: معامل Hill
        linker_len: طول الرابط (ذرات)
    """

    def __init__(self, name, dc50, dmax, hill_n=1.0, linker_len=12):
        self.name = name
        self.dc50 = dc50
        self.dmax = dmax
        self.hill_n = hill_n
        self.linker_len = linker_len

    def degradation_fraction(self, conc):
        """نسبة تحلل الهدف عند تركيز [conc]."""
        c = np.asarray(conc, dtype=float)
        return self.dmax * (c**self.hill_n) / (
            self.dc50**self.hill_n + c**self.hill_n
        )

    def ternary_formation(self, conc, ka_er=1.0, ka_crbn=0.5, alpha=3.0):
        """
        نسبة تكوين المعقد الثلاثي (ERα-PROTAC-CRBN).
        alpha = معامل التعاونية الإيجابية.
        """
        c = np.asarray(conc, dtype=float)
        p_er = 1 - np.exp(-ka_er * c / 100)
        p_crbn = 1 - np.exp(-ka_crbn * c / 100)
        p_ternary = alpha * p_er * p_crbn / (1 + alpha * p_er * p_crbn)
        return p_ternary * 100

    @staticmethod
    def pkpd_model(t, y, dose, vd, cl, ka, dc50, dmax, k_deg, k_syn):
        """نظام ODE لـ PK/PD."""
        C_gut, C_plasma, R = y
        dC_gut = -ka * C_gut
        dC_plasma = ka * C_gut / vd - (cl / vd) * C_plasma
        degradation = (dmax / 100) * (
            C_plasma**1.2 / (dc50**1.2 + C_plasma**1.2)
        )
        dR = k_syn - k_deg * R - k_deg * degradation * R
        return [dC_gut, dC_plasma, dR]

    def simulate(self, dose=200, vd=300, cl=12, ka=0.5,
                 k_deg=0.05, k_syn=5.0, t_days=7):
        """محاكاة 7 أيام من PK/PD."""
        t_span = (0, t_days * 24)
        t_eval = np.linspace(0, t_days * 24, 500)
        y0 = [dose, 0, 100]
        return solve_ivp(
            self.pkpd_model, t_span, y0,
            args=(dose, vd, cl, ka, self.dc50, self.dmax, k_deg, k_syn),
            t_eval=t_eval, max_step=1.0
        )


# نموذج Vepdegestrant (FDA 2026)
VEPDEGESTRANT = PROTAC(
    name="Vepdegestrant (Veppanu)",
    dc50=0.94,
    dmax=95.0,
    hill_n=1.2,
    linker_len=12,
)

# نموذج Omaveloxolone (مخلّب STING — للمقارنة)
OMAVELOXOLONE = PROTAC(
    name="Omaveloxolone (STING degrader)",
    dc50=118.0,
    dmax=98.6,
    hill_n=1.0,
    linker_len=0,
)
