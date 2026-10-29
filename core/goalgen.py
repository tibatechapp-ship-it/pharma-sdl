"""التوليد الموجّه بالهدف — المكافئ المحلي الكامل لـ ChatChemTS/ChemTSv2 بلا مفتاح.

خطوة التحقق (2026-10-29 — من مستودع molecule-generator-collection والدوريات):
- ChatChemTS (Ishida et al., JCIM 2025): مفتوح المصدر لكنه يشترط مفتاح OpenAI
  مدفوعاً في .env لبناء دوال المكافأة وإعداد التشغيل → مخالف لمبدأ «صفر اشتراكات».
- ChemTSv2 (المحرك تحته): مجاني محلياً لكنه يجرّ TensorFlow + أوزان RNN مدرَّبة
  (~ مئات MB اعتماديات جديدة) — ثقل غير مبرر لمنصة تعليمية.

→ قرار «اعمل نفسه» (نفس القاعدة التي حكمت S7): حلقة توليد موجّهة محلية بالكامل:
  توسيع BRICS تكراري حول أفضل الناجين (بديل مبرَّر لشجرة MCTS في ChemTS) +
  قيود هدف صريحة يحددها المستخدم + دالة مكافأة شفافة (تشابه بالبذرة + QED).
  كل مرشح يُعرض بوصفاته الكاملة ومخالفاته — لا صندوق أسود.

بلا مفتاح، بلا شبكة، بلا اعتماديات جديدة — RDKit فقط (نمط expander: HAS_RDKIT
حارس وجود، وفشل أي خطوة يعيد تقريراً بسببه لا استثناءً).
"""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass

HAS_RDKIT = importlib.util.find_spec("rdkit") is not None
if HAS_RDKIT:
    from rdkit import Chem, DataStructs
    from rdkit.Chem import (
        BRICS,
        QED,
        Crippen,
        Descriptors,
        Lipinski,
        rdFingerprintGenerator,
        rdMolDescriptors,
    )

ENGINE = "local-brics-directed"

REASON_INVALID = "invalid_seed"
REASON_NO_RDKIT = "no_rdkit"
REASON_NO_SURVIVORS = "no_survivors"

# مفاتيح المخالفات القابلة للبرمجة — تُترجم في الواجهة عبر i18n (لا نصوص هنا)
KNOWN_VIOLATIONS = frozenset(
    {"mw_low", "mw_high", "logp", "tpsa", "hbd", "hba", "sim", "qed"}
)

# هياكل مرجعية عامة المعرفة (نمط FALLBACK_REFERENCE: توثيق لا اختراع) — تُفكَّك
# BRICS لتوسيع فضاء إعادة التركيب فوق شظايا البذرة وحدها، فالبذور الصغيرة
# (كالأسبرين) تُنتج شظايا قليلة ومركّبات أصغر من أي هدف دوائي واقعي.
REFERENCE_STRUCTURES: tuple[tuple[str, str], ...] = (
    ("CC(=O)OC1=CC=CC=C1C(=O)O", "أسبرين"),
    ("CC(=O)Nc1ccc(O)cc1", "باراسيتامول"),
    ("CC(C)Cc1ccc(cc1)C(C)C(=O)O", "إيبوبروفين"),
    ("COc1ccc2cc(ccc2c1)C(C)C(=O)O", "نابروكسين"),
    ("OC(=O)Cc1ccccc1Nc1c(Cl)cccc1Cl", "ديكلوفيناك"),
)


@dataclass(frozen=True)
class GoalSpec:
    """قيود الهدف — كلها صريحة وقابلة للعرض، لا معايير خفية."""

    mw_min: float = 250.0
    mw_max: float = 500.0
    logp_max: float = 5.0
    tpsa_max: float = 140.0
    hbd_max: int = 5
    hba_max: int = 10
    sim_floor: float = 0.30
    qed_min: float = 0.30


@dataclass(frozen=True)
class GoalCandidate:
    smiles: str
    mw: float
    logp: float
    tpsa: float
    hbd: int
    hba: int
    qed: float
    sim: float
    reward: float
    violations: tuple[str, ...]


