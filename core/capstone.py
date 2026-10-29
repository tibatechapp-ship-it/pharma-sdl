"""capstone — من الهدف إلى القرار: خط اكتشاف شبه آلي كامل.

الخطوات (كلها دوال نقية تستقبل بيانات جاهزة — الشبكة اختيارية):
  1. المكتبة: بحث تشابه حي من PubChem أو مكتبة محلية من mpro_sample.csv
  2. فلترة ADME: Lipinski (MW, LogP, HBD, HBA) + Veber (TPSA, الروتاتمر)
  3. تنبؤ ML: نموذج pIC50 (Morgan → RandomForest) مع فترة ثقة
  4. PK/PD: C90 من معادلة Hill ثم Cmax الفموي (حجرة واحدة، Bateman)
     → الجرعة اللازمة للتحقق → قرار دوائي تعليمي
  5. التقرير: Markdown دائماً + PDF عربي (Tajawal) إن توفرت reportlab

⚠️ تعليمي فقط — لا يصلح لقرارات سريرية.
"""
from __future__ import annotations

import io
import math
import random
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = REPO_ROOT / "data" / "mpro_sample.csv"
FONTS_DIR = REPO_ROOT / "data" / "fonts"

# ═══ المعاملات الفسيولوجية التعليمية (مبنية على نيرماتريلڤير) ═══
PK_PARAMS = {
    "F": 0.45,          # التوافر الحيوي الفموي
    "Vd_L": 104.7,      # حجم التوزيع (L)
    "t_half_h": 6.05,   # عمر النصف (h)
    "ka_per_h": 1.04,   # ثابت الامتصاص (/h)
    "gamma": 1.0,       # ميل Hill
}
KE = math.log(2) / PK_PARAMS["t_half_h"]
KA = PK_PARAMS["ka_per_h"]
TMAX_H = math.log(KA / KE) / (KA - KE)

# عتبات ADME
LIPINSKI = {"mw": 500.0, "logp": 5.0, "hbd": 5, "hba": 10}
VEBER = {"tpsa": 140.0, "rotb": 10}

# قرار الجرعة (mg لكل 12 ساعة)
DOSE_BANDS = [
    (300.0, "ممكن دوائياً", "✅"),
    (750.0, "حدّي — يحتاج تحسين فعالية", "🟡"),
]


# ═══════════════════ المرحلة 1: المكتبة ═══════════════════

def offline_library(n: int = 150, seed: int = 42, path: Path = DEFAULT_DATA) -> pd.DataFrame:
    """مكتبة محلية بلا شبكة: عينة من مجموعة Mpro + خصائص ADME بحساب RDKit.

    ⚠️ للعرض فقط: الجزيئات من مجموعة تدريب النموذج نفسها — التنبؤات
    متفائلة بطبيعتها. استخدم `fetch_analog_library` لجزيئات جديدة صادقة.
    """
    from rdkit import Chem
    from rdkit.Chem import Crippen, Descriptors, rdMolDescriptors

    df = pd.read_csv(path).dropna(subset=["smiles"]).reset_index(drop=True)
    rng = random.Random(seed)
    idx = rng.sample(range(len(df)), min(n, len(df)))

    rows = []
    for i in idx:
        m = Chem.MolFromSmiles(df.loc[i, "smiles"])
        if m is None:
            continue
        rows.append(
            {
                "cid": 0,
                "smiles": df.loc[i, "smiles"],
                "mw": Descriptors.MolWt(m),
                "logp": Crippen.MolLogP(m),
                "hbd": rdMolDescriptors.CalcNumHBD(m),
                "hba": rdMolDescriptors.CalcNumHBA(m),
                "tpsa": rdMolDescriptors.CalcTPSA(m),
                "rotb": rdMolDescriptors.CalcNumRotatableBonds(m),
            }
        )
    return pd.DataFrame(rows)


