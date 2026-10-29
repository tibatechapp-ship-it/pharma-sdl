# 🧬 Pharma SDL — مختبر الفارما الذاتي

> **"من الكتاب إلى الكود — من النظرية إلى الاكتشاف"**

منصة عربية تفاعلية لتعليم واكتشاف الأدوية بالذكاء الاصطناعي.

[![Tests](https://github.com/tibatechapp-ship-it/pharma-sdl/actions/workflows/tests.yml/badge.svg)](https://github.com/tibatechapp-ship-it/pharma-sdl/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)


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
- 🎯 **التوليد الموجّه بالهدف**: مكافئ ChatChemTS/ChemTSv2 محلي 100% — حلقات BRICS حول أفضل الناجين بقيود هدف صريحة (MW/LogP/TPSA/تشابه) ودالة مكافأة شفافة — بلا مفتاح ولا TensorFlow وبلا اشتراك — سبرنت 9
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
Python 3.11 | Streamlit | RDKit | AutoDock Vina 1.2 | Meeko | 3Dmol.js | scikit-learn | Plotly | PubChem API | CPIC API | Ersilia Model Hub | JapanFold API | ReportLab

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
| 10 | قياس TDC · تحسين Predict بـdescriptors · دفتر Boltz-2 | 📋 [ROADMAP-2026](docs/ROADMAP-2026.md) · [الاستراتيجية](docs/STRATEGY-2026.md) |

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

### 🧠 خط التعلم الكامل (13 مرحلة)
PK → RDKit Discovery → PK/PD المضادات → PROTAC → CYP2C19 → **ML التنبؤ** → **Capstone: من الهدف إلى القرار** → **Docking ثلاثي الأبعاد (Vina)** → **PGx السريري (CPIC)** → **ADMET (Ersilia)** → **المحلل الداخلي للبوزات** → **القراءة التلقائية الشاملة** → **التوليد الموجّه بالهدف**
