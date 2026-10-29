"""توسيع مكتبة الجزيئات حول بذرة — محركان موثّقان بلا بناء على رمل.

- حي (مفتاحيّ الشبكة، بلا مفتاح): تشابه PubChem ثنائي الأبعاد
  fastsimilarity_2d — نفس مسار fetch_analog_library المُختبَر.
- محلي (بلا شبكة): تفكيك BRICS وإعادة تركيب عبر RDKit — توليد تناظري
  كيميائي حقيقي، لا أرقام عشوائية.

الترتيب في expand_library("auto"): حي أولاً ثم محلي — والمصدر يُعاد
بصراحة ليُعرض في الواجهة (قاعدة «الفشل لا يرمي استثناءً»).
"""
from __future__ import annotations

import importlib.util

import requests

HAS_RDKIT = importlib.util.find_spec("rdkit") is not None
if HAS_RDKIT:
    from rdkit import Chem
    from rdkit.Chem import BRICS

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PUBCHEM_TIMEOUT = 30.0

SRC_PUBCHEM = "pubchem"
SRC_BRICS = "brics"
SRC_NONE = "none"


# ─────────────────────────────────────────────────────────────
# المحرك المحلي — BRICS
# ─────────────────────────────────────────────────────────────

def expand_brics(seed_smiles: str, n: int = 12, max_depth: int = 3) -> list[str]:
    """توسيع offline عبر تفكيك BRICS وإعادة التركيب — يتطلب RDKit.

    قائمة فارغة عند: غياب RDKit، أو بذرة غير صالحة، أو لا تركيبات جديدة.
    البروتوكول الأصلي: Degen et al., ChemMedChem 2008 (BRICS).
    """
    if not HAS_RDKIT:
        return []
    mol = Chem.MolFromSmiles(seed_smiles.strip()) if seed_smiles.strip() else None
    if mol is None:
        return []
    try:
        frag_smiles = BRICS.BRICSDecompose(mol, minFragmentSize=3)
        frag_mols = [Chem.MolFromSmiles(f) for f in frag_smiles]
        frag_mols = [f for f in frag_mols if f is not None]
        if len(frag_mols) < 2:
            return []
        seed_canon = Chem.MolToSmiles(mol)
    except Exception:  # noqa: BLE001 — BRICS فشل على البذرة → فارغة بلا انهيار
        return []
    out: list[str] = []
    seen = {seed_canon}
    # scrambleReagents=False: الافتراضي يستدعي random.shuffle — نريدها حتمية
    built = BRICS.BRICSBuild(frag_mols, maxDepth=max_depth, scrambleReagents=False)
    for m in built:
        if len(out) >= n:
            break
        if m is None or m.GetNumAtoms() == 0:
            continue
        # تنقية يدوية بلا استثناءات: catchErrors يُرجع رمز الفشل بدل الرمي
        if Chem.SanitizeMol(m, catchErrors=True) != Chem.SanitizeFlags.SANITIZE_NONE:
            continue
        smi = Chem.MolToSmiles(m)
        if smi in seen:
            continue
        seen.add(smi)
        out.append(smi)
    return out


# ─────────────────────────────────────────────────────────────
# المحرك الحي — تشابه PubChem
# ─────────────────────────────────────────────────────────────

def expand_pubchem(seed_smiles: str, n: int = 12, threshold: int = 70) -> list[str]:
    """جيران تشابه حقيقيون من PubChem — [] عند أي فشل شبكة/شكل.

    يُعيد استخدام fetch_analog_library المُختبَرة (نفس النقطة والنمط)
    ويقتنع بأعمدة SMILES منها — بلا تكرار للنداءات.
    """
    from urllib.parse import quote

    try:
        resp = requests.get(
            f"{PUBCHEM_BASE}/compound/fastsimilarity_2d/smiles/{quote(seed_smiles)}"
            f"/cids/JSON",
            params={"Threshold": threshold, "MaxCids": max(n * 3, n)},
            timeout=PUBCHEM_TIMEOUT,
        )
        resp.raise_for_status()
        cids = [c for c in resp.json()["IdentifierList"]["CID"] if c != 0][:n]
        if not cids:
            return []
        props = "CanonicalSMILES,SMILES"
        pr = requests.get(
            f"{PUBCHEM_BASE}/compound/cid/{','.join(map(str, cids))}"
            f"/property/{props}/JSON",
            timeout=PUBCHEM_TIMEOUT,
        )
        pr.raise_for_status()
        rows = pr.json()["PropertyTable"]["Properties"]
    except (requests.RequestException, KeyError, ValueError):
        return []
    out: list[str] = []
    seed = seed_smiles.strip()
    for p in rows:
        smi = p.get("CanonicalSMILES") or p.get("SMILES")
        if not smi or smi == seed:  # البذرة نفسها أول نتيجة — تُستثنى
            continue
        if smi not in out:
            out.append(smi)
    return out[:n]


# ─────────────────────────────────────────────────────────────
# الموزّع — auto: حي ثم محلي، والمصدر يُعاد بصراحة
# ─────────────────────────────────────────────────────────────

def expand_library(
    seed_smiles: str, n: int = 12, mode: str = "auto", threshold: int = 70
) -> tuple[list[str], str]:
    """توسيع المكتبة — يُرجع (قائمة SMILES, المصدر: pubchem|brics|none).

    mode: "auto" (حي ثم محلي) | "pubchem" (حي فقط) | "brics" (محلي فقط).
    """
    if not seed_smiles or not seed_smiles.strip():
        return [], SRC_NONE
    if mode == "pubchem":
        return expand_pubchem(seed_smiles, n=n, threshold=threshold), SRC_PUBCHEM
    if mode == "brics":
        return expand_brics(seed_smiles, n=n), SRC_BRICS
    live = expand_pubchem(seed_smiles, n=n, threshold=threshold)
    if live:
        return live, SRC_PUBCHEM
    return expand_brics(seed_smiles, n=n), SRC_BRICS