def fetch_analog_library(seed_smiles: str, max_cids: int = 120, threshold: int = 60) -> pd.DataFrame:
    """بحث تشابه ثنائي الأبعاد حي من PubChem (يحتاج شبكة — اختبار integration).

    يرجع DataFrame كأعمدة ADME، أو DataFrame فارغ عند فشل الشبكة
    (المستدعي يتحول حينها إلى `offline_library`).
    """
    from urllib.parse import quote

    import requests

    base = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
    props = "CanonicalSMILES,MolecularWeight,XLogP,HBondDonorCount,HBondAcceptorCount,TPSA,RotatableBondCount"
    try:
        r = requests.get(
            f"{base}/compound/fastsimilarity_2d/smiles/{quote(seed_smiles)}/cids/JSON",
            params={"Threshold": threshold, "MaxCids": max_cids},
            timeout=30,
        )
        r.raise_for_status()
        cids = r.json()["IdentifierList"]["CID"]
        cids = [c for c in cids if c != 0][:max_cids]
        if not cids:
            return pd.DataFrame()
        rows = []
        for i in range(0, len(cids), 100):
            chunk = ",".join(map(str, cids[i : i + 100]))
            pr = requests.get(f"{base}/compound/cid/{chunk}/property/{props}/JSON", timeout=30)
            pr.raise_for_status()
            rows.extend(pr.json()["PropertyTable"]["Properties"])
    except (requests.RequestException, KeyError):
        return pd.DataFrame()

    out = []
    for p in rows:
        smi = p.get("CanonicalSMILES") or p.get("SMILES")
        if not smi:
            continue
        out.append(
            {
                "cid": p.get("CID", 0),
                "smiles": smi,
                "mw": p.get("MolecularWeight"),
                "logp": p.get("XLogP"),
                "hbd": p.get("HBondDonorCount"),
                "hba": p.get("HBondAcceptorCount"),
                "tpsa": p.get("TPSA"),
                "rotb": p.get("RotatableBondCount"),
            }
        )
    return pd.DataFrame(out)


# ═══════════════════ المرحلة 2: فلترة ADME ═══════════════════

