"""عميل Boltz-2 — طبقة co-folding المرجعية في المقارنة ثلاثية الطبقات (P14).

المرجع (خطوة التحقق 2026-11-04، كما تقتضي docs/INTEGRATION-ROADMAP.md:
«لا تبنِ إنتاجاً قبل خطوة تحقق واحدة»):

- Boltz-2 (MIT CSAIL / Jameel Clinic) — الكود والنماذج رخصة MIT كاملة
  (jwohlwend/boltz). الاستشهاد: Passaro et al., «Boltz-2: Towards Accurate
  and Efficient Binding Affinity Prediction», bioRxiv 2025.06.14.659707.
- عقد المخرجات الموثَّق من README المستودع الرسمي حرفياً:
    affinity_pred_value         : قيمة التقارب بصيغة log10(IC50) مع IC50
                                  مقاس بوحدة الميكرومولار (μM).
    affinity_probability_binary : احتمال [0..1] أن الجزيء مرتبط أصلاً
                                  (فرز مرشحين، مرحلة اكتشاف).
  التحويل الوحيد المسموح هنا: IC50[μM] = 10^(value) ثم
  pIC50 = 6 − value (لأن pIC50 = −log10(IC50[M]) = 6 − log10(IC50[μM])).
- حجم التشغيل الفعلي: ~20 ثانية GPU لكل معقد (T4/A100)، والاستدلال
  العملي يتطلب GPU + ذاكرة أكبر من 16GB — لذلك **لا يعمل داخل هذه
  البيئة المحلية**؛ التشغيل الفعلي عبر دفتر Lab08 على Colab:
  labs/lab08_boltz2_co_folding.ipynb — ويُجمَّد مخرجه في ملف بيان
  (manifest) بمخطط ثابت يستهلكه هذا العميل.

المبدأ الحاكم (نمط ersilia_client / admet_ai_client): البيان غائب أو
غير صالح لا يرمي استثناءً للواجهة — حالة «unavailable» صادقة مع سبب
موثق، ولا تُختلق قيمة واحدة أبداً. كل رقم يحمل نسبه الكامل (نموذج/
عتاد/بذرة/تاريخ) كما ورد في البيان، والعميل لا يضيف عليه شيئاً.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ── عقد مخطط البيان — ثابت ومعلن، دفتر Lab08 يكتبه حرفياً ──
MANIFEST_SCHEMA = "pharma-sdl.boltz2-affinity.v1"

REQUIRED_PRED_FIELDS = ("smiles", "affinity_pred_value")

STATUS_AVAILABLE = "available"
STATUS_MISSING = "unavailable_missing_manifest"
STATUS_INVALID = "unavailable_invalid_schema"

# RT·ln10 عند 298K — نفس ثابت جسر Cheng-Prusoff في core/docking.py
P_IC50_OFFSET_UM = 6.0


def affinity_to_pic50(affinity_pred_value: float) -> float:
    """log10(IC50[μM]) → pIC50 = 6 − value (عقد الوحدات الرسمي لـ Boltz-2)."""
    return P_IC50_OFFSET_UM - float(affinity_pred_value)


def affinity_to_ic50_um(affinity_pred_value: float) -> float:
    """log10(IC50[μM]) → IC50 بوحدة μM (قيمة مباشرة 10^value)."""
    return float(10.0 ** float(affinity_pred_value))


@dataclass(frozen=True)
class Boltz2AffinityRecord:
    """قراءة تقارب واحدة من بيان Boltz-2 — كما وردت، بلا إضافة."""

    smiles: str
    affinity_pred_value: float  # log10(IC50[μM]) — دلالة رسمية
    affinity_probability_binary: float | None = None
    confidence: dict[str, float] = field(default_factory=dict)  # ipTM/pTM/pLDDT إن وُجدت
    seed: int | None = None
    source: str = ""  # أمر التشغيل أو أي إثبات نسبة سجّله الدفتر

    @property
    def pic50(self) -> float:
        return round(affinity_to_pic50(self.affinity_pred_value), 2)

    @property
    def ic50_um(self) -> float:
        return affinity_to_ic50_um(self.affinity_pred_value)

    @property
    def ic50_nm(self) -> float:
        return self.ic50_um * 1000.0


@dataclass(frozen=True)
class Boltz2ManifestMeta:
    """ميتاداتا النسبة — تُنقل من البيان حرفياً وتُجمَّد مع كل رقم."""

    schema: str
    generated_at: str
    model_name: str
    model_version: str
    hardware: str
    receptor_name: str
    receptor_pdb: str
    sequence_sha256: str


class Boltz2Client:
    """مستهلك بيان Boltz-2 المجمد — الطبقة الثالثة في المقارنة ثلاثية الطبقات.

    بيان غائب/فاسد → حالة صادقة بلا قيم مختلقة (المبدأ الحاكم للمشروع).
    """

    def __init__(
        self,
        meta: Boltz2ManifestMeta,
        records: dict[str, Boltz2AffinityRecord],
        manifest_path: Path,
    ) -> None:
        self._meta = meta
        self._records = records  # مفاتيحها SMILES قانونية بترتيب RDKit
        self._manifest_path = manifest_path

    # ── البناء ──

    @classmethod
    def load(cls, manifest_path: Path | str) -> "Boltz2Client | None":
        """تحميل البيان؛ None عند الغياب أو الفساد (حالة صادقة لا استثناء)."""
        path = Path(manifest_path)
        if not path.exists():
            logger.info("بيان Boltz-2 غائب: %s — الطبقة الثالثة غير متاحة offline", path)
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("بيان Boltz-2 غير قابل للقراءة (%s): %s", path, exc)
            return None
        if raw.get("schema") != MANIFEST_SCHEMA:
            logger.warning("مخطط بيان غير معروف: %r", raw.get("schema"))
            return None
        preds = raw.get("predictions")
        if not isinstance(preds, list):
            logger.warning("بيان بلا قائمة predictions صالحة")
            return None
        records: dict[str, Boltz2AffinityRecord] = {}
        for entry in preds:
            rec = cls._parse_prediction(entry)
            if rec is not None:
                records[rec.smiles] = rec
        meta = Boltz2ManifestMeta(
            schema=str(raw["schema"]),
            generated_at=str(raw.get("generated_at", "")),
            model_name=str(raw.get("model", {}).get("name", "boltz-2")),
            model_version=str(raw.get("model", {}).get("version", "")),
            hardware=str(raw.get("hardware", {}).get("device", "")),
            receptor_name=str(raw.get("receptor", {}).get("name", "")),
            receptor_pdb=str(raw.get("receptor", {}).get("pdb_reference", "")),
            sequence_sha256=str(raw.get("receptor", {}).get("sequence_sha256", "")),
        )
        return cls(meta, records, path)

    @staticmethod
    def _parse_prediction(entry: dict) -> Boltz2AffinityRecord | None:
        if not isinstance(entry, dict):
            return None
        for req in REQUIRED_PRED_FIELDS:
            if req not in entry or entry[req] is None:
                logger.warning("تنبؤ ناقص الحقل الإلزامي %r — استُبعد", req)
                return None
        try:
            value = float(entry["affinity_pred_value"])
        except (TypeError, ValueError):
            logger.warning("affinity_pred_value ليس عدداً — استُبعد")
            return None
        smiles_raw = str(entry["smiles"]).strip()
        smiles = _canonical_or_none(smiles_raw)
        if smiles is None:
            logger.warning("SMILES غير قابل للتحليل في البيان — استُبعد")
            return None
        prob = entry.get("affinity_probability_binary")
        conf = {
            k: float(entry[k])
            for k in ("iptm", "ptm", "complex_plddt", "ligand_iptm", "ligand_plddt")
            if isinstance(entry.get(k), (int, float))
        }
        return Boltz2AffinityRecord(
            smiles=smiles,
            affinity_pred_value=value,
            affinity_probability_binary=float(prob) if isinstance(prob, (int, float)) else None,
            confidence=conf,
            seed=int(entry["seed"]) if isinstance(entry.get("seed"), int) else None,
            source=str(entry.get("source", "")),
        )

    # ── الاستهلاك ──

    @property
    def status(self) -> str:
        """حالة الطبقة الثالثة — قيمة واحدة من ثوابت STATUS_*."""
        return STATUS_AVAILABLE if self._records else STATUS_INVALID

    @property
    def meta(self) -> Boltz2ManifestMeta:
        return self._meta

    def lookup(self, smiles: str) -> Boltz2AffinityRecord | None:
        """بحث بمطابقة SMILES قانونية — None = ليس في البيان (صادق لا صامت)."""
        canon = _canonical_or_none(smiles)
        if canon is None:
            return None
        return self._records.get(canon)

    def reading_for(self, smiles: str) -> dict | None:
        """قراءة موحّدة الصيغة لمحرك المقارنة ثلاثية الطبقات."""
        rec = self.lookup(smiles)
        if rec is None:
            return None
        return {
            "tier": 3,
            "engine": "boltz-2",
            "status": STATUS_AVAILABLE,
            "affinity_pred_value": rec.affinity_pred_value,
            "unit": "log10(IC50[μM])",
            "pic50": rec.pic50,
            "ic50_nm": round(rec.ic50_nm, 3),
            "affinity_probability_binary": rec.affinity_probability_binary,
            "confidence": rec.confidence,
            "provenance": {
                "model": f"{self._meta.model_name} {self._meta.model_version}".strip(),
                "hardware": self._meta.hardware,
                "generated_at": self._meta.generated_at,
                "receptor": f"{self._meta.receptor_name} ({self._meta.receptor_pdb})",
                "manifest_sha256": _file_sha256(self._manifest_path),
                "seed": rec.seed,
                "source": rec.source,
            },
        }


def _canonical_or_none(smiles: str) -> str | None:
    """تقنين SMILES عبر RDKit؛ None عند فشل التحليل."""
    try:
        from rdkit import Chem

        mol = Chem.MolFromSmiles(smiles)
        return Chem.MolToSmiles(mol) if mol is not None else None
    except Exception:  # pragma: no cover - rdkit غائب فقط في بيئات شاذة
        return None


def _file_sha256(path: Path) -> str:
    """بصمة البيان — تربط كل رقم بنسخته المجمّدة بالضبط."""
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()
