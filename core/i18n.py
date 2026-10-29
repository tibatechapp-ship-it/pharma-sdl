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
        # ── توسيع المكتبة (Make/S6) ──
        "expand_title": "🌱 توسيع المكتبة حول بذرة",
        "expand_caption": (
            "جيران تشابه حقيقيون من PubChem (شبكة) أو إعادة تركيب BRICS كيميائية "
            "محلية بـ RDKit (بلا شبكة) — **مصدر النتائج معلَن دائماً**. "
            "هذا توسيع كيميائي منهجي، وليس نموذج توليد ذكاء اصطناعي."
        ),
        "expand_seed": "البذرة (SMILES)",
        "expand_n": "عدد الجزيئات المطلوب",
        "expand_btn": "🌱 وسّع المكتبة",
        "expand_empty": "أدخل SMILES للبذرة أولاً.",
        "expand_status": "⏳ تشابه PubChem أولاً، ثم BRICS محلي عند غياب الشبكة…",
        "expand_src_live": "🌐 نتائج تشابه PubChem الحيّة — {n} جزيئاً:",
        "expand_src_offline": "🧱 توسيع BRICS المحلي (بلا شبكة) — {n} جزيئاً:",
        "expand_none": "لم يُنتج أي توسيع — تحقق من صلاحية SMILES للبذرة.",
        # ── التوليد الموجّه بالهدف (S9) ──
        "goal_title": "🎯 التوليد الموجّه بالهدف — صنعناه محلياً",
        "goal_caption": (
            "مكافئ ChatChemTS/ChemTSv2 بلا مفتاح ولا TensorFlow: حلقات توسيع BRICS "
            "حول أفضل الناجين + قيود هدف صريحة تحددها أنت + دالة مكافأة شفافة "
            "(تشابه بالبذرة + QED). كل مرشح يعرض وصفاته — لا صندوق أسود."
        ),
        "goal_mw": "نطاق الوزن الجزيئي (دالتون)",
        "goal_logp": "أعلى LogP مقبول",
        "goal_sim": "أدنى تشابه بالبذرة (تانيموتو)",
        "goal_n": "عدد الناجين المطلوب",
        "goal_btn": "🎯 ولّد نحو الهدف",
        "goal_empty": "أدخل SMILES للبذرة أولاً (الحقل أعلاه).",
        "goal_running": "⏳ حلقات توسيع BRICS حول أفضل الناجين…",
        "goal_done": "✅ {n} جزيئاً اجتاز كل قيود الهدف عبر {r} جولة/جولات (قُيّم {p} مرشحاً فريداً):",
        "goal_none": "لم يجتز أي مرشح القيود بعد {r} جولة/جولات — خفّف الهدف أو جرّب بذرة أخرى.",
        "goal_invalid": "بذرة غير صالحة — تحقق من صيغة SMILES.",
        "goal_engine": "المحرك: BRICS موجّه محلي بالكامل — بلا مفتاح، بلا شبكة، بلا TensorFlow",
        "goal_props": "MW {mw:.0f} · LogP {logp:.1f} · TPSA {tpsa:.0f} · QED {qed:.2f} · تشابه {sim:.2f}",
        "goal_lesson": "📖 لماذا التوليد الموجّه مهم؟",
        "goal_lesson_text": (
            "التوليد العشوائي يُنتج مكتبات ضخمة يُرمى معظمها. التوليد الموجّه يقلب "
            "المعادلة: تحدد الهدف أولاً (نطاق MW قابل للفم، LogP غير كارثي، تشابه "
            "كافٍ بالبذرة لحفظ الفعالية المحتملة) ثم يُولّد ما يجتازه فقط — هذه فكرة "
            "ChemTS وREINVENT التجارية، ونفّذناها هنا محلياً بالكامل لتتعلم المبدأ "
            "بلا مفتاح ولا اشتراك. الدرس العملي: دالة المكافأة هي قرارك العلمي — "
            "قيود أضيق تعني فضاءً أصغر أنقى، وقيود فضفاضة تعني مكتبة أوسع أضعف."
        ),
        # ── المحلل الداخلي للبوزات (S7-a) ──
        "dock_contacts_title": "🔬 المحلل الداخلي للبوزات — صنعناه محلياً",
        "dock_contacts_caption": (
            "نفس بوزات Vina تُعاد قراءتها هندسياً بمحرك اتصالات محلي بسيط — "
            "فرق الدرجتين = اختلاف دالتي التسجيل، وهذا هو الدرس."
        ),
        "dock_contacts_lesson": "📖 كيف يُقيّم المحلل الداخلي؟",
        "dock_contacts_fail": "تعذّر تحليل البوزات — لن يُعطّل ذلك بقية العرض.",
        "col_vina": "Vina",
        "col_contacts": "اتصالات",
        "col_hbonds": "روابط H",
        "col_hydro": "كارهة للماء",
        "col_clashes": "تعارضات",
        "col_inhouse": "الدرجة الداخلية",
        # ── تحقق Boltz-2 الخارجي (S7-b — opt-in بمفتاح المستخدم) ──
        "boltz_title": "🌐 تحقق خارجي عبر Boltz-2 (اختياري — يحتاج مفتاح JapanFold)",
        "boltz_caption": (
            "يترافق بروتين + ليغاند ويعطي affinity مستقلاً عن Vina — للمقارنة، "
            "لا للاستبدال. المفتاح من البيئة `JAPANFOLD_API_KEY` فقط، ولا شيء "
            "يعمل بدونه: كل المختبرات المحلية تعمل بدون مفتاح."
        ),
        "boltz_seq": "تسلسل البروتين (FASTA أو تسلسل خام)",
        "boltz_btn": "🌐 أرسل تحقق Boltz-2",
        "boltz_no_key": (
            "لا يوجد `JAPANFOLD_API_KEY` في البيئة — هذه ميزة opt-in تعمل فقط "
            "بمفتاحك من japanfold.aiand.com/account/token (حساب جديد برصيد 100$). "
            "محرّك Vina المحلي يكفي لكل الدروس بلا مفتاح."
        ),
        "boltz_running": "وظيفة على خوادم JapanFold — قد تستغرق دقائق (انتظار محتجَز بلا sleep)…",
        "boltz_done": "✅ وصل رد Boltz-2 — حقول affinity (مقارنة بجانب Vina):",
        "boltz_fail": "فشل Boltz-2: `{reason}` — محركنا المحلي يعمل كما كان.",
        "boltz_empty": "أدخل تسلسل بروتين أولاً.",
        # ── القراءة التلقائية (S8) ──
        "auto_title": "⚙️ القراءة التلقائية — خط كامل من نقرة واحدة",
        "auto_caption": (
            "مكتبة حول بذرتك (PubChem حي → BRICS محلي احتياطاً) → فلتر ADME محلي "
            "→ ربط Vina → المحلل الداخلي → فلتر ADMET (Ersilia إن توفّر خادم وإلا "
            "محلي) → أعلام PGx صادقة → تقرير PDF عربي. بلا أي مفتاح."
        ),
        "auto_seed": "الجزيء البذرة (SMILES)",
        "auto_target": "الهدف (مستقبل مُجهَّز)",
        "auto_n": "حجم المكتبة المولّدة",
        "auto_top": "أقصى عدد يُربَط بـVina",
        "auto_btn": "⚙️ شغّل القراءة التلقائية",
        "auto_status": "⏳ ينفَّذ الخط الآلي — ست مراحل…",
        "auto_done": "✅ اكتملت القراءة التلقائية",
        "auto_no_engine": (
            "القراءة التلقائية تحتاج Vina+Meeko ومستقبلات مُجهَّزة — شغّل "
            "scripts/prepare_receptors.py أو استخدم خط Capstone العادي أعلاه."
        ),
        "auto_empty_seed": "أدخل بذرة صالحة أولاً.",
        "auto_m_lib": "المكتبة",
        "auto_m_docked": "أُربط",
        "auto_m_admet": "اجتاز ADMET",
        "auto_m_best": "أفضل Vina",
        "auto_engine": "محرك ADMET",
        "auto_best_smiles": "أفضل جزيء (SMILES)",
        "auto_table_title": "🏆 المرشّحون — Vina × المحلل الداخلي × ADMET",
        "auto_flags_title": "🧬 أعلام PGx وحجوزات صادقة",
        "auto_pdf": "⬇️ تقرير PDF عربي للقراءة التلقائية",
        "auto_no_pdf": "PDF غير متاح هنا — جرّب بيئة كاملة بالخطوط.",
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
        # ── Library expansion (Make/S6) ──
        "expand_title": "🌱 Expand the library around a seed",
        "expand_caption": (
            "Real similarity neighbours from PubChem (network) or local BRICS "
            "recombination via RDKit (offline) — **the source is always stated**. "
            "This is systematic chemistry expansion, not an AI generative model."
        ),
        "expand_seed": "Seed (SMILES)",
        "expand_n": "Number of molecules",
        "expand_btn": "🌱 Expand library",
        "expand_empty": "Enter a seed SMILES first.",
        "expand_status": "⏳ PubChem similarity first, then local BRICS when offline…",
        "expand_src_live": "🌐 Live PubChem similarity — {n} molecules:",
        "expand_src_offline": "🧱 Local BRICS expansion (offline) — {n} molecules:",
        "expand_none": "No expansion produced — check the seed SMILES validity.",
        # ── Goal-directed generation (S9) ──
        "goal_title": "🎯 Goal-directed generation — built locally",
        "goal_caption": (
            "A ChatChemTS/ChemTSv2 equivalent with no key and no TensorFlow: "
            "iterative BRICS expansion around the best survivors + explicit goal "
            "constraints you set + a transparent reward function (seed similarity "
            "+ QED). Every candidate shows its descriptors — no black box."
        ),
        "goal_mw": "Molecular weight range (Da)",
        "goal_logp": "Maximum acceptable LogP",
        "goal_sim": "Minimum seed similarity (Tanimoto)",
        "goal_n": "Number of survivors wanted",
        "goal_btn": "🎯 Generate toward goal",
        "goal_empty": "Enter the seed SMILES first (field above).",
        "goal_running": "⏳ BRICS expansion rounds around the best survivors…",
        "goal_done": "✅ {n} molecule(s) passed every goal constraint in {r} round(s) ({p} unique candidates evaluated):",
        "goal_none": "No candidate survived after {r} round(s) — relax the goal or try another seed.",
        "goal_invalid": "Invalid seed — check the SMILES syntax.",
        "goal_engine": "Engine: fully local directed BRICS — no key, no network, no TensorFlow",
        "goal_props": "MW {mw:.0f} · LogP {logp:.1f} · TPSA {tpsa:.0f} · QED {qed:.2f} · similarity {sim:.2f}",
        "goal_lesson": "📖 Why does goal-directed generation matter?",
        "goal_lesson_text": (
            "Random generation produces huge libraries, most of which get thrown "
            "away. Goal-directed generation flips the equation: you define the goal "
            "first (oral-friendly MW range, non-disastrous LogP, enough seed "
            "similarity to preserve plausible activity), then only what passes it "
            "is generated — the same idea behind commercial ChemTS and REINVENT, "
            "implemented here fully locally so you learn the principle with no key "
            "and no subscription. Practical lesson: the reward function is your "
            "scientific decision — tighter constraints mean a smaller purer space, "
            "looser ones mean a broader weaker library."
        ),
        # ── In-house pose analyzer (S7-a) ──
        "dock_contacts_title": "🔬 In-house pose analyzer — built locally",
        "dock_contacts_caption": (
            "The same Vina poses re-read geometrically by a simple local "
            "contact engine — the score gap is the scoring-function lesson."
        ),
        "dock_contacts_lesson": "📖 How does the in-house analyzer work?",
        "dock_contacts_fail": "Pose analysis unavailable — the rest of the view is unaffected.",
        "col_vina": "Vina",
        "col_contacts": "Contacts",
        "col_hbonds": "H-bonds",
        "col_hydro": "Hydrophobic",
        "col_clashes": "Clashes",
        "col_inhouse": "In-house score",
        # ── External Boltz-2 check (S7-b — opt-in with user's key) ──
        "boltz_title": "🌐 External check via Boltz-2 (optional — needs a JapanFold key)",
        "boltz_caption": (
            "Co-folds protein + ligand and returns an affinity independent of "
            "Vina — for comparison, not replacement. The key comes only from "
            "`JAPANFOLD_API_KEY`; nothing runs without it, all local labs keep "
            "working key-free."
        ),
        "boltz_seq": "Protein sequence (FASTA or raw)",
        "boltz_btn": "🌐 Submit Boltz-2 check",
        "boltz_no_key": (
            "No `JAPANFOLD_API_KEY` in the environment — this is an opt-in "
            "feature using only your key from japanfold.aiand.com/account/token "
            "(new accounts get $100 credit). The local Vina engine needs no key."
        ),
        "boltz_running": "Job running on JapanFold servers — may take minutes (long-poll, no sleep)…",
        "boltz_done": "✅ Boltz-2 responded — affinity fields (compare with Vina):",
        "boltz_fail": "Boltz-2 failed: `{reason}` — the local engine is unaffected.",
        "boltz_empty": "Enter a protein sequence first.",
        # ── Auto-read pipeline (S8) ──
        "auto_title": "⚙️ Auto-read — a full pipeline in one click",
        "auto_caption": (
            "Library around your seed (live PubChem → local BRICS fallback) → "
            "local ADME filter → Vina docking → in-house analyzer → ADMET filter "
            "(Ersilia if a server answers, else local) → honest PGx flags → "
            "Arabic PDF report. No keys at all."
        ),
        "auto_seed": "Seed molecule (SMILES)",
        "auto_target": "Target (prepared receptor)",
        "auto_n": "Generated library size",
        "auto_top": "Max molecules docked by Vina",
        "auto_btn": "⚙️ Run auto-read",
        "auto_status": "⏳ Auto pipeline running — six phases…",
        "auto_done": "✅ Auto-read complete",
        "auto_no_engine": (
            "Auto-read needs Vina+Meeko and prepared receptors — run "
            "scripts/prepare_receptors.py, or use the regular Capstone pipeline above."
        ),
        "auto_empty_seed": "Enter a valid seed first.",
        "auto_m_lib": "Library",
        "auto_m_docked": "Docked",
        "auto_m_admet": "ADMET passed",
        "auto_m_best": "Best Vina",
        "auto_engine": "ADMET engine",
        "auto_best_smiles": "Best molecule (SMILES)",
        "auto_table_title": "🏆 Candidates — Vina × in-house × ADMET",
        "auto_flags_title": "🧬 PGx flags & honest caveats",
        "auto_pdf": "⬇️ Auto-read PDF report (Arabic)",
        "auto_no_pdf": "PDF unavailable here — try a full environment with fonts.",
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