def adme_filter(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """فلترة Lipinski + Veber → (المتبقية، قمع العدّ لكل مرحلة)."""
    num = df.apply(pd.to_numeric, errors="coerce")
    mask = (
        (num["mw"] <= LIPINSKI["mw"])
        & (num["logp"] <= LIPINSKI["logp"])
        & (num["hbd"] <= LIPINSKI["hbd"])
        & (num["hba"] <= LIPINSKI["hba"])
        & (num["tpsa"] <= VEBER["tpsa"])
        & (num["rotb"] <= VEBER["rotb"])
    )
    funnel = {
        "المكتبة الأولية": len(df),
        "MW ≤ 500": int((num["mw"] <= LIPINSKI["mw"]).sum()),
        "LogP ≤ 5": int(((num["mw"] <= 500) & (num["logp"] <= 5)).sum()),
        "+ HBD/HBA": int(
            (
                (num["mw"] <= 500)
                & (num["logp"] <= 5)
                & (num["hbd"] <= 5)
                & (num["hba"] <= 10)
            ).sum()
        ),
        "+ Veber (TPSA/روتاتمر)": int(mask.sum()),
    }
    return df[mask].reset_index(drop=True), funnel


# ═══════════════════ المرحلة 3: تنبؤ ML ═══════════════════

def score_potency(df: pd.DataFrame, model) -> pd.DataFrame:
    """إضافة أعمدة التنبؤ (pIC50 + CI + IC50 + حكم) — غير الصالحة NaN."""
    preds = model.predict_many(df["smiles"].tolist())
    rows = []
    for p in preds:
        if p is None:
            rows.append((np.nan, np.nan, np.nan, np.nan, None, None))
        else:
            rows.append(
                (p["pic50"], p["ci95"][0], p["ci95"][1], p["ic50_nm"], p["verdict"], p["icon"])
            )
    out = df.copy()
    out[["pic50", "ci_lo", "ci_hi", "ic50_nm", "verdict", "icon"]] = pd.DataFrame(
        rows, index=out.index
    )
    return out.sort_values("pic50", ascending=False, na_position="last").reset_index(drop=True)


# ═══════════════════ المرحلة 4: PK/PD ═══════════════════

def cmax_mg(dose_mg: float, mw: float) -> float:
    """Cmax الفموي (nM) لجرعة mg عبر حجرة واحدة مع امتصاص من الدرجة الأولى."""
    moles = dose_mg * 1e-3 / mw
    return float(
        (PK_PARAMS["F"] * moles * KA)
        / (PK_PARAMS["Vd_L"] * (KA - KE))
        * (math.exp(-KE * TMAX_H) - math.exp(-KA * TMAX_H))
        * 1e9
    )


def c90_nm(pic50: float, gamma: float = PK_PARAMS["gamma"]) -> float:
    """التركيز اللازم لاحتلال 90% من الهدف: C = IC50·θ/(1−θ)^... (Hill)."""
    ic50_nm = 10 ** (-pic50) * 1e9
    occ = 0.90
    return float(ic50_nm * (occ / (1 - occ)) ** (1.0 / gamma))


def pkpd_outlook(df: pd.DataFrame, dose_mg: float = 300.0) -> pd.DataFrame:
    """للأعلى 10: C90، Cmax عند الجرعة، الجرعة اللازمة، القرار."""
    out = df.head(10).copy()
    cmaxes, needs, verdicts, icons = [], [], [], []
    for row in out.itertuples():
        if np.isnan(row.pic50):
            cmaxes.append(np.nan)
            needs.append(np.nan)
            verdicts.append("—")
            icons.append("⚪")
            continue
        mw = float(row.mw) if row.mw and not np.isnan(float(row.mw)) else 400.0
        cmax = cmax_mg(dose_mg, mw)
        target = c90_nm(row.pic50)
        need = target / cmax * dose_mg if cmax > 0 else np.inf
        label, icon = "بعيد — فعالية غير كافية", "🔴"
        for threshold, band_label, band_icon in DOSE_BANDS:
            if need <= threshold:
                label, icon = band_label, band_icon
                break
        cmaxes.append(round(cmax, 1))
        needs.append(round(need, 1) if np.isfinite(need) else None)
        verdicts.append(label)
        icons.append(icon)
    out[["cmax_nm", "dose_needed_mg", "pkpd_verdict", "pkpd_icon"]] = pd.DataFrame(
        {"cmax": cmaxes, "need": needs, "v": verdicts, "i": icons}, index=out.index
    )
    return out


# ═══════════════════ المرحلة 5: التقرير ═══════════════════

@dataclass
class PipelineResult:
    """كل مخرجات خط الاكتشاف لعرضها أو توليد التقرير."""

    funnel: dict[str, int]
    ranked: pd.DataFrame
    dose_mg: float
    source: str
    top: pd.DataFrame = field(init=False)

    def __post_init__(self) -> None:
        self.top = pkpd_outlook(self.ranked, self.dose_mg)


def build_markdown_report(res: PipelineResult, target_name: str = "SARS-CoV-2 Mpro") -> str:
    """تقرير Markdown — يعمل دائماً بلا تبعيات إضافية."""
    lines = [
        f"# تقرير خط الاكتشاف — {target_name}",
        "",
        f"> مصدر المكتبة: **{res.source}** · الجرعة المرجعية: **{res.dose_mg:.0f} mg / 12h**",
        "",
        "## قمع الفلترة",
        "",
        "| المرحلة | المتبقي |",
        "|---|---|",
    ]
    lines += [f"| {k} | {v} |" for k, v in res.funnel.items()]
    lines += [
        "",
        f"## أعلى {len(res.top)} مرشح (تنبؤ ML + قرار PK/PD)",
        "",
        "| # | SMILES | pIC50 | IC50 | C90 | الجرعة اللازمة | القرار |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(res.top.itertuples(), 1):
        if np.isnan(r.pic50):
            continue
        ic50 = f"{r.ic50_nm:,.0f} nM" if not np.isnan(r.ic50_nm) else "—"
        need = f"{r.dose_needed_mg} mg" if r.dose_needed_mg else "—"
        lines.append(
            f"| {i} | `{r.smiles[:44]}…` | {r.pic50:.2f} | {ic50} "
            f"| {r.cmax_nm and f'{r.cmax_nm:,.0f} nM' or '—'} | {need} | {r.pkpd_verdict} |"
        )
    lines += [
        "",
        "## المنهجية",
        "",
        "- **ADME**: Lipinski (MW/LogP/HBD/HBA) + Veber (TPSA/الروابط الدوارة)",
        "- **الفعالية**: RandomForest على بصمات Morgan (r=2, 2048b) — بيانات ChEMBL Mpro",
        (
            "- **PK/PD**: C90 من Hill (θ=90%)، Cmax من حجرة واحدة فموية "
            f"(F={PK_PARAMS['F']}, Vd={PK_PARAMS['Vd_L']}L, t½={PK_PARAMS['t_half_h']}h)"
        ),
        "",
        "> ⚠️ تقرير تعليمي — لا يصلح لقرارات سريرية.",
    ]
    return "\n".join(lines)


def shape_arabic(text: str) -> str:
    """تشكيل العربية للـ PDF (reshape + bidi) — يعيد النص كما هو عند غياب المكتبات."""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        return get_display(arabic_reshaper.reshape(text))
    except ImportError:
        return text


def build_pdf_report(res: PipelineResult, target_name: str = "SARS-CoV-2 Mpro") -> bytes | None:
    """تقرير PDF عربي بـ reportlab — None إذا لم تتوفر المكتبات."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError:
        return None

    reg = FONTS_DIR / "Tajawal-Regular.ttf"
    bold = FONTS_DIR / "Tajawal-Bold.ttf"
    if not reg.exists():
        return None
    pdfmetrics.registerFont(TTFont("Tajawal", str(reg)))
    if bold.exists():
        pdfmetrics.registerFont(TTFont("Tajawal-Bold", str(bold)))

    def S(name: str, size: int, font: str = "Tajawal", **kw) -> ParagraphStyle:
        base = dict(fontName=font, fontSize=size, leading=size * 1.6, alignment=2, **kw)
        return ParagraphStyle(name, **base)

    st_title = S("t", 18, "Tajawal-Bold" if bold.exists() else "Tajawal", spaceAfter=6)
    st_h = S("h", 13, "Tajawal-Bold" if bold.exists() else "Tajawal", spaceBefore=10)
    st_body = S("b", 10)
    st_small = S("s", 8)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, topMargin=18 * mm, bottomMargin=15 * mm,
        leftMargin=15 * mm, rightMargin=15 * mm, title="Pharma SDL Capstone Report",
    )
    story = [
        Paragraph(shape_arabic(f"تقرير خط الاكتشاف — {target_name}"), st_title),
        Paragraph(
            shape_arabic(f"مصدر المكتبة: {res.source} · الجرعة المرجعية: {res.dose_mg:.0f} mg/12h"),
            st_body,
        ),
        Paragraph(shape_arabic("قمع الفلترة"), st_h),
    ]
    funnel_rows = [[shape_arabic("المرحلة"), shape_arabic("المتبقي")]] + [
        [shape_arabic(k), str(v)] for k, v in res.funnel.items()
    ]
    tbl = Table(funnel_rows, colWidths=[110 * mm, 30 * mm])
    tbl.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Tajawal"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#667eea")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ]
        )
    )
    story.append(tbl)
    story.append(Paragraph(shape_arabic("أعلى المرشحين — تنبؤ ML وقرار PK/PD"), st_h))

    head = [shape_arabic(c) for c in ["#", "pIC50", "IC50 (nM)", "الجرعة اللازمة", "القرار"]]
    body = []
    for i, r in enumerate(res.top.itertuples(), 1):
        if np.isnan(r.pic50):
            continue
        need = f"{r.dose_needed_mg} mg" if r.dose_needed_mg else "—"
        body.append(
            [
                str(i),
                f"{r.pic50:.2f}",
                f"{r.ic50_nm:,.0f}" if not np.isnan(r.ic50_nm) else "—",
                need,
                shape_arabic(r.pkpd_verdict),
            ]
        )
    if body:
        tbl2 = Table([head] + body, colWidths=[12 * mm, 22 * mm, 30 * mm, 38 * mm, 68 * mm])
        tbl2.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Tajawal"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2dd4a7")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (2, -1), "CENTER"),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ]
            )
        )
        story.append(tbl2)

    story += [
        Spacer(1, 8),
        Paragraph(
            shape_arabic(
                "المنهجية: ADME = Lipinski + Veber · الفعالية = RandomForest/Morgan على ChEMBL Mpro · "
                f"PK/PD = C90 من Hill ثم Cmax فموي (F={PK_PARAMS['F']}, Vd={PK_PARAMS['Vd_L']}L, "
                f"t½={PK_PARAMS['t_half_h']}h)"
            ),
            st_small,
        ),
        Paragraph(shape_arabic("⚠️ تقرير تعليمي — لا يصلح لقرارات سريرية."), st_body),
    ]
    doc.build(story)
    return buf.getvalue()


# ═══════════════════ المنسّق ═══════════════════

def run_pipeline(
    library: pd.DataFrame,
    dose_mg: float = 300.0,
    source: str = "محلية",
    model=None,
) -> PipelineResult:
    """تنفيذ الخط كاملاً على مكتبة جاهزة (بلا شبكة) → PipelineResult.

    model: PotencyModel جاهز — يُدرَّب الافتراضي مرة واحدة إذا أُهمل.
    """
    filtered, funnel = adme_filter(library)
    if filtered.empty:
        raise ValueError("كل جزيئات المكتبة فشلت في فلترة ADME — لا يمكن المتابعة")
    ranked = score_potency(filtered, model or _default_model())
    return PipelineResult(funnel=funnel, ranked=ranked, dose_mg=dose_mg, source=source)


_model_cache: tuple[object] | None = None


def _default_model():
    """نموذج pIC50 الافتراضي — مفرد على مستوى العملية (بلا streamlit هنا)."""
    global _model_cache
    if _model_cache is None:
        from core.ml_potency import train_default_model

        _model_cache = (train_default_model(),)
    return _model_cache[0]
