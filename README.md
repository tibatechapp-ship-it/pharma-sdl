<p align="center">
  <img src=".github/assets/banner.svg" alt="Pharma SDL — مختبر الفارما الذاتي" width="100%">
</p>

# 🧬 Pharma SDL — مختبر الفارما الذاتي

> **"من الكتاب إلى الكود — من النظرية إلى الاكتشاف"**

منصة عربية تفاعلية لتعليم واكتشاف الأدوية بالذكاء الاصطناعي.

<p align="center">
  <a href="https://github.com/tibatechapp-ship-it/pharma-sdl/actions/workflows/tests.yml"><img src="https://github.com/tibatechapp-ship-it/pharma-sdl/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white" alt="Python 3.11 | 3.12">
  <img src="https://img.shields.io/badge/Streamlit-UI-FF4B4B?logo=streamlit&logoColor=white" alt="Streamlit">
  <img src="https://img.shields.io/badge/%D8%A7%D8%AE%D8%AA%D8%A8%D8%A7%D8%B1%D8%A7%D8%AA-170%2B-brightgreen" alt="170+ tests">
  <a href=".github/workflows/platform.yml"><img src="https://github.com/tibatechapp-ship-it/pharma-sdl/actions/workflows/platform.yml/badge.svg" alt="Platform API"></a>
  <img src="https://img.shields.io/badge/API-FastAPI%20v0.2.0-009688?logo=fastapi&logoColor=white" alt="FastAPI platform">
</p>

---

## 🚀 v0.2.0 — النقلة النوعية: منصة API-First

> **الخبر:** طبقة جديدة كاملة `pharma_sdl/` تحوّل المشروع من تطبيق تعليمي إلى
> **منصة اكتشاف أدوية تشغيلية** وفق [الخطة الاستراتيجية v1.1](docs/plan/PharmaSDL_Strategic_Plan_v1.1.pdf) —
> واللوحة التعليمية أسفله تعمل كما هي بلا أي كسر.

**خط التشغيل الكامل:** تنقية ← فرز ظاهري ← إجماع علاجي ← مختبر ← تقرير —
بمحركات قابلة للتبديل وسياسات أهداف صريحة (Mpro **غير تساهمي حصراً**).

| الوحدة | ماذا تفعل |
|---|---|
| `curation` | توحيد + إزالة تكرار (InChIKey) + PAINS + Lipinski/Veber + **بوابة الرؤوس التساهمية** — كل رفض مسبَّب عربي/إنجليزي |
| `targets` | سجل أهداف بسياسات: 7VH8 (Mpro) و7CMD (PLpro) بصناديق ربط مُتحقق منها |
| `engines` | `simulation` (حتمي، دائماً متاح) · `vina` (ربط فعلي) · `boltz2` (تقارب مباشر عبر بوابة) — التراجع بينها **مُعلَن** |
| `screening` | جولة فرز كاملة من نداء واحد — **الهيكل الهزّ من الخطة منفَّذ** |
| `affinity` | جسر Cheng-Prusoff (ΔG ≈ −1.364×pIC50) مع حكم اتفاق صريح |
| `lab` | مقبس مختبر موحّد — FRET محاكى الآن، دمج حقيقي لاحقاً بعلامة `simulated=true` |
| `reporting` | تقرير Markdown/JSON ثنائي اللغة لكل جولة |
| `api` | FastAPI + طابور مهام + OpenAPI تفاعلي على `/docs` |

### ⚡ جرب المنصة في 60 ثانية

```bash
pip install -r requirements.txt -r requirements-dev.txt

# بوابة الـAPI مع توثيق تفاعلي
uvicorn pharma_sdl.api.app:create_app --factory --port 8000
#   → http://localhost:8000/docs

# أو من سطر الأوامر مباشرة
pharma-sdl engines
pharma-sdl targets
pharma-sdl screen --target 7VH8_A --ligands data/demo_ligands.csv --top 10

# أو بالحاويات (API على :8000 + لوحة على :8501)
docker compose up --build
```

نداء فرز حي (وضع العرض — 24 جزيء جاهزون):