@dataclass(frozen=True)
class GoalReport:
    seed: str
    engine: str
    goal: GoalSpec
    rounds_run: int
    pool_size: int
    survivors: tuple[GoalCandidate, ...]
    reason: str | None = None


_GEN = None
_REF_FRAGS: list | None = None


def _gen():
    global _GEN
    if _GEN is None:
        _GEN = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    return _GEN


def _reference_fragments() -> list:
    global _REF_FRAGS
    if _REF_FRAGS is not None:
        return _REF_FRAGS
    frags: list = []
    for smi, _name in REFERENCE_STRUCTURES:
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            continue
        try:
            # sorted هنا أيضاً: نفس سبب _expand — حتمية كاملة عبر العمليات
            for f in sorted(BRICS.BRICSDecompose(mol, minFragmentSize=3)):
                fm = Chem.MolFromSmiles(f)
                if fm is not None:
                    frags.append(fm)
        except Exception:  # noqa: BLE001, S112 — مرجع فاسد يُتخطى بلا انهيار ولا ضجيج
            continue
    _REF_FRAGS = frags
    return frags


def _profile(mol) -> tuple[float, float, float, int, int, float]:
    qed = 0.0
    try:
        qed = QED.qed(mol)
    except Exception:  # noqa: BLE001, S110 — QED يفشل على بنى نادرة → صفر محايد
        pass
    return (
        Descriptors.MolWt(mol),
        Crippen.MolLogP(mol),
        rdMolDescriptors.CalcTPSA(mol),
        Lipinski.NumHDonors(mol),
        Lipinski.NumHAcceptors(mol),
        qed,
    )


def _violations(spec: GoalSpec, mw: float, logp: float, tpsa: float,
                hbd: int, hba: int, qed: float, sim: float) -> tuple[str, ...]:
    v: list[str] = []
    if mw < spec.mw_min:
        v.append("mw_low")
    if mw > spec.mw_max:
        v.append("mw_high")
    if logp > spec.logp_max:
        v.append("logp")
    if tpsa > spec.tpsa_max:
        v.append("tpsa")
    if hbd > spec.hbd_max:
        v.append("hbd")
    if hba > spec.hba_max:
        v.append("hba")
    if sim < spec.sim_floor:
        v.append("sim")
    if qed < spec.qed_min:
        v.append("qed")
    return tuple(v)


