import json

cells = []

def md(text):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)})

def code(text):
    cells.append({"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": text.splitlines(keepends=True)})

md("""# Lab 05 — CYP2C19 والطب الشخصي في clopidogrel

**Pharma SDL — Self-Driving Lab**

> **المشكلة:** clopidogrel (Plavix) دواء طليعة (prodrug) يحتاج CYP2C19 لتحويله للشكل النشط.
> **البيانات:** QPGx-CARES (قطر 2026): 376 مريض PCI، 22% حاملو LoF، وفر 300 QR/مريض/سنة.

**الأهداف:**
1. فهم 4 أنماط CYP2C19 (UM/NM/IM/PM)
2. محاكاة تثبيط الصفيحات لكل نمط
3. توصيات CPIC (2022)
4. تحليل اقتصادي (Qatar case)
5. مقارنة clopidogrel vs ticagrelor/prasugrel

---
""")

md("## 1. إعداد البيئة\n")
code("""import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

plt.rcParams['figure.figsize'] = (10, 6)
sns.set_style('whitegrid')
print('✅ البيئة جاهزة')
""")

md("## 2. الأنماط الجينية (CPIC 2022)\n")
code("""phenotypes = {
    'UM': {'name': 'Ultra-rapid', 'name_ar': '?,?,?,?,? فائق', 'score': 3.0, 'prevalence_me': '1-2%', 'prevalence_qatar': '2%'},
    'NM': {'name': 'Normal', 'name_ar': '?,?,?,?,? طبيعي', 'score': 2.0, 'prevalence_me': '35-40%', 'prevalence_qatar': '36%'},
    'IM': {'name': 'Intermediate', 'name_ar': '?,?,?,?,? متوسط', 'score': 1.0, 'prevalence_me': '18-25%', 'prevalence_qatar': '22%'},
    'PM': {'name': 'Poor', 'name_ar': '?,?,?,?,? ضعيف', 'score': 0.0, 'prevalence_me': '2-15%', 'prevalence_qatar': '5%'},
}

df = pd.DataFrame(phenotypes).T
print(df[['name_ar', 'score', 'prevalence_me', 'prevalence_qatar']])
""")

md("## 3. محاكاة تثبيط الصفيحات\n")
code("""def predict_inhibition(score, dose):
    max_inh = {3.0: 95, 2.0: 85, 1.0: 45, 0.0: 15}[score]
    dose_factor = np.log10(dose + 1) / np.log10(151)
    dose_factor = np.clip(dose_factor, 0, 1.2)
    return max_inh * dose_factor

def time_course(score, dose, hours=72):
    t = np.linspace(0, hours, 200)
    peak = predict_inhibition(score, dose)
    rise = 1 - np.exp(-t / 3.0)
    decay = np.exp(-t / 72)
    return t, peak * rise * decay

fig, ax = plt.subplots(figsize=(12, 6))
colors = {'UM': '#3b82f6', 'NM': '#22c55e', 'IM': '#f59e0b', 'PM': '#ef4444'}
for key, p in phenotypes.items():
    t, resp = time_course(p['score'], 75)
    ax.plot(t, resp, label=f"{p['name_ar']} ({key})", color=colors[key], lw=2)

ax.axhline(50, color='gray', ls='--', label='حد الفعالية (50%)')
ax.set_xlabel('الزمن (ساعة)')
ax.set_ylabel('تثبيط الصفيحات (%)')
ax.set_title('استجابة clopidogrel (75 mg) حسب النمط الجيني')
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.show()
""")

md("## 4. جدول التوصيات (CPIC 2022)\n")
code("""recs = {
    'UM': {'clopidogrel': '✅ 75 mg قياسي', 'alternative': 'لا حاجة', 'color': 'green'},
    'NM': {'clopidogrel': '✅ 75 mg قياسي', 'alternative': 'لا حاجة', 'color': 'green'},
    'IM': {'clopidogrel': '⚠️ 150 mg أو بديل', 'alternative': 'Ticagrelor/Prasugrel', 'color': 'orange'},
    'PM': {'clopidogrel': '❌ غير موصى', 'alternative': 'Ticagrelor/Prasugrel', 'color': 'red'},
}

for key, r in recs.items():
    print(f"{key:3s} | {r['clopidogrel']:25s} | {r['alternative']}")
""")

md("## 5. التحليل الاقتصادي (Qatar case)\n")
code("""# بيانات QPGx-CARES (قطر 2026)
n_patients = 376
lof_carriers = 0.22
change_rate = 0.22
cost_per_patient = 300  # QR/سنة

print(f"عدد المرضى: {n_patients}")
print(f"حاملو LoF: {int(n_patients * lof_carriers)} ({lof_carriers*100:.0f}%)")
print(f"تغيير العلاج: {int(n_patients * change_rate)} ({change_rate*100:.0f}%)")
print(f"الوفر: {n_patients * cost_per_patient:,} QR/سنة")
print(f"الوفر بالدولار: ${n_patients * cost_per_patient / 3.64:,.0f}/سنة")
""")

md("## 6. الخلاصة\n")
md("""
### النتائج الرئيسية:
1. **22% من المرضى** لا يستفيدون من clopidogrel (PM/IM)
2. **البديل (ticagrelor/prasugrel)** ضروري لـ PM
3. **الوفر: 300 QR/مريض/سنة** (قطر)
4. **CPIC guidelines** توصي بتجنب clopidogrel لـ PM

### التحديات:
- تكلفة الفحص الجيني
- التدريب (80% قبول من الأطباء)
- 37% إضافية (لا تغيير)

### الخطوات التالية:
- إضافة فحص CYP2C19 قبل PCI
- تكامل مع EHR
- تعميم في دول GCC
""")

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11.0"}
    },
    "nbformat": 4,
    "nbformat_minor": 5
}
with open('download/Lab05-CYP2C19/Lab05_CYP2C19.ipynb', 'w') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print("✅ Notebook created")