```bash
curl -s -X POST localhost:8000/api/v1/screening/runs \
  -H 'Content-Type: application/json' -d '{"target_id": "7VH8_A", "top_n": 5}'
# → 202 {"job_id": "...", "run_url": "..."} ثم:
curl -s localhost:8000/api/v1/screening/runs/<job_id> | python3 -m json.tool
curl -s "localhost:8000/api/v1/screening/runs/<job_id>/report?lang=ar"
```

📖 التفاصيل الكاملة: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) ·
[قرارات التصميم ADR-0001…0005](docs/adr/) · [CHANGELOG](CHANGELOG.md)

---

## 🌐 Live Demo

_قيد النشر_

> 📖 **دليل المنصة (GitHub Pages)**: <https://tibatechapp-ship-it.github.io/pharma-sdl/>
> (فعّل من Settings → Pages → Branch: main / folder: docs)

> إذا لم يكن الرابط يعمل، شغّل محلياً: `streamlit run app.py`

## ✨ Features
- 🏭 **Make**: توليد SMILES بـ RDKit
- 🔬 **Test**: محاكاة hERG + LDL-C
- 🧠 **Analyze**: تعلم نشط (UCB + Pareto)
- 🧬 **PROTAC**: Vepdegestrant (أول PROTAC معتمد)
- 🔌 **PubChem**: جلب بيانات حقيقية (مخزّنة ساعة — أداء أعلى)
- 🧪 **MIC Lab**: PK/PD للمضادات الحيوية (3 مضادات، 3 مؤشرات)
- 🧬 **PROTAC Lab**: Vepdegestrant (Hook Effect, ternary complex)
- 🧫 **CYP2C19**: طب شخصي (4 أنماط، CPIC 2022، بيانات قطر)
- 🤖 **Predict**: تنبؤ pIC50 بتعلم آلي حقيقي — RandomForest على بصمات Morgan مدرّب على قياسات Mpro من ChEMBL (900 جزيء) مع فترة ثقة من تباين الأشجار
- 🎓 **Capstone**: خط الاكتشاف الكامل «من الهدف إلى القرار» — مكتبة (PubChem حي أو محلية) → فلترة ADME (Lipinski+Veber) → تنبؤ ML → قرار PK/PD (C90 من Hill مقابل Cmax فموي) → تقرير PDF عربي جاهز للتنزيل
- 🧲 **Docking**: ربط جزيئي حقيقي بـ AutoDock Vina + Meeko على مستقبلات PDB مُجهّزة مسبقاً (Mpro 7VH8 — نفس هدف نموذج ML، وPLpro 7CMD)، عرض البوز ثلاثي الأبعاد بـ 3Dmol.js، وضع درس عربي كامل، ومقارنة فيزياء↔ML عبر جسر Cheng-Prusoff (ΔG ≈ −1.364×pIC50) — سبرنت 4
- 💊 **PGx**: توصيات الصيدلة الجينية لخمسة جينات (CYP2D6 · TPMT · UGT1A1 · CYP2C19 · CYP3A5) — جلب حي من CPIC API بكاش 24 ساعة + احتياطي مدمج فوري + تنبيه تعليمي دائم — سبرنت 4
- 🧪 **ADMET Hub (Ersilia)**: نماذج مفتوحة موثّقة (hERG CardioToxNet + ذوبان SolTranNet) عبر خادم Ersilia محلي — بلا مفاتيح، وعند غياب الخادم مرجعية دوائية موثّقة بدل أرقام مختلقة — سبرنت 5
- 🌱 **توسيع المكتبة**: جيران تشابه حقيقيون من PubChem (بلا مفتاح) أو BRICS محلي عبر RDKit (بلا شبكة) — المصدر يُعلَن دائماً — سبرنت 6
- 🎯 **التوليد الموجّه بالهدف**: مكافئ ChatChemTS/ChemTSv2 محلي 100% — حلقات BRICS حول أفضل الناجين بقيود هدف صريحة (MW/LogP/TPSA/تشابه) ودالة مكافأة شفافة، مع رسم بنيوي 2D لكل ناجٍ — بلا مفتاح ولا TensorFlow وبلا اشتراك — سبرنت 9
- 🗂️ **التصنيف الدوائي**: دليل ATC لمنظمة الصحة العالمية — 23 مجموعة ثنائية اللغة (البنسلينات، الفلوروكينولونات، الستاتينات…) بآليات العمل والأعضاء، تصنيف فوري لاسم عربي/إنجليزي/SMILES + ATC حي من RxNorm (بلا مفتاح) + درس «ما المتبع عالمياً» — سبرنت 10
- 🔬 **المحلل الداخلي للبوزات**: محرك تسجيل ثانٍ صنعناه محلياً (اتصالات/روابط H/تعارضات) يقرأ نفس بوزات Vina — درس «دالتا تسجيل، نتائج مختلفة» — سبرنت 7
- 🌐 **تحقق Boltz-2 (opt-in)**: ميزة اختيارية بمفتاح المستخدم من البيئة فقط (JAPANFOLD_API_KEY) — كل المختبرات تعمل بلا مفتاح — سبرنت 7
- ⚙️ **القراءة التلقائية**: خط كامل من نقرة واحدة — مكتبة حول البذرة → فلتر ADME محلي → ربط Vina → المحلل الداخلي → فلتر ADMET (Ersilia إن توفّر وإلا محلي) → أعلام PGx صادقة → تقرير PDF عربي — سبرنت 8
- 🌐 **مبدّل عربي/إنجليزي** في الشريط الجانبي (يغطي العنوان والتبويبات الجديدة والقوالب العامة)

