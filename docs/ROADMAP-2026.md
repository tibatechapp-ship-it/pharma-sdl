# 🗺️ خارطة طريق Pharma SDL — دمج أدوات 2025-2026

> مراجعة داخلية + مشهد الأدوات المفتوحة/المغلقة المُتحقق منها (تشرين الأول 2026)
> كل بند مرتبط بالأداة الحقيقية ورخصتها وطريقة الدمج المقترحة.

## 1) ملاحظات المراجعة الداخلية (تشرين الأول 2026)

| # | الملاحظة | الخطورة | العلاج المقترح |
|---|---|---|---|
| 1 | Predict (RF على Morgan فقط): R² ≈ 0.44 | متوسطة | إضافة descriptors فيزيائية (MW/LogP/TPSA/HBD/HBA) للميزات → رفع متوقع لـ R² ≈ 0.55-0.60 |
| 2 | PGx ثابت (CPIC 2022 مدمجة يدوياً) | متوسطة | سحب حي من CPIC API مع كاش 24h واحتياطي محلي |
| 3 | لا يوجد Docking حقيقي (3D) | عالية | AutoDock Vina + Meeko مع مستقبلات مُجهزة مسبقاً |
| 4 | ADME قواعد فقط (Lipinski/Veber) | متوسطة | طبقة تنبؤ ML متعدد المهام (TDC/ADMET-AI) |
| 5 | لا تصميم توليدي موجّه | منخفضة | REINVENT 4 priors في Colab (ثقيل للـ Cloud) |
| 6 | Live Demo ما زال «قيد النشر» في README | إدارية | بانتظار رابط المستخدم |
| 7 | هدف واحد فقط (Mpro) لنموذج التنبؤ | منخفضة | تعليمياً مقبول — توثيق الحدود موجود في Model Card |

## 2) الأدوات المفتوحة المُتحقق منها — وكيف نستفيد منها

| الأداة | الرخصة | ماذا تفعل | دمجنا المقترح | الجهد |
|---|---|---|---|---|
| **AutoDock Vina 1.2** (Scripps) | Apache-2.0 | Docking سريع بدقة مرجعية | تبويب Docking: `pip install vina` + مستقبلات PDBQT جاهزة (Mpro 7VH8) | متوسط — سبرنت 4 |
| **Meeko** (Scripps) | GPL-2/Apache dual | تجهيز ligands PDBQT + تصدير SDF للبوزات | بايثون API مباشر داخل التبويب | مع Vina |
| **CPIC/ClinPGx API** (api.cpicpgx.org) | بيانات مفتوحة، PostgREST JSON | توصيات PGx سريرية حية | تبويب PGx: CYP2D6 (تاموكسيفين/كوديين)، TPMT (ثيوبورينات)، UGT1A1 (إرينوتيكان) — كاش 24h | متوسط — سبرنت 4 |
| **TDC — Therapeutics Data Commons** (tdcommons.ai) | MIT | مجموعات بيانات + benchmarks + oracles جاهزة | دفتر Lab07: قياس نموذجنا على benchmark رسمي ومقارنة الـ leaderboard | سهل |
| **Boltz-2** (MIT/Valence/Recursion) | MIT كامل (أوزان+تدريب) | Co-folding + تنبؤ affinity يقارب FEP بألف مرة أرخص | دفتر Lab08 على Colab GPU: طيّ نيرماتريلڤير مع Mpro → مقارنة ثلاثية (ML سريع / Docking / Co-folding) | متوسط (GPU) |
| **Ersilia Model Hub** | GPL-3.0 | 200+ نموذج جاهز لأمراض المهملة | دفتر/تبويب «الصحة العالمية»: نماذج الملاريا والسل (eos8d8a نفاذية السل) — يربط بمختبر MIC | متوسط |
| **ADMET-AI v2** (Harvard) | MIT | 41 مهمة ADMET بـ ensemble — مصدّر TDC | ترقية قمع ADME: تنبؤ ML بدل القواعد فقط (كولاب أولاً بسبب torch) | متوسط |
| **REINVENT 4** (AstraZeneca) | Apache-2.0 | تصميم توليدي: de novo/scaffold/linker/تحسين | دفتر Lab09: أخذ عينات من priors المنشورة + توجيهها بنموذجنا pIC50 (دورة تعلم نشط كاملة) | متوسط-ثقيل (GPU) |
| **RDKit** (مستخدمة) | BSD | الأساس الكيميائي | — | — |
| **Chemprop** (MIT) | MIT | MPNN للخصائص — معيار مجال | مرجع مقارنة في دفتر القياس | سهل |

## 3) أدوات مغلقة بوصول مجاني — نقاط تقاطع تعليمية

| الأداة | الوصول | استفادتنا |
|---|---|---|
| **AlphaFold 3 Server** (DeepMind) | مجاني غير تجاري (~20 مهمة/يوم) | تحقق مرجعي لنتائج Boltz-2 في الدفاتر؛ اقتباس في فصول الكتاب |
| **ADMETlab 3.0** (ويب) | مجاني | محطة تحقق متقاطع لنتائج ADMET (سكرين شوت + مقارنة تعليمية) |
| **SwissADME / pkCSM** (ويب) | مجاني | نفس الدور — تعليم منهجية التحقق المتقاطع |
| **Schrödinger (Maestro/Glide/FEP+)** | ترخيص أكاديمي مجاني | مسار متقدم للطلبة بعد إتقان مختبراتنا المفتوحة |
| **OpenEye Toolkits** | أكاديمي مجاني | بديل تجاري لاحق عند الحاجة |
| **Chai-1** | أوزان غير تجارية + كود Apache | بديل Boltz-2 للمقارنة في الدفاتر |

## 4) خطة التنفيذ المرتبة

### سبرنت 4 (الحالي — مخطط)
1. **تبويب Docking**: Vina + Meeko + 2 مستقبلات مُجهزة (Mpro، إنزيم آخر) + عرض بوز 3D + مقارنة Vina score ↔ ML pIC50
2. **تبويب PGx حي**: CPIC API (CYP2D6/TPMT/UGT1A1) + كاش + احتياطي محلي
3. مبدّل عربي/إنجليزي · GitHub Pages

### سبرنت 5 (مقترح من هذا البحث)
4. **Lab07**: قياس نموذجنا على TDC benchmark (ثقافة القياس الصادق)
5. **تحسين Predict**: إضافة descriptors للميزات → رفع R² (تحديث Model Card)
6. **Lab08 Boltz-2 على Colab**: من التسلسل إلى الـ affinity — تكتمل القصة (جين → بنية → ربط → PK/PD → قرار)

### سبرنت 6
7. تكامل Ersilia (الصحة العالمية) · دفتر REINVENT 4 توليدي · ترقية ADME بـ ML

## المصادر المُتحقق منها
- Boltz-2: PubMed 40667369 (Passaro et al. 2025) · tamarind.bio/tools/boltz · github.com/jwohlwend/boltz
- Meeko: JCIM 2025 (doi:10.1021/acs.jcim.5c02271) · meeko.readthedocs.io
- TDC: tdcommons.ai · Ersilia: ersilia.io · github.com/ersilia-os
- CPIC/ClinPGx API: api.cpicpgx.org · clinpgx.org/page/cpicResources
- REINVENT 4: github.com/MolecularAI/REINVENT4 (Apache-2.0، نشط 2026-10)
- ADMET-AI: github.com/swansonk14/admet_ai
- AlphaFold 3 Server: الإعلان الرسمي DeepMind (مجاني غير تجاري)
