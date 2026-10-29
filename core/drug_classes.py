"""التصنيف الدوائي — دليل المجموعات بالمعيار العالمي ATC (منظمة الصحة العالمية).

سؤال المستخدم (2026-10-30): «نذكر الأدوية بدون المجموعات — مجموعة البنسلين
والكينولون والتركيبات الكيميائية — ما الصح وما المتبع عالمياً؟»

الجواب الموثّق: المعيار العالمي المتّبع هو **نظام ATC** (Anatomical Therapeutic
Chemical) الصادر عن مركز WHO التعاوني في أوسلو:
  الحرف الأول: الجهاز (J = مضادات عامة) · رقمان: المجموعة العلاجية (J01)
  · حرف: المجموعة الدوائية (J01C) · حرف: المجموعة الكيميائية (J01CA)
  · رقم: المادة (J01CA04 = أموكسيسيلين).
وعلمياً: الدواء يُدرس عبر **مجموعته** (آلية العمل، الآثار المشتركة، التحسس
المتقاطع) لا كجزيرة معزولة — وهذا ما بنيناه هنا.

بنية الوحدة:
- CATALOG: بطاقات مجموعات ثنائية اللغة برموز ATC وآلية العمل وأعضائها الموثّقين.
- classify(name_or_smiles): تصنيف محلي فوري — مطابقة أعضاء أولاً (الأدق)
  ثم قواعد لواحق آمنة غير ملتبسة بالترتيب (thromycin قبل mycin، prazole قبل conazole).
- atc_live(name): نداء RxNorm RxClass حي (مجاني بلا مفتاح) — نمط العملاء الرقيق:
  فشل الشبكة → None بلا استثناءات. ⚠️ توثيق التحقق (2026-10-30): العقد مأخوذ من
  وثائق NIH الرسمية (rxnav.nlm.nih.gov/REST)؛ النداء الحي من بيئة التطوير
  محجوب (مهلة اتصال) فاختُبر بالـmock ووُسم integration — التحقق الحي عند
  توفر شبكة مفتوحة.
بلا اعتماديات جديدة: requests فقط للعميل الحي، والباقي معرفة محلية.
"""
from __future__ import annotations

from dataclasses import dataclass

import requests

RXNAV_BASE = "https://rxnav.nlm.nih.gov/REST"
RXNAV_TIMEOUT = 20.0


@dataclass(frozen=True)
class ClassCard:
    class_id: str                      # معرّف برمجي مستقر
    atc: str                           # رمز ATC للمجموعة (مثال: J01C)
    name_ar: str
    name_en: str
    mech_ar: str                       # آلية العمل — سطر واحد صادق
    mech_en: str
    members: tuple[tuple[str, str], ...]  # (اسم إنجليزي, اسم عربي) — موثّقون
    smiles: tuple[str, ...] = ()       # بنى الأعضاء المتوفرة (تطابق بالبنية)
    suffixes: tuple[str, ...] = ()     # لواحق آمنة غير ملتبسة (thromycin قبل mycin)
    prefixes: tuple[str, ...] = ()     # بادئات آمنة (cef/ceph للسيفالوسبورينات)


@dataclass(frozen=True)
class ClassHit:
    card: ClassCard
    basis: str                         # "member" | "smiles" | "suffix" | "prefix"
    matched: str                       # ماذا طابق (اسم عضو/لاحقة/بنية)


# ── الكاتالوج — مجموعات عالمية موثّقة برموز ATC ─────────────────────────