def _evaluate(smiles: str, spec: GoalSpec, seed_fp) -> GoalCandidate | None:
    """تقييم مرشح واحد — None عند فشل التنقية (نمط expander: بلا استثناءات)."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None or mol.GetNumAtoms() == 0:
        return None
    if Chem.SanitizeMol(mol, catchErrors=True) != Chem.SanitizeFlags.SANITIZE_NONE:
        return None
    mw, logp, tpsa, hbd, hba, qed = _profile(mol)
    sim = DataStructs.TanimotoSimilarity(seed_fp, _gen().GetFingerprint(mol))
    viol = _violations(spec, mw, logp, tpsa, hbd, hba, qed, sim)
    reward = 0.5 * sim + 0.5 * qed  # دالة المكافأة الشفافة — تُوثَّق في الواجهة
    return GoalCandidate(
        smiles=Chem.MolToSmiles(mol), mw=mw, logp=logp, tpsa=tpsa,
        hbd=hbd, hba=hba, qed=qed, sim=sim, reward=reward, violations=viol,
    )


def _expand(anchor_smiles: str, n: int, extra_fragments: list) -> list[str]:
    """توسيع BRICS حول مرساة واحدة بفضاء شظايا مُثرى — بديل موضعي لـ expand_brics."""
    mol = Chem.MolFromSmiles(anchor_smiles)
    if mol is None:
        return []
    try:
        # sorted: BRICSDecompose يعيد مجموعة — الترتيب يعتمد على هاش السلاسل،
        # والفرز يضمن حتمية كاملة عبر العمليات (PYTHONHASHSEED متغاير)
        frag_smiles = sorted(BRICS.BRICSDecompose(mol, minFragmentSize=3))
    except Exception:  # noqa: BLE001 — BRICS يفشل على بعض البنى → فارغة بلا انهيار
        return []
    frag_mols = [Chem.MolFromSmiles(f) for f in frag_smiles]
    frag_mols = [f for f in frag_mols if f is not None]
    # نسخ عميقة لكل نداء: BRICSBuild قد يعدّل جزيئات الشظايا في مكانها،
    # والمرجعية مخزنة مؤقتاً على مستوى الوحدة — النسخ يقطع العدوى بين النداءات
    frag_mols.extend(Chem.Mol(f) for f in extra_fragments)
    if len(frag_mols) < 2:
        return []
    out: list[str] = []
    seen: set[str] = set()
    # scrambleReagents=False: الافتراضي يستدعي random.shuffle (عدم حتمية
    # موثّقة في مصدر BRICSBuild نفسه) — نريدها حتمية للعلم والاختبار
    built = BRICS.BRICSBuild(frag_mols, maxDepth=2, scrambleReagents=False)
    for m in built:
        if len(out) >= n:
            break
        if m is None or m.GetNumAtoms() == 0:
            continue
        if Chem.SanitizeMol(m, catchErrors=True) != Chem.SanitizeFlags.SANITIZE_NONE:
            continue
        smi = Chem.MolToSmiles(m)
        if smi in seen:
            continue
        seen.add(smi)
        out.append(smi)
    return out


def generate_toward_goal(
    seed_smiles: str,
    goal: GoalSpec | None = None,
    rounds: int = 3,
    pool_per_round: int = 40,
    top_keep: int = 5,
) -> GoalReport:
    """حلقة التوليد الموجّه: توسيع ← تقييم ← إعادة تثبيت حول أفضل ناجٍ.

    - rounds تُقاطَع مبكراً عند بلوغ top_keep ناجين (اقتصادياً كما في ChemTS).
    - المرساة التالية = أعلى المرشحين مكافأةً في الجولة، فينحاز الفضاء تدريجياً
      نحو ما يجتاز الهدف — وهذا جوهر «الموجّه» بديلَ شجرة MCTS.
    - الفشل يعود تقريراً بسببه (invalid_seed / no_rdkit / no_survivors).
    """
    spec = goal or GoalSpec()
    seed = (seed_smiles or "").strip()
    if not HAS_RDKIT:
        return GoalReport(seed, ENGINE, spec, 0, 0, (), REASON_NO_RDKIT)
    mol = Chem.MolFromSmiles(seed) if seed else None
    if mol is None:
        return GoalReport(seed, ENGINE, spec, 0, 0, (), REASON_INVALID)
    seed_canon = Chem.MolToSmiles(mol)
    seed_fp = _gen().GetFingerprint(mol)

    seen: set[str] = {seed_canon}
    pool_evaluated = 0
    rounds_run = 0
    candidates: list[GoalCandidate] = []
    survivors: list[GoalCandidate] = []
    anchor = seed_canon
    ref_frags = _reference_fragments()

    for r in range(max(1, rounds)):
        rounds_run = r + 1
        batch = _expand(anchor, pool_per_round, ref_frags)
        for smi in batch:
            if smi in seen:
                continue
            seen.add(smi)
            cand = _evaluate(smi, spec, seed_fp)
            if cand is None:
                continue
            pool_evaluated += 1
            candidates.append(cand)
        survivors = [c for c in candidates if not c.violations]
        survivors.sort(key=lambda c: c.reward, reverse=True)
        if len(survivors) >= top_keep:
            break
        round_best = max(candidates, key=lambda c: c.reward) if candidates else None
        if round_best is not None:
            anchor = round_best.smiles

    if survivors:
        return GoalReport(
            seed_canon, ENGINE, spec, rounds_run, pool_evaluated,
            tuple(survivors[:top_keep]), None,
        )
    return GoalReport(
        seed_canon, ENGINE, spec, rounds_run, pool_evaluated, (),
        REASON_NO_SURVIVORS,
    )
