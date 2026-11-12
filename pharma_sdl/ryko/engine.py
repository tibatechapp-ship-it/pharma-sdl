"""RykoEngine — العقل المنسّق: سجل العمليات + الحاكم + الإيصال.

كل عملية تُعلن: وحدتها، معادلتها، مصدرها، افتراضاتها، ومدخلاتها. الحساب
يمر عبر حاكم ما قبل الحساب (داخل كل دالة)، والناتج يخرج إيصالاً قابلاً
للتحقق دون اتصال — مستوحى من إيصالات ZYKO (§2 من الخطة).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from . import (
    chem_core,
    diagnostics_seed,
    math_core,
    pharma_core,
    pharmaceutics_core,
    physics_core,
)
from .errors import RykoError, RykoInputError, RykoUnknownOpError
from .receipts import RykoReceipt

RYKO_VERSION = "0.19.0"


@dataclass(frozen=True)
class OpSpec:
    """مواصفة عملية مُعلنة — الكتالوج هو الواجهة العلمية للحساب."""

    fn: Callable[..., tuple[float | str, dict]]
    unit: str
    formula: str
    source: str
    inputs: tuple[tuple[str, str], ...]  # (اسم المدخل، وصفه)
    assumptions: tuple[str, ...] = ()


MODULE_TITLES: dict[str, str] = {
    "math": "الرياضيات والحساب الدوائي",
    "physics": "الفيزياء — ديناميكا حرارية وانتقال",
    "chem": "الكيمياء — واصفات وأيونبة",
    "pharmaceutics": "الصيدلانيات — انحلال وBCS وجرعات",
    "pharma": "الفارماكولوجيا — Hill وأمان وتفاعلات",
    "diagnostics": "مرحلة 2 — التشخيص البايزي (بذرة)",
}

OPS: dict[str, dict[str, OpSpec]] = {}


def _register(module: str, op: str, spec: OpSpec) -> None:
    OPS.setdefault(module, {})[op] = spec


# ── math ──
_register("math", "convert", OpSpec(
    fn=math_core.convert,
    unit="converted", formula="value × factor", source="SI",
    inputs=(("value", "القيمة"), ("from_unit", "الوحدة من"), ("to_unit", "الوحدة إلى"),
            ("molar_mass", "الكتلة المولية (لتحويل مول — اختياري)")),
))
_register("math", "auc_trapz", OpSpec(
    fn=math_core.auc_trapz,
    unit="conc×time", formula="AUC = Σ (C₁+C₂)/2 × Δt",
    source="Gabrielsson & Weiner 2007",
    inputs=(("times", "الأزمنة (قائمة)"), ("concs", "التراكيز (قائمة)"),
            ("log_tail", "ذيل لوغاريتمي (اختياري)")),
))
_register("math", "half_life", OpSpec(
    fn=math_core.half_life,
    unit="h", formula="t½ = ln(2)/kₑ", source="Rowland & Tozer 2011",
    inputs=(("ke", "ثابت الإطراح 1/h"),),
))
_register("math", "ke_from_half_life", OpSpec(
    fn=math_core.ke_from_half_life,
    unit="1/h", formula="kₑ = ln(2)/t½", source="Rowland & Tozer 2011",
    inputs=(("t_half_h", "العمر النصفي ساعة"),),
))
_register("math", "clearance", OpSpec(
    fn=math_core.clearance,
    unit="L/h", formula="CL = Dose/AUC", source="Rowland & Tozer 2011",
    inputs=(("dose_mg", "الجرعة mg"), ("auc", "المساحة")),
))
_register("math", "volume_distribution", OpSpec(
    fn=math_core.volume_distribution,
    unit="L", formula="Vd = CL/kₑ", source="Rowland & Tozer 2011",
    inputs=(("cl_l_h", "الوضوح L/h"), ("ke", "ثابت الإطراح 1/h")),
))
_register("math", "bioavailability", OpSpec(
    fn=math_core.bioavailability,
    unit="fraction", formula="F = (AUCpo/AUCiv)×(Doseiv/Dosepo)",
    source="Rowland & Tozer 2011",
    inputs=(("auc_po", "AUC فموي"), ("auc_iv", "AUC وريدي"),
            ("dose_po", "جرعة فموية"), ("dose_iv", "جرعة وريدية")),
))
_register("math", "ci95_mean", OpSpec(
    fn=math_core.ci95_mean,
    unit="mean", formula="x̄ ± t(0.975,n−1)·s/√n", source="scipy.stats",
    inputs=(("values", "القيم (قائمة)"),),
))
_register("math", "linear_fit", OpSpec(
    fn=math_core.linear_fit,
    unit="slope", formula="least squares", source="closed form",
    inputs=(("xs", "السينات (قائمة)"), ("ys", "الصادات (قائمة)")),
))

# ── physics ──
_register("physics", "binding_dg", OpSpec(
    fn=physics_core.binding_dg,
    unit="kcal/mol", formula="ΔG = RT·ln(Kd)", source="standard thermodynamics",
    inputs=(("kd_um", "Kd ميكرومولار"), ("temp_c", "الحرارة °C (افتراضي 25)")),
))
_register("physics", "kd_from_dg", OpSpec(
    fn=physics_core.kd_from_dg,
    unit="uM", formula="Kd = exp(ΔG/RT)", source="standard thermodynamics",
    inputs=(("dg_kcal", "ΔG kcal/mol"), ("temp_c", "الحرارة °C (افتراضي 25)")),
))
_register("physics", "stokes_einstein", OpSpec(
    fn=physics_core.stokes_einstein,
    unit="m²/s", formula="D = kT/(6πηr)", source="Einstein 1905",
    inputs=(("radius_nm", "نصف القطر nm"), ("viscosity_mpa_s", "اللزوجة mPa·s"),
            ("temp_c", "الحرارة °C (افتراضي 25)")),
))
_register("physics", "arrhenius_ratio", OpSpec(
    fn=physics_core.arrhenius_ratio,
    unit="k2/k1", formula="k₂/k₁ = exp(−Ea/R × (1/T₂ − 1/T₁))", source="Arrhenius 1889",
    inputs=(("ea_j_per_mol", "طاقة التنشيط J/mol"), ("temp1_c", "الحرارة 1 °C"),
            ("temp2_c", "الحرارة 2 °C")),
))
_register("physics", "vant_hoff_ratio", OpSpec(
    fn=physics_core.vant_hoff_ratio,
    unit="K2/K1", formula="ln(K₂/K₁) = −ΔH/R × (1/T₂ − 1/T₁)", source="van't Hoff",
    inputs=(("dh_j_per_mol", "أنثالبي J/mol"), ("temp1_c", "الحرارة 1 °C"),
            ("temp2_c", "الحرارة 2 °C")),
))
_register("physics", "fick_flux", OpSpec(
    fn=physics_core.fick_flux,
    unit="mol/s", formula="J = D·A·ΔC/Δx", source="Fick 1855",
    inputs=(("diff_m2_s", "معامل الانتشار m²/s"), ("area_m2", "المساحة m²"),
            ("delta_c_mol_m3", "فرق التركيز mol/m³"), ("thickness_m", "السماكة m")),
))

# ── chem ──
_register("chem", "validate_smiles", OpSpec(
    fn=chem_core.validate_smiles,
    unit="smiles", formula="RDKit canonical", source="RDKit 2026.09",
    inputs=(("smiles", "السلسلة"),),
))
_register("chem", "descriptors", OpSpec(
    fn=chem_core.descriptors,
    unit="cLogP", formula="Crippen logP", source="RDKit (Crippen 1999، Ertl 2000)",
    inputs=(("smiles", "السلسلة"),),
))
_register("chem", "lipinski", OpSpec(
    fn=chem_core.lipinski,
    unit="verdict", formula="MW≤500 · cLogP≤5 · HBD≤5 · HBA≤10", source="Lipinski 1997",
    inputs=(("smiles", "السلسلة"),),
))
_register("chem", "ionization_fraction", OpSpec(
    fn=chem_core.ionization_fraction,
    unit="fraction_unionized", formula="acid: 1/(1+10^(pH−pKa)) · base: 1/(1+10^(pKa−pH))",
    source="Henderson-Hasselbalch",
    inputs=(("pka", "pKa"), ("ph", "pH"), ("acid", "حمض؟ (صح/خطأ)")),
))
_register("chem", "physchem_bridge", OpSpec(
    fn=chem_core.physchem_bridge,
    unit="vector_head", formula="core/physchem vector", source="pharma-sdl educational layer",
    inputs=(("smiles", "السلسلة"),),
))

# ── pharmaceutics ──
_register("pharmaceutics", "higuchi_k", OpSpec(
    fn=pharmaceutics_core.higuchi_k,
    unit="amount/√h", formula="Q = k·√t", source="Higuchi 1961/1963",
    inputs=(("times_h", "الأزمنة ساعة (قائمة)"), ("amounts_released", "الكميات المطلقة (قائمة)")),
))
_register("pharmaceutics", "korsmeyer_peppas", OpSpec(
    fn=pharmaceutics_core.korsmeyer_peppas,
    unit="k", formula="Q = k·tⁿ", source="Korsmeyer & Peppas 1983",
    inputs=(("times_h", "الأزمنة ساعة (قائمة)"), ("fraction_released", "الأجزاء 0–1 (قائمة)")),
))
_register("pharmaceutics", "first_order_k", OpSpec(
    fn=pharmaceutics_core.first_order_k,
    unit="1/h", formula="Q(t)=Q∞(1−e^(−kt))", source="release kinetics standard",
    inputs=(("times_h", "الأزمنة ساعة (قائمة)"), ("released_fraction", "أجزاء 0–1 (قائمة)")),
))
_register("pharmaceutics", "zero_order_rate", OpSpec(
    fn=pharmaceutics_core.zero_order_rate,
    unit="amount/h", formula="Q = Q₀ + k·t", source="release kinetics standard",
    inputs=(("times_h", "الأزمنة ساعة (قائمة)"), ("amounts_released", "الكميات (قائمة)")),
))
_register("pharmaceutics", "dose_number", OpSpec(
    fn=pharmaceutics_core.dose_number,
    unit="D0", formula="D₀ = Dose/(Cs×V)", source="Löbenberg & Amidon 2000",
    inputs=(("dose_mg", "الجرعة mg"), ("solubility_mg_ml", "الذوبانية mg/mL"),
            ("volume_ml", "الحجم mL (افتراضي 250)")),
))
_register("pharmaceutics", "bcs_class", OpSpec(
    fn=pharmaceutics_core.bcs_class,
    unit="class", formula="(D₀, permeability) → I/II/III/IV", source="BCS؛ Löbenberg & Amidon 2000",
    inputs=(("dose_number", "رقم الجرعة"), ("permeability_high", "نفاذية عالية؟ (صح/خطأ)")),
))
_register("pharmaceutics", "noyes_whitney_rate", OpSpec(
    fn=pharmaceutics_core.noyes_whitney_rate,
    unit="mg/s", formula="dC/dt = D·A·(Cs−C)/h", source="Noyes & Whitney 1897",
    inputs=(("diff_cm2_s", "الانتشار cm²/s"), ("area_cm2", "المساحة cm²"),
            ("cs_minus_c_mg_ml", "فرق التشبع mg/mL"), ("h_cm", "سماكة الطبقة cm")),
))
_register("pharmaceutics", "cockcroft_gault", OpSpec(
    fn=pharmaceutics_core.cockcroft_gault,
    unit="mL/min", formula="CrCl = ((140−العمر)×وزن)/(72×SCr)×(0.85 إناث)",
    source="Cockcroft & Gault 1976",
    inputs=(("age_y", "العمر سنة"), ("weight_kg", "الوزن كغ"),
            ("scr_mg_dl", "الكرياتينين mg/dL"), ("male", "ذكر؟ (صح/خطأ)")),
))
_register("pharmaceutics", "loading_dose", OpSpec(
    fn=pharmaceutics_core.loading_dose,
    unit="mg", formula="LD = Cp·Vd/F", source="Rowland & Tozer 2011",
    inputs=(("vd_l", "حجم التوزيع L"), ("target_conc_mg_l", "التركيز الهدف mg/L"),
            ("bioavailability_f", "F (افتراضي 1)")),
))
_register("pharmaceutics", "maintenance_rate", OpSpec(
    fn=pharmaceutics_core.maintenance_rate,
    unit="mg/h", formula="معدل الجرعة = CL·Css/F", source="Rowland & Tozer 2011",
    inputs=(("cl_l_h", "الوضوح L/h"), ("css_mg_l", "التركيز الثابت mg/L"),
            ("bioavailability_f", "F (افتراضي 1)")),
))
_register("pharmaceutics", "infusion_css", OpSpec(
    fn=pharmaceutics_core.infusion_css,
    unit="mg/L", formula="Css = معدل التسريب/CL · t95 ≈ 4.32×t½",
    source="Rowland & Tozer 2011",
    inputs=(("rate_mg_h", "معدل التسريب mg/h"), ("cl_l_h", "الوضوح L/h"),
            ("ke", "ثابت الإطراح 1/h (اختياري)")),
))
_register("pharmaceutics", "pediatric_dose", OpSpec(
    fn=pharmaceutics_core.pediatric_dose,
    unit="mg", formula="جرعة = وزن×mg/kg", source="الممارسة المعيارية",
    inputs=(("weight_kg", "الوزن كغ"), ("mg_per_kg", "الجرعة mg/kg")),
))

# ── pharma ──
_register("pharma", "hill_effect", OpSpec(
    fn=pharma_core.hill_effect,
    unit="effect", formula="E = Emax·Cʰ/(EC50ʰ+Cʰ)", source="Hill 1910؛ Goutelle 2008",
    inputs=(("conc", "التركيز"), ("emax", "الحد الأقصى"), ("ec50", "EC50"),
            ("hill_coeff", "معامل Hill (افتراضي 1)")),
))
_register("pharma", "ec50_from_effect", OpSpec(
    fn=pharma_core.ec50_from_effect,
    unit="conc", formula="EC50 = C×(Emax/E − 1)^(1/h)", source="Hill 1910 (عكس)",
    inputs=(("effect", "الأثر"), ("emax", "الحد الأقصى"), ("conc", "التركيز"),
            ("hill_coeff", "معامل Hill (افتراضي 1)")),
))
_register("pharma", "therapeutic_index", OpSpec(
    fn=pharma_core.therapeutic_index,
    unit="ratio", formula="TI = TD50/ED50", source="standard",
    inputs=(("td50", "TD50"), ("ed50", "ED50")),
))
_register("pharma", "certain_safety_factor", OpSpec(
    fn=pharma_core.certain_safety_factor,
    unit="ratio", formula="CSF = TD₁/ED₉₉", source="standard",
    inputs=(("td1", "TD1"), ("ed99", "ED99")),
))
_register("pharma", "cheng_prusoff_ki", OpSpec(
    fn=pharma_core.cheng_prusoff_ki,
    unit="nM", formula="Ki = IC50/(1+[L]/Kd)", source="Cheng & Prusoff 1973",
    inputs=(("ic50", "IC50 nM"), ("ligand_nm", "[L] nM"), ("kd_nm", "Kd nM")),
))
_register("pharma", "cyp_lookup", OpSpec(
    fn=pharma_core.cyp_lookup,
    unit="kb_entry", formula="static declared KB", source="FDA Guidance 2020 (أمثلة معيارية)",
    inputs=(("drug", "اسم الدواء"),),
))
_register("pharma", "ddd_lookup", OpSpec(
    fn=pharma_core.ddd_lookup,
    unit="kb_entry", formula="static declared KB", source="WHO ATC/DDD Index 2024",
    inputs=(("drug", "اسم الدواء"),),
))

# ── diagnostics (مرحلة 2 — بذرة) ──
_register("diagnostics", "ppv_npv", OpSpec(
    fn=diagnostics_seed.ppv_npv,
    unit="PPV", formula="PPV = Se·π/(Se·π + (1−Sp)(1−π))", source="Bayes",
    inputs=(("sensitivity", "الحساسية"), ("specificity", "النوعية"), ("prevalence", "الانتشار")),
))
_register("diagnostics", "likelihood_ratios", OpSpec(
    fn=diagnostics_seed.likelihood_ratios,
    unit="LR+", formula="LR⁺ = Se/(1−Sp) · LR⁻ = (1−Se)/Sp", source="Fagan 1975",
    inputs=(("sensitivity", "الحساسية"), ("specificity", "النوعية")),
))
_register("diagnostics", "post_test_probability", OpSpec(
    fn=diagnostics_seed.post_test_probability,
    unit="probability", formula="odds×LR → probability", source="Fagan 1975",
    inputs=(("pre_test_prob", "الاحتمال المسبق"), ("likelihood_ratio", "نسبة الأرجحية")),
))
_register("diagnostics", "kappa", OpSpec(
    fn=diagnostics_seed.kappa,
    unit="kappa", formula="κ = (Po − Pe)/(1 − Pe)", source="Cohen 1960",
    inputs=(("a", "متفق موجب"), ("b", "خلاف"), ("c", "خلاف"), ("d", "متفق سالب")),
))


class RykoEngine:
    """العقل المنسّق — نفس البوابات لكل وحدة، وناتج دائماً إيصال."""

    def compute(self, module: str, op: str, **inputs: object) -> RykoReceipt:
        """حساب عملية عبر الحاكم — الناتج إيصال قابلة للتحقق دون اتصال."""
        mod = str(module).lower().strip()
        operation = str(op).lower().strip()
        spec = OPS.get(mod, {}).get(operation)
        if spec is None:
            known = sum(len(ops) for ops in OPS.values())
            raise RykoUnknownOpError(
                f"عملية غير معروفة: {module}.{op} — المعروف {known} عملية.",
                f"Unknown operation: {module}.{op} — {known} known operations.",
            )
        try:
            value, extra = spec.fn(**inputs)
        except RykoError:
            raise
        except TypeError as exc:
            declared = ", ".join(name for name, _ in spec.inputs)
            raise RykoInputError(
                f"مدخلات غير مطابقة لـ{mod}.{operation} — المعلن: {declared}. ({exc})",
                f"Inputs do not match {mod}.{operation} — declared: {declared}. ({exc})",
            ) from exc
        return RykoReceipt(
            module=mod,
            op=operation,
            inputs=dict(inputs),
            value=value,
            unit=spec.unit,
            formula=spec.formula,
            source=spec.source,
            assumptions=spec.assumptions,
            extra=dict(extra),
        )

    def catalog(self) -> dict:
        """الكتالوج المعلن — الواجهة العلمية: عملية، وحدة، معادلة، مصدر، مدخلات."""
        out: dict[str, dict] = {}
        for mod in sorted(OPS):
            out[mod] = {"title": MODULE_TITLES.get(mod, mod), "ops": {}}
            for op, spec in sorted(OPS[mod].items()):
                out[mod]["ops"][op] = {
                    "unit": spec.unit,
                    "formula": spec.formula,
                    "source": spec.source,
                    "inputs": {name: desc for name, desc in spec.inputs},
                    "assumptions": list(spec.assumptions),
                }
        return out

    def stats(self) -> dict:
        """أرقام صادقة عن العقل نفسه — عدد الوحدات والعمليات والإصدار."""
        return {
            "version": RYKO_VERSION,
            "modules": len(OPS),
            "operations": sum(len(ops) for ops in OPS.values()),
        }