CATALOG: tuple[ClassCard, ...] = (
    ClassCard(
        class_id="penicillins", atc="J01C",
        name_ar="البنسلينات (بيتا لاكتام)", name_en="Penicillins (beta-lactam)",
        mech_ar="تثبيط إنزيمات PBP فتُضعف تصنيع جدار الخلية البكتيرية — قتل، وتحسس متقاطع مع السيفالوسبورينات.",
        mech_en="Inhibit PBPs weakening cell-wall synthesis — bactericidal; cross-sensitivity with cephalosporins.",
        members=(("amoxicillin", "أموكسيسيلين"), ("ampicillin", "أمبيسيلين"),
                 ("penicillin g", "بنسلين ج"), ("amoxiclav", "أموكسيكلاف")),
        suffixes=("cillin",),
    ),
    ClassCard(
        class_id="cephalosporins", atc="J01D",
        name_ar="السيفالوسبورينات (بيتا لاكتام)", name_en="Cephalosporins (beta-lactam)",
        mech_ar="نفس عائلة بيتا لاكتام لكن مقاومة أكثر لبعض البتالاكتامازات — أربعة أجيال تتسع تغطيتها قرمية.",
        mech_en="Beta-lactam family more resistant to some beta-lactamases — four generations with widening gram-negative coverage.",
        members=(("ceftriaxone", "سيفترياكسون"), ("cefalexin", "سيفالكسين"),
                 ("cefixime", "سيفيكسيم"), ("cefepime", "سيفيبيم")),
        prefixes=("cef", "ceph"),
    ),
    ClassCard(
        class_id="carbapenems", atc="J01DH",
        name_ar="الكاربابينيمات (بيتا لاكتام)", name_en="Carbapenems (beta-lactam)",
        mech_ar="أوسع بيتا لاكتامات تغطيةً — خط أخير للمقاومة، ويُمنع استهلاكه عشوائياً حفاظاً على فعاليته.",
        mech_en="Broadest beta-lactam coverage — last-line for resistance; stewardship protects its utility.",
        members=(("meropenem", "ميروبينيم"), ("imipenem", "إيميبينيم"),
                 ("ertapenem", "إرتابينيم")),
        suffixes=("penem",),
    ),
    ClassCard(
        class_id="fluoroquinolones", atc="J01M",
        name_ar="الفلوروكينولونات", name_en="Fluoroquinolones",
        mech_ar="تثبيط DNA جيراز وTopo IV فتمنع نسخ الجرثومة — تحذيرات حديثة: أوتار والشرفات و QT.",
        mech_en="Inhibit DNA gyrase / topoisomerase IV — modern warnings: tendons, CNS, QT.",
        members=(("ciprofloxacin", "سيبروفلوكساسين"), ("levofloxacin", "ليفوفلوكساسين"),
                 ("moxifloxacin", "موكسيفلوكساسين"), ("ofloxacin", "أوفلوكساسين")),
        suffixes=("floxacin",),
    ),
    ClassCard(
        class_id="macrolides", atc="J01FA",
        name_ar="الماكروليدات", name_en="Macrolides",
        mech_ar="تثبيط تخليق البروتين عبر وحدة 50S — تُطيل QT، وتفاعلات CYP3A4 شائعة.",
        mech_en="Inhibit protein synthesis via 50S — QT prolongation and CYP3A4 interactions are common.",
        members=(("azithromycin", "أزيثروميسين"), ("clarithromycin", "كلاريثروميسين"),
                 ("erythromycin", "إريثروميسين")),
        suffixes=("thromycin",),
    ),
    ClassCard(
        class_id="aminoglycosides", atc="J01G",
        name_ar="الأمينوغليكوزيدات", name_en="Aminoglycosides",
        mech_ar="تثبيط 30S — تركيز-معتمدة (PAE)، سمية كلوية وأذنية — لذا جرعة واحدة يومياً كما في مختبر MIC لدينا.",
        mech_en="Inhibit 30S — concentration-dependent with PAE; nephro/ototoxicity hence once-daily dosing (see our MIC lab).",
        members=(("gentamicin", "الجنتامايسين"), ("amikacin", "أميكاسين"),
                 ("tobramycin", "توبرامايسين")),
    ),
    ClassCard(
        class_id="lincosamides", atc="J01FF",
        name_ar="اللينكوساميدات", name_en="Lincosamides",
        mech_ar="تثبيط 50S قريب من الماكروليدات — انتبه للتهاب القولون بالمطثية العسيرة.",
        mech_en="50S inhibition similar to macrolides — watch C. difficile colitis.",
        members=(("clindamycin", "كليندامايسين"), ("lincomycin", "لينكومايسين")),
    ),
    ClassCard(
        class_id="glycopeptides", atc="J01XA",
        name_ar="الغليكوببتيدات", name_en="Glycopeptides",
        mech_ar="ترابط بديبتيدات الجدار في الجراثيم قرمية المقاومة — سلاح MRSA، ويراقب فجوة الهدف (AUC/MIC).",
        mech_en="Bind wall precursors in gram-positives — MRSA weapon with AUC/MIC target monitoring.",
        members=(("vancomycin", "فانكومايسين"), ("teicoplanin", "تيكوبلانين")),
    ),
    ClassCard(
        class_id="tetracyclines", atc="J01AA",
        name_ar="التتراسيكلينات", name_en="Tetracyclines",
        mech_ar="تثبيط 30S — تترابط مع الكالسيوم (أسنان/عظام) فتُمنع للأطفال والحمل.",
        mech_en="Inhibit 30S — chelate calcium (teeth/bone) hence avoided in children and pregnancy.",
        members=(("doxycycline", "دوكسيسايكلين"), ("tetracycline", "تتراسيكلين"),
                 ("minocycline", "مينوسايكلين")),
        suffixes=("cycline",),
    ),
    ClassCard(
        class_id="sulfonamides", atc="J01E",
        name_ar="السلفوناميدات + الترايميثوبريم", name_en="Sulfonamides & trimethoprim",
        mech_ar="حجب توليف الفولات (DHPS/DHFR) — التركيبة SMX-TMP متتالية-قتلة.",
        mech_en="Block folate synthesis (DHPS/DHFR) — SMX-TMP combination is sequentially bactericidal.",
        members=(("sulfamethoxazole", "سلفاميثوكسازول"), ("trimethoprim", "ترايميثوبريم"),
                 ("sulfadiazine", "سلفادايازين")),
        prefixes=("sulfa",),
    ),
    ClassCard(
        class_id="azoles", atc="J02A",
        name_ar="الأزولات المضادة للفطريات", name_en="Azole antifungals",
        mech_ar="تثبيط إنزيم CYP51 الفطري فتُقلب غشاء الإرغوستيرول — قلبها يعني تفاعلات CYP إنسانية عديدة.",
        mech_en="Inhibit fungal CYP51 depleting ergosterol — the same CYP affinity drives many human interactions.",
        members=(("fluconazole", "فلوكونازول"), ("itraconazole", "إيتراكونازول"),
                 ("voriconazole", "فوركونازول"), ("ketoconazole", "كيوتوكونازول")),
        suffixes=("conazole",),
    ),
    ClassCard(
        class_id="allylamines", atc="D01BA",
        name_ar="الأليلامينات المضادة للفطريات", name_en="Allylamine antifungals",
        mech_ar="تثبيط سكوالين إيبوكسيداز مبكراً في مسار الإرغوستيرول — فموي/موضعي للتهاب الأظافر.",
        mech_en="Inhibit squalene epoxidase early in ergosterol pathway — oral/topical for onychomycosis.",
        members=(("terbinafine", "تيرفينافين"), ("naftifine", "نافتيفين")),
    ),
    ClassCard(
        class_id="ppis", atc="A02BC",
        name_ar="مثبطات مضخة البروتون", name_en="Proton-pump inhibitors",
        mech_ar="حجب H+/K+ ATPase الحمضية نهائياً — أقوى من حاصرات H2، ودرسها: تفعيل أدوية معتمدة على الحمض.",
        mech_en="Irreversibly block gastric H+/K+ ATPase — stronger than H2 blockers; alters acid-activated drugs.",
        members=(("omeprazole", "أوميبرازول"), ("pantoprazole", "بانتوبرازول"),
                 ("esomeprazole", "إيزوميبرازول")),
        suffixes=("prazole",),
    ),
    ClassCard(
        class_id="statins", atc="C10AA",
        name_ar="الستاتينات", name_en="Statins",
        mech_ar="تثبيط HMG-CoA ريدكتاز — ملاحظة فارما: أتورفاستاتين مثال على أهمية المجموعة لا العضو (فيها برموز مختلفة C10AA05).",
        mech_en="Inhibit HMG-CoA reductase — a perfect example why the class matters more than the member.",
        members=(("atorvastatin", "أتورفاستاتين"), ("simvastatin", "سيمفاستاتين"),
                 ("rosuvastatin", "روسوفاستاتين")),
        suffixes=("statin",),
    ),
    ClassCard(
        class_id="acei", atc="C09A",
        name_ar="مثبطات الإنزيم المحول للأنجيوتنسين", name_en="ACE inhibitors",
        mech_ar="حجب تحويل AngI→AngII — الكحالة شائعة (مادة bradykinin) ولهذا يبدّل إلى ARBs.",
        mech_en="Block AngI→AngII conversion — cough via bradykinin is the classic reason to switch to ARBs.",
        members=(("lisinopril", "ليسينوبريل"), ("enalapril", "إنالابريل"),
                 ("ramipril", "راميبريل"), ("captopril", "كابتوبريل")),
        suffixes=("pril",),
    ),
    ClassCard(
        class_id="arbs", atc="C09C",
        name_ar="حاصرات مستقبلات الأنجيوتنسين", name_en="Angiotensin receptor blockers",
        mech_ar="حجب مستقبل AT1 مباشرة بلا كحالة — نفس السطر العلاجي لمثبطات ACE.",
        mech_en="Directly block AT1 receptor without cough — same therapeutic line as ACEi.",
        members=(("losartan", "لوسارتان"), ("valsartan", "فالسارتان"),
                 ("candesartan", "كانديسارتان")),
        suffixes=("sartan",),
    ),
    ClassCard(
        class_id="beta_blockers", atc="C07",
        name_ar="حاصرات بيتا", name_en="Beta-blockers",
        mech_ar="حجب مستقبلات بيتا — الانتقائية (قلبي β1 مقابل عام) هي الدرس: القلقصة القصبية لقوّة عامة.",
        mech_en="Block beta receptors — selectivity (β1 vs non-selective) is the lesson: asthma favors β1.",
        members=(("metoprolol", "ميتوبرولول"), ("propranolol", "بروبرانولول"),
                 ("atenolol", "أتينولول"), ("carvedilol", "كارفيديلول")),
        suffixes=("olol",),
    ),
    ClassCard(
        class_id="dhp_ccbs", atc="C08C",
        name_ar="حاصرات الكالسيوم ثنائية الهيدروبيريدين", name_en="Dihydropyridine CCBs",
        mech_ar="حجب قنوات L الجنبية للعضلات الملساء الوعائية — الوذمة الظنبوبية أثر جماعي للمجموعة.",
        mech_en="Block vascular smooth-muscle L-channels — ankle edema is a class effect.",
        members=(("amlodipine", "أملوديبين"), ("nifedipine", "نيفيديبين")),
        suffixes=("dipine",),
    ),
    ClassCard(
        class_id="biguanides", atc="A10BA",
        name_ar="البيغوانيدات", name_en="Biguanides",
        mech_ar="تنشيط AMPK وتقليل توليد الجلوكوز الكبدي — عضوها السريري الوحيد ميتفورمين، واحذر الحماض اللبني نادرًا.",
        mech_en="Activate AMPK and cut hepatic glucose output — metformin is the sole clinical member; rare lactic acidosis.",
        members=(("metformin", "ميتفورمين"),),
    ),
    ClassCard(
        class_id="sulfonylureas", atc="A10BB",
        name_ar="السلفونيل يوريا", name_en="Sulfonylureas",
        mech_ar="غلق قنوات KATP للبيتا خلايا فتفرز الإنسولين — الهبوط السكري أثر جماعي للمجموعة.",
        mech_en="Close pancreatic KATP channels → insulin release — hypoglycemia is a class effect.",
        members=(("gliclazide", "غليكلازيد"), ("glimepiride", "غليميبيريد"),
                 ("glibenclamide", "غليبنكلاميد"), ("glipizide", "غليبيزيد")),
    ),
    ClassCard(
        class_id="anilides", atc="N02BE",
        name_ar="الأنيليدات (باراسيتامول)", name_en="Anilides (paracetamol)",
        mech_ar="مضاد ألم/حرارة مركزي — ليس NSAID: شبه غياب المفعول الالتهابي المحيطي، والسمية كبدي (NAPQI).",
        mech_en="Central analgesic/antipyretic — not an NSAID: little peripheral inflammation, hepatotoxic via NAPQI.",
        members=(("paracetamol", "باراسيتامول"), ("acetaminophen", "أسيتامينوفين")),
        smiles=("CC(=O)Nc1ccc(O)cc1",),
    ),
    ClassCard(
        class_id="nsaids", atc="M01A",
        name_ar="مضادات الالتهاب غير الستيرويدية", name_en="NSAIDs",
        mech_ar="تثبيط COX-1/2 فتنقص البروستاغلاندين — الدرس الجماعي: قرحة/كلى/قلب عبر نفس الآلية.",
        mech_en="Inhibit COX-1/2 lowering prostaglandins — the class lesson: GI/renal/CV effects share one mechanism.",
        members=(("ibuprofen", "إيبوبروفين"), ("diclofenac", "ديكلوفيناك"),
                 ("naproxen", "نابروكسين"), ("ketoprofen", "كيوتوبروفين"),
                 ("aspirin", "أسبرين")),
        smiles=("CC(C)Cc1ccc(cc1)C(C)C(=O)O",           # إيبوبروفين
                "OC(=O)Cc1ccccc1Nc1c(Cl)cccc1Cl",        # ديكلوفيناك
                "COc1ccc2cc(ccc2c1)C(C)C(=O)O",          # نابروكسين
                "CC(=O)OC1=CC=CC=C1C(=O)O"),             # أسبرين
    ),
    ClassCard(
        class_id="benzodiazepines", atc="N05BA",
        name_ar="البنزوديازيبينات", name_en="Benzodiazepines",
        mech_ar="تعزيز GABA-A — الاعتماد والانسحاب أثر جماعي، ومزجها مع الأفيونات خطر تنفسي.",
        mech_en="Enhance GABA-A — dependence/withdrawal are class effects; opioid co-use is a respiratory risk.",
        members=(("diazepam", "ديازيبام"), ("lorazepam", "لورازيبام"),
                 ("alprazolam", "ألبرازولام"), ("midazolam", "ميدازولام")),
        suffixes=("azepam", "azolam"),
    ),
)