### 🤖 Model Card (Predict)
| البند | القيمة |
|---|---|
| البيانات | قياسات IC50 حقيقية لـ SARS-CoV-2 Mpro (CHEMBL4523582) — وسيط pchembl لكل جزيء، نظيفة من قياسات data_validity_comment |
| الميزات | بصمات Morgan (radius=2، 2048 بت) |
| النموذج | RandomForestRegressor (300 شجرة، random_state=42) |
| الأداء | R² ≈ 0.44 ، RMSE ≈ 0.78 على 180 جزيء اختبار |
| عدم اليقين | تباين تنبؤات الأشجار (إبيستيمي عملي) — فترات عريضة = جزيء غريب عن التدريب |
| الحدود | ميزات ثنائية الأبعاد فقط، بيانات فحص واحد (Mpro) — لا يستخدم لقرارات سريرية |

## 🚀 Quick Start
```bash
git clone https://github.com/tibatechapp-ship-it/pharma-sdl.git
cd pharma-sdl
pip install -r requirements.txt
streamlit run app.py
```

## 🧪 Tests
```bash
pytest -v
pytest --cov=core --cov-report=html
```

## 📚 Tech Stack
Python 3.11 | **FastAPI (منصة v0.2.0)** | Streamlit | RDKit | AutoDock Vina 1.2 | Meeko | 3Dmol.js | scikit-learn | Plotly | PubChem API | CPIC API | Ersilia Model Hub | JapanFold API | ReportLab | Docker

## 🤝 المساهمة والتوثيق

| الملف | المحتوى |
|---|---|
| [CONTRIBUTING.md](CONTRIBUTING.md) | بيئة التطوير، سير العمل، معايير القبول |
| [SECURITY.md](SECURITY.md) | سياسة الإبلاغ عن الثغرات وسياسة المفاتيح |
| [CHANGELOG.md](CHANGELOG.md) | سجل التغييرات الإصداري |
| [docs/ROADMAP-2026.md](docs/ROADMAP-2026.md) | خارطة السبرنت 9+ |

الـIssues والـPRs لهما قوالب جاهزة: [تقرير علة](.github/ISSUE_TEMPLATE/bug_report.yml) · [اقتراح ميزة](.github/ISSUE_TEMPLATE/feature_request.yml) · [قالب PR](.github/PULL_REQUEST_TEMPLATE.md).

## 🗺️ سجل السبرنتات

