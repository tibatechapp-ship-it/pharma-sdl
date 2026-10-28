# 🧬 Pharma SDL — مختبر الفارما الذاتي

> **"من الكتاب إلى الكود — من النظرية إلى الاكتشاف"**

منصة عربية تفاعلية لتعليم واكتشاف الأدوية بالذكاء الاصطناعي.

[![Tests](https://github.com/tibatechapp-ship-it/pharma-sdl/actions/workflows/tests.yml/badge.svg)](https://github.com/tibatechapp-ship-it/pharma-sdl/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)


## 🌐 Live Demo

_قيد النشر_

> إذا لم يكن الرابط يعمل، شغّل محليًا: `streamlit run app.py`

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
Python 3.11 | Streamlit | RDKit | scikit-learn | Plotly | PubChem API

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

### 🧠 خط التعلم الكامل (6 مختبرات)
PK → RDKit Discovery → PK/PD المضادات → PROTAC → CYP2C19 → **ML التنبؤ** → Capstone (قريباً)