# أعضاء سريعون: اسم/بنية → بطاقة (يبنى مرة عند أول استدعاء)
_INDEX: dict[str, tuple[ClassCard, str, str]] | None = None


def _norm(text: str) -> str:
    return (text or "").strip().lower().replace(" ", "").replace("-", "").replace("_", "")


def _build_index() -> dict[str, tuple[ClassCard, str, str]]:
    idx: dict[str, tuple[ClassCard, str, str]] = {}
    for card in CATALOG:
        for en, ar in card.members:
            idx.setdefault(_norm(en), (card, "member", en))
            idx.setdefault(_norm(ar), (card, "member", ar))
        for smi in card.smiles:
            idx.setdefault(_norm(smi), (card, "smiles", smi))
    return idx


def _index() -> dict[str, tuple[ClassCard, str, str]]:
    global _INDEX
    if _INDEX is None:
        _INDEX = _build_index()
    return _INDEX


def _by_suffix(text_norm: str) -> ClassHit | None:
    """قواعد اللواحق/البادئات الآمنة — بطاقة واحدة قد تحمل أكثر من قاعدة."""
    for card in CATALOG:
        for suf in card.suffixes:
            if text_norm.endswith(suf):
                return ClassHit(card, "suffix", suf)
    for card in CATALOG:
        for pre in card.prefixes:
            if text_norm.startswith(pre):
                return ClassHit(card, "prefix", pre)
    return None


