"""i18n مبسّط — عربي/إنجليزي لواجهة Pharma SDL.

النطاق: واجهة التطبيق (العناوين، التبويبات الجديدة، الأزرار، الشروح).
المنصّة عربية أولاً؛ الإنجليزية تغطي الواجهة الكاملة للتبويبين الجديدَين
(Docking/PGx) والقوالب العامة، والنصوص النثرية الطويلة للتبويبات القديمة
تبقى عربية في هذه المرحلة (خارطة الطريق تتوسّع تدريجياً).
"""
from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "ar": {
        # ── القالب العام ──
        "app_title": "🧬 Pharma SDL — مختبر الفارما الذاتي",
        "app_tagline": "> من الكتاب إلى الكود — من النظرية إلى الاكتشاف",
        "lab_header": "🧬 مختبرات Pharma SDL",
        "lang_label": "🌐 اللغة / Language",
        "tab_docking": "🧲 الربط الجزيئي",
        "tab_pgx": "💊 الجينوم الدوائي",
        "stlite_title": "⚠️ أنت تعمل في بيئة stlite (المتصفح/WASM) — بعض المختبرات معطلة",
        "stlite_body": (
            "بيئة المتصفح لا توفّر عجلات WASM لـ **RDKit** و**Vina**، لذا ستظهر أخطاء في "
            "المختبرات التي تعتمدهما (Make، Test، Predict، Capstone، Docking).\n\n"
            "**المتاح هنا:** الجينوم الدوائي PGx (البيانات المدمجة)، PubChem (عبر الشبكة).\n\n"
            "**لتشغيل كل المختبرات كاملة على جهازك:**\n"
            "```bash\npip install -r requirements.txt\nstreamlit run app.py\n```"
        ),
        # ── Docking ──
        "dock_title": "🧲 الربط الجزيئي — AutoDock Vina + Meeko",
        "dock_caption": (
            "مستقبلات حقيقية مُجهَّزة من PDB (7VH8/7CMD) — اختر الجزيء واربطه، "
            "ثم شاهد البوز ثلاثي الأبعاد وقارن درجة Vina بجسر Cheng-Prusoff من نموذج ML."
        ),
        "dock_lesson_title": "📖 وضع الدرس — كيف يعمل Vina؟",
        "dock_target": "الهدف (مستقبل مُجهَّز)",
        "dock_licand_src": "الجزيء المرتبط",
        "dock_preset": "أمثلة جاهزة",
        "dock_custom": "أو الصق SMILES الخاص بك",
        "dock_nposes": "عدد البوزات",
        "dock_exh": "شدة البحث (exhaustiveness)",
        "dock_btn": "🧲 اربط الجزيء",
        "dock_status_title": "⏳ ينفَّذ الربط — أربع مراحل…",
        "dock_phase1": "**1/4** تجهيز الليغاند (Meeko: بنية 3D + شحنات + PDBQT)…",
        "dock_phase2": "**2/4** بناء شبكات الطاقة داخل صندوق الربط…",
        "dock_phase3": "**3/4** البحث عن البوزات (Monte Carlo)…",
        "dock_phase4": "**4/4** تجهيز العرض ثلاثي الأبعاد والمقارنة…",
        "dock_done": "✅ اكتمل الربط",
        "dock_best": "أفضل طاقة ربط (Vina)",
        "dock_ml_pic50": "pIC50 من ML",
        "dock_dg_est": "ΔG المقدَّر (Cheng-Prusoff)",
        "dock_gap": "الفرق Vina−ML",
        "dock_compare_caption": (
            "اتفاق تقريبي (فرق < 2 kcal/mol) = متسق؛ اختلاف كبير = درّس السبب: "
            "دالة تسجيل Vina تقريبية، ونموذج ML مدرَّب على Mpro فقط."
        ),
        "dock_table_title": "🏆 البوزات والطاقات",
        "dock_3d_title": "🧊 البوز الأفضل — عرض ثلاثي الأبعاد",
        "dock_dl_pdb": "⬇️ أفضل بوز (PDB)",
        "dock_dl_pdbqt": "⬇️ كل البوزات (PDBQT)",
        "dock_no_engine": (
            "⚠️ vina/meeko غير متاحين في هذه البيئة — يُعرض تقدير Cheng-Prusoff "
            "من نموذج ML فقط، وشغّل النسخة الكاملة محلياً للربط الفعلي."
        ),
        "dock_compare_title": "⚖️ مقارنة فيزياء ↔ تعلّم آلي",
        "kcal": "kcal/mol",
        "nM": "nM",
        # ── ADMET (Ersilia) ──
        "tab_admet": "🧪 مركز ADMET",
        "admet_title": "🧪 مركز ADMET — نماذج Ersilia المفتوحة",
        "admet_caption": (
            "نموذجان مُتحقَّق منهما من Ersilia Model Hub يعملان محلياً (ersilia serve): "
            "سمية القلب hERG (CardioToxNet) والذوبانية المائية (SolTranNet) — "
            "وهما من أشهر عقبات التطوير قبل السريري."
        ),
        "admet_lesson_title": "📖 وضع الدرس — لماذا يقتل ADMET معظم المرشحات؟",
        "admet_model": "النموذج",
        "admet_input": "الجزيئات — SMILES واحد في كل سطر",
        "admet_preset": "املأ بأمثلة جاهزة",
        "admet_btn": "🧪 تنبؤ ADMET",
        "admet_status": "⏳ نداء خادم Ersilia المحلي…",
        "admet_no_server": (
            "لم يصل ردّ من خادم Ersilia — تُعرض مرجعية تعليمية مدمجة موثّقة "
            "بدل تنبؤات، ولا يُعاد تقدير قيم من خارج النموذج."
        ),
        "admet_server_hint": "كيف أشغّل الخادم؟",
        "admet_table_title": "🧾 النتائج — 🌐 Ersilia حي",
        "admet_ref_title": "📚 مرجعية مدمجة — أمثلة دوائية موثّقة",
        "admet_empty": "أدخل SMILES صالحاً واحداً على الأقل.",
        "admet_invalid": "أجزاء غير صالحة استُبعدت: {bad}",
        "admet_disclaimer": (
            "⚠️ محتوى تعليمي فقط — تنبؤات نماذج بحثية بحدود تعميم معروفة، "
            "والأحكام إرشادية وليست قراراً علاجياً أو تنظيمياً."
        ),
        "admet_col_value": "القيمة",
        "admet_col_verdict": "الحكم",
        # ── PGx ──
        "pgx_title": "💊 الجينوم الدوائي — توصيات CPIC",
        "pgx_caption": (
            "كيف يغيّر نمطك الوراثي (diplotype) قرار الدواء والجرعة؟ اختر الجين "
            "والنمط — البيانات الحية من api.cpicpgx.org مع احتياطي مدمج فوري."
        ),
        "pgx_gene": "الجين",
        "pgx_diplotype": "النمط الجيني (Diplotype)",
        "pgx_source": "مصدر البيانات",
        "pgx_src_offline": "📚 مدمج فوري (بلا شبكة)",
        "pgx_src_live": "🌐 CPIC حي (كاش 24 ساعة)",
        "pgx_function": "لماذا يهم هذا الجين؟",
        "pgx_substrates": "أشهر أدويته",
        "pgx_phenotype_of": "النمط الظاهري المقابل",
        "pgx_table_title": "🧾 التوصيات — {gene} / {diplotype}",
        "pgx_live_empty": (
            "الجلب الحي لم يُرجع صفوفاً مطابقة (شبكة أو تغطية) — عُرض الاحتياطي المدمج."
        ),
        "pgx_interpret_title": "🧠 التفسير الموجَّه",
        "pgx_disclaimer": (
            "⚠️ محتوى تعليمي فقط — مبسّط من إرشادات CPIC. لا يُستخدم لقرارات "
            "سريرية؛ راجع cpicpgx.org والنصوص الرسمية."
        ),
    },
    "en": {
        # ── Chrome ──
        "app_title": "🧬 Pharma SDL — Self-Directed Pharmacology Lab",
        "app_tagline": "> From book to code — from theory to discovery",
        "lab_header": "🧬 Pharma SDL Labs",
        "lang_label": "🌐 Language / اللغة",
        "tab_docking": "🧲 Docking",
        "tab_pgx": "💊 PGx",
        "stlite_title": "⚠️ You are running in stlite (browser/WASM) — some labs are disabled",
        "stlite_body": (
            "The browser environment has no WASM wheels for **RDKit** or **Vina**, "
            "so labs that depend on them (Make, Test, Predict, Capstone, Docking) "
            "will error out.\n\n"
            "**Available here:** PGx (bundled data) and PubChem (via network).\n\n"
            "**To run every lab locally:**\n"
            "```bash\npip install -r requirements.txt\nstreamlit run app.py\n```"
        ),
        # ── Docking ──
        "dock_title": "🧲 Molecular Docking — AutoDock Vina + Meeko",
        "dock_caption": (
            "Real receptors prepared from PDB (7VH8/7CMD) — pick a ligand, dock it, "
            "then inspect the 3D pose and compare the Vina score with the "
            "Cheng-Prusoff bridge from our ML model."
        ),
        "dock_lesson_title": "📖 Lesson mode — how does Vina work?",
        "dock_target": "Target (prepared receptor)",
        "dock_licand_src": "Ligand",
        "dock_preset": "Ready examples",
        "dock_custom": "Or paste your own SMILES",
        "dock_nposes": "Number of poses",
        "dock_exh": "Search effort (exhaustiveness)",
        "dock_btn": "🧲 Dock ligand",
        "dock_status_title": "⏳ Docking — four phases…",
        "dock_phase1": "**1/4** Ligand prep (Meeko: 3D conformer + charges + PDBQT)…",
        "dock_phase2": "**2/4** Building energy maps inside the binding box…",
        "dock_phase3": "**3/4** Pose search (Monte Carlo)…",
        "dock_phase4": "**4/4** Preparing the 3D view and comparison…",
        "dock_done": "✅ Docking complete",
        "dock_best": "Best binding energy (Vina)",
        "dock_ml_pic50": "pIC50 from ML",
        "dock_dg_est": "Estimated ΔG (Cheng-Prusoff)",
        "dock_gap": "Gap (Vina−ML)",
        "dock_compare_caption": (
            "Rough agreement (gap < 2 kcal/mol) = consistent; a large gap is a lesson: "
            "the Vina scoring function is approximate, and our ML model is Mpro-only."
        ),
        "dock_table_title": "🏆 Poses & energies",
        "dock_3d_title": "🧊 Best pose — 3D view",
        "dock_dl_pdb": "⬇️ Best pose (PDB)",
        "dock_dl_pdbqt": "⬇️ All poses (PDBQT)",
        "dock_no_engine": (
            "⚠️ vina/meeko unavailable here — showing only the Cheng-Prusoff "
            "estimate from the ML model; run the full app locally to dock."
        ),
        "dock_compare_title": "⚖️ Physics ↔ Machine-learning comparison",
        "kcal": "kcal/mol",
        "nM": "nM",
        # ── ADMET (Ersilia) ──
        "tab_admet": "🧪 ADMET Hub",
        "admet_title": "🧪 ADMET Hub — open Ersilia models",
        "admet_caption": (
            "Two verified models from the Ersilia Model Hub running locally "
            "(ersilia serve): hERG cardiotoxicity (CardioToxNet) and aqueous "
            "solubility (SolTranNet) — two of the biggest preclinical killers."
        ),
        "admet_lesson_title": "📖 Lesson mode — why does ADMET kill most candidates?",
        "admet_model": "Model",
        "admet_input": "Molecules — one SMILES per line",
        "admet_preset": "Fill with ready examples",
        "admet_btn": "🧪 Predict ADMET",
        "admet_status": "⏳ Calling the local Ersilia server…",
        "admet_no_server": (
            "No response from the Ersilia server — a documented built-in "
            "educational reference is shown instead; no out-of-model estimates."
        ),
        "admet_server_hint": "How to run the server?",
        "admet_table_title": "🧾 Results — 🌐 live Ersilia",
        "admet_ref_title": "📚 Built-in reference — documented drug examples",
        "admet_empty": "Enter at least one valid SMILES.",
        "admet_invalid": "Invalid parts excluded: {bad}",
        "admet_disclaimer": (
            "⚠️ Educational content only — research-model predictions with known "
            "generalization limits; verdicts are indicative, never clinical advice."
        ),
        "admet_col_value": "Value",
        "admet_col_verdict": "Verdict",
        # ── PGx ──
        "pgx_title": "💊 Pharmacogenomics — CPIC recommendations",
        "pgx_caption": (
            "How does your genotype (diplotype) change drug & dose decisions? "
            "Pick a gene and haplotype pair — live data from api.cpicpgx.org "
            "with an instant bundled fallback."
        ),
        "pgx_gene": "Gene",
        "pgx_diplotype": "Diplotype",
        "pgx_source": "Data source",
        "pgx_src_offline": "📚 Bundled instant (offline)",
        "pgx_src_live": "🌐 Live CPIC (24h cache)",
        "pgx_function": "Why does this gene matter?",
        "pgx_substrates": "Key substrates",
        "pgx_phenotype_of": "Corresponding phenotype",
        "pgx_table_title": "🧾 Recommendations — {gene} / {diplotype}",
        "pgx_live_empty": (
            "Live fetch returned no matching rows (network or coverage) — "
            "the bundled fallback is shown."
        ),
        "pgx_interpret_title": "🧠 Guided interpretation",
        "pgx_disclaimer": (
            "⚠️ Educational content only — simplified from CPIC guidelines. "
            "Never for clinical decisions; consult cpicpgx.org."
        ),
    },
}

DEFAULT_LANG = "ar"


def t(lang: str, key: str) -> str:
    """ترجمة مفتاح — يسقط إلى العربية ثم إلى المفتاح نفسه."""
    return STRINGS.get(lang, STRINGS[DEFAULT_LANG]).get(
        key, STRINGS[DEFAULT_LANG].get(key, key)
    )


def available_langs() -> list[str]:
    return list(STRINGS)