| # | النطاق | الحالة |
|---|---|---|
| 1 | كاش PubChem · README · دفاتر Colab | ✅ |
| 2 | Lab06 ML (pIC50 + فترة ثقة) · تبويب Predict | ✅ |
| 3 | Capstone: خط اكتشاف كامل + تقرير PDF عربي | ✅ |
| 4 | Docking (Vina+Meeko) · PGx (CPIC) · مبدّل لغة · GitHub Pages | ✅ |
| 5 | ADMET Hub (Ersilia) — نماذج موثّقة بلا مفاتيح + مرجعية مدمجة | ✅ |
| 6 | توسيع المكتبة (PubChem/BRICS) · عميل JapanFold موثّق بالعقد الفعلي | ✅ |
| 7 | المحلل الداخلي للبوزات (محرك ثانٍ محلي) · تحقق Boltz-2 opt-in | ✅ |
| 8 | القراءة التلقائية: زر واحد من البذرة إلى تقرير PDF عربي | ✅ |
| 9 | التوليد الموجّه بالهدف — مكافئ ChatChemTS محلي حتمي بلا مفتاح (ChatChemTS يشترط OpenAI مدفوع) | ✅ |
| 10 | التصنيف الدوائي ATC (23 مجموعة + RxNorm حي) + رسم 2D + إثراء MIC بالمجموعات | ✅ |
| 11 | قياس TDC · تحسين Predict بـdescriptors · دفتر Boltz-2 | 📋 [ROADMAP-2026](docs/ROADMAP-2026.md) · [الاستراتيجية](docs/STRATEGY-2026.md) |
| **12** | **النقلة النوعية: منصة API-First — `pharma_sdl/` بـ9 وحدات، FastAPI، Vina حقيقي خلف عقد محركات، بوابة التساهمية، Docker، 46 اختباراً** | ✅ [v0.2.0](CHANGELOG.md) · [المعمارية](docs/ARCHITECTURE.md) |

### إعادة توليد المستقبلات المُجهّزة
```bash
python scripts/prepare_receptors.py   # ينزّل 7VH8/7CMD من RCSB ويجهّز PDBQT ويتحقق بالـself-dock
```

## 📄 License
MIT © 2026

## 📓 Notebooks

| # | المختبر | Colab | الوقت |
|---|---|---|---|
| 01 | الحركية الدوائية (PK) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tibatechapp-ship-it/pharma-sdl/blob/main/download/Lab01-Pharmacokinetics/Lab01_Pharmacokinetics.ipynb) | 45 دقيقة |
| 02 | اكتشاف الأدوية (RDKit) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tibatechapp-ship-it/pharma-sdl/blob/main/download/Lab02-Drug-Discovery-RDKit/Lab02_Drug_Discovery_RDKit.ipynb) | 60 دقيقة |
| 03 | PK/PD المضادات | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tibatechapp-ship-it/pharma-sdl/blob/main/download/Lab03-PKPD-Antibiotics/Lab03_PKPD_Antibiotics.ipynb) | 60 دقيقة |
| 04 | PROTAC (Vepdegestrant) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tibatechapp-ship-it/pharma-sdl/blob/main/download/Lab04-PROTAC/Lab04_PROTAC_Vepdegestrant.ipynb) | 45 دقيقة |
| 05 | CYP2C19 (قطر) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tibatechapp-ship-it/pharma-sdl/blob/main/download/Lab05-CYP2C19/Lab05_CYP2C19.ipynb) | 45 دقيقة |
| 06 | التنبؤ بالفعالية (ML) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tibatechapp-ship-it/pharma-sdl/blob/main/download/Lab06-ML-Potency/Lab06_ML_Potency.ipynb) | 60 دقيقة |

### 🧠 خط التعلم الكامل (14 مرحلة)
PK → RDKit Discovery → PK/PD المضادات → PROTAC → CYP2C19 → **ML التنبؤ** → **Capstone: من الهدف إلى القرار** → **Docking ثلاثي الأبعاد (Vina)** → **PGx السريري (CPIC)** → **ADMET (Ersilia)** → **المحلل الداخلي للبوزات** → **القراءة التلقائية الشاملة** → **التوليد الموجّه بالهدف** → **التصنيف الدوائي ATC**