def classify(name_or_smiles: str) -> list[ClassHit]:
    """تصنيف محلي فوري — الأعضاء والبنى أولاً (الأدق) ثم اللواحق الآمنة.

    [] عند عدم التوفر — صدق بلا تخمين: اقترح ATC الحي في الواجهة.
    """
    norm = _norm(name_or_smiles)
    if not norm:
        return []
    if norm in _index():
        card, basis, matched = _index()[norm]
        return [ClassHit(card, basis, matched)]
    hit = _by_suffix(norm)
    return [hit] if hit else []


def card_by_id(class_id: str) -> ClassCard | None:
    for card in CATALOG:
        if card.class_id == class_id:
            return card
    return None


# ── العميل الحي — RxNorm RxClass (مجاني بلا مفتاح، نمط العملاء الرقيق) ──


def atc_live(name: str, timeout: float | None = None) -> list[tuple[str, str]] | None:
    """رموز ATC لدواء بالاسم عبر NIH RxNav — [(رمز, اسم), ...] أو None عند أي فشل.

    العقد (وثائق rxnav.nlm.nih.gov/REST الرسمية):
      1) GET /rxcui.json?name=<name>        → {"idGroup": {"rxnormId": [...]}}
      2) GET /rxclass/class/byRxcui.json?rxcui=<id>&relaSource=ATC
             → {"rxclassDrugInfoList": {"rxclassDrugInfo": [{"rxclassMinConceptItem":
                {"classId": "J01CA04", "className": "..."}}, ...]}}
    لا مفتاح، لا فوترة — وفشل الشبكة يعيد None بلا استثناءات (قاعدة المنصة).
    """
    if not (name or "").strip():
        return None
    t = RXNAV_TIMEOUT if timeout is None else timeout
    try:
        r1 = requests.get(f"{RXNAV_BASE}/rxcui.json", params={"name": name}, timeout=t)
        r1.raise_for_status()
        ids = (r1.json().get("idGroup") or {}).get("rxnormId") or []
        if not ids:
            return None
        r2 = requests.get(
            f"{RXNAV_BASE}/rxclass/class/byRxcui.json",
            params={"rxcui": ids[0], "relaSource": "ATC"}, timeout=t,
        )
        r2.raise_for_status()
        infos = ((r2.json().get("rxclassDrugInfoList") or {}).get("rxclassDrugInfo")) or []
        out: list[tuple[str, str]] = []
        seen: set[str] = set()
        for info in infos:
            item = info.get("rxclassMinConceptItem") or {}
            code, cls_name = item.get("classId"), item.get("className")
            if code and code not in seen:
                seen.add(code)
                out.append((code, cls_name or ""))
        return out or None
    except (requests.RequestException, ValueError, TypeError, KeyError):
        return None
