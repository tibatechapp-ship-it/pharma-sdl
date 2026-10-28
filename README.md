# 🧬 Pharma SDL — مختبر الفارما الذاتي

> **"من الكتاب إلى الكود — من النظرية إلى الاكتشاف"**

منصة عربية تفاعلية لتعليم واكتشاف الأدوية بالذكاء الاصطناعي.

[![Tests](https://github.com/tibatechapp-ship-it/pharma-sdl/actions/workflows/tests.yml/badge.svg)](https://github.com/tibatechapp-ship-it/pharma-sdl/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## ✨ Features
- 🏭 **Make**: توليد SMILES بـ RDKit
- 🔬 **Test**: محاكاة hERG + LDL-C
- 🧠 **Analyze**: تعلم نشط (UCB + Pareto)
- 🧬 **PROTAC**: Vepdegestrant (أول PROTAC معتمد)
- 🔌 **PubChem**: جلب بيانات حقيقية

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
| 01 | الحرائك الدوائية (PK) | [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/tibatechapp-ship-it/pharma-sdl/blob/main/notebooks/01_PK.ipynb) | 45 دقيقة |
