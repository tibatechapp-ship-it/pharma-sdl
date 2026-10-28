#!/usr/bin/env python3
"""
normalize_drug_names.py — تنسيق INN (Brand) في المشروع
- يحوّل "Brand (INN)" → "INN (Brand)"
- يحوّل "Brand" أول ذكر → "INN (Brand)"
- يحذف الشركات من المتن (يبقيها في المصادر)
- يحافظ على PRESERVE و INN

Usage:
    python scripts/normalize_drug_names.py --dry-run
    python scripts/normalize_drug_names.py --apply
"""
import re
import json
import argparse
from pathlib import Path


# ═══════════════════════════════════════════════════════════
# قاعدة البيانات: INN ↔ Brand
# ═══════════════════════════════════════════════════════════
DRUG_PAIRS = {
    'Enlicitide': 'Lipfendra',
    'Vepdegestrant': 'Veppanu',
    'Orforglipron': 'Foundayo',
    'Pirtobrutinib': 'Jaypirca',
    'Imlunestrant': 'Inluriyo',
    'Abemaciclib': 'Verzenio',
    'Tucatinib': 'Tukysa',
    'Pivekimab': 'Decnupaz',
    'Tebipenem': 'Utebzi',
    'Lunsotogene': 'Otarmeni',
    'Gedatolisib': 'Revtorpyk',
    'Datopotamab': 'Datroway',
    'Daraxonrasib': 'Rasonque',
    'Navepegritide': 'Yuviwel',
    'Povorcitinib': 'Povofortay',
    'Tividenofusp': 'Avlayah',
    'Sonrotoclax': 'Beqalzi',
    'Oveporexton': 'Orzeyful',
    'Semaglutide': 'Rybelsus',
}

BRAND_TO_INN = {v: k for k, v in DRUG_PAIRS.items()}


# ═══════════════════════════════════════════════════════════
# الشركات (تُحذف من المتن فقط)
# ═══════════════════════════════════════════════════════════
COMPANIES = [
    r'\bInsilico Medicine\b',
    r'\bInsilico\b',
    r'\bEli Lilly\b',
    r'\bMerck\b',
    r'\bPfizer\b',
    r'\bSanofi\b',
    r'\bEvotec\b',
    r'\bNovartis\b',
    r'\bAstraZeneca\b',
    r'\bGenentech\b',
    r'\bJohnson & Johnson\b',
    r'\bJ&J\b',
    r'\bAbbVie\b',
    r'\bAmgen\b',
    r'\bBiogen\b',
    r'\bRS Research\b',
    r'\bSynastra\b',
    r'\bEQL Pharma\b',
    r'\bAbdi Ibrahim\b',
    r'\bSothema\b',
]


# ═══════════════════════════════════════════════════════════
# PRESERVE — لا تُلمس أبدًا
# ═══════════════════════════════════════════════════════════
PRESERVE = [
    'Streamlit', 'GitHub', 'Hugging Face', 'Google Colab',
    'Python', 'RDKit', 'PubChem', 'NumPy', 'SciPy',
    'Plotly', 'scikit-learn', 'pytest', 'ruff',
    'FDA', 'EMA', 'CHMP', 'WHO', 'IDSA', 'CPIC',
    'Nature', 'Science', 'JAMA', 'NEJM', 'PNAS',
    'MIT License', 'AppImage', 'Electron', 'Stlite',
]


# ═══════════════════════════════════════════════════════════
# حماية PRESERVE
# ═══════════════════════════════════════════════════════════
def protect_preserved(content):
    tokens = {}
    for i, word in enumerate(PRESERVE):
        token = f"__PRES_{i:03d}__"
        tokens[token] = word
        content = content.replace(word, token)
    return content, tokens


def restore_preserved(content, tokens):
    for token, word in tokens.items():
        content = content.replace(token, word)
    return content


# ═══════════════════════════════════════════════════════════
# تنسيق الأدوية — الأول ذكر فقط
# ═══════════════════════════════════════════════════════════
def normalize_drug_mentions(content):
    """توحيد صيغة الأدوية: INN (Brand) في أول ذكر، INN فقط بعد ذلك."""
    changes = 0
    seen = set()

    # 1. عكس "Brand (INN)" → "INN (Brand)" — كل مرة
    for inn, brand in DRUG_PAIRS.items():
        pattern = rf'\b{brand}\s*\(\s*{inn}\s*\)'
        replacement = f'{inn} ({brand})'
        content, n = re.subn(pattern, replacement, content, flags=re.IGNORECASE)
        changes += n
        if n > 0:
            seen.add(inn)

    # 2. تصحيح "Brand (Brand)" → "INN (Brand)"
    for inn, brand in DRUG_PAIRS.items():
        pattern = rf'\b{brand}\s*\(\s*{brand}\s*\)'
        replacement = f'{inn} ({brand})'
        content, n = re.subn(pattern, replacement, content, flags=re.IGNORECASE)
        changes += n
        if n > 0:
            seen.add(inn)

    # 3. تصحيح "INN (INN)" → "INN"
    for inn in DRUG_PAIRS.keys():
        pattern = rf'\b{inn}\s*\(\s*{inn}\s*\)'
        content, n = re.subn(pattern, inn, content, flags=re.IGNORECASE)
        changes += n

    # 4. أول Brand → INN (Brand)
    for inn, brand in DRUG_PAIRS.items():
        if inn in seen:
            # ظهر بالفعل — حوّل كل Brand إلى INN
            content, n = re.subn(rf'\b{brand}\b', inn, content)
            changes += n
        else:
            # أول ذكر — حوّل Brand إلى INN (Brand)
            pattern = rf'(?<![(\[])\b{brand}\b(?!\s*\()'
            match = re.search(pattern, content)
            if match:
                content = (
                    content[:match.start()]
                    + f'{inn} ({brand})'
                    + content[match.end():]
                )
                changes += 1
                seen.add(inn)

    return content, changes


# ═══════════════════════════════════════════════════════════
# حذف الشركات من المتن فقط
# ═══════════════════════════════════════════════════════════
def remove_companies_from_body(content):
    """يحذف الشركات من المتن، يبقيها في المصادر."""
    lines = content.split('\n')
    result = []
    in_references = False

    reference_markers = [
        '## المصادر', '## المراجع', '## References',
        '## مصادر', '## مراجع',
    ]

    for line in lines:
        # كشف بداية قسم المصادر
        if any(marker in line for marker in reference_markers):
            in_references = True

        # كشف بداية قسم جديد (إنهاء المصادر)
        if in_references and line.startswith('## ') and not any(
            m in line for m in reference_markers
        ):
            in_references = False

        if in_references:
            result.append(line)
        else:
            # استبدال الشركات في المتن
            modified = line
            for pattern in COMPANIES:
                modified = re.sub(pattern, 'شركة', modified)
            result.append(modified)

    content = '\n'.join(result)

    # تنظيف التكرارات
    content = re.sub(r'شركة\s+شركة', 'شركة', content)
    content = re.sub(r'شركة\s+و\s+شركة', 'شركات', content)
    content = re.sub(r'(شركة)(?:\s*(?:و|,)\s*شركة)+', 'عدة شركات', content)

    return content


# ═══════════════════════════════════════════════════════════
# التطبيق الكامل على نص
# ═══════════════════════════════════════════════════════════
def normalize_text(content):
    tokens = {}

    # 1. حماية PRESERVE
    content, tokens = protect_preserved(content)

    # 2. تنسيق الأدوية
    content, drug_changes = normalize_drug_mentions(content)

    # 3. حذف الشركات من المتن
    before = content
    content = remove_companies_from_body(content)
    company_changes = 1 if content != before else 0

    # 4. استعادة PRESERVE
    content = restore_preserved(content, tokens)

    return content, {'drugs': drug_changes, 'companies': company_changes}


# ═══════════════════════════════════════════════════════════
# التعامل مع الملفات
# ═══════════════════════════════════════════════════════════
def process_file(path, dry_run=True):
    try:
        if path.suffix == '.ipynb':
            data = json.loads(path.read_text(encoding='utf-8'))
            total = {'drugs': 0, 'companies': 0}

            for cell in data.get('cells', []):
                if 'source' not in cell:
                    continue
                new_lines = []
                for line in cell['source']:
                    new_line, stats = normalize_text(line)
                    for k in total:
                        total[k] += stats[k]
                    new_lines.append(new_line)
                cell['source'] = new_lines

            changed = total['drugs'] + total['companies'] > 0
            if changed and not dry_run:
                path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=1),
                    encoding='utf-8'
                )
            return total

        else:
            content = path.read_text(encoding='utf-8')
            new_content, stats = normalize_text(content)
            changed = new_content != content

            if changed and not dry_run:
                path.write_text(new_content, encoding='utf-8')
            return stats

    except Exception as e:
        return {'error': str(e)}


# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()

    if not (args.dry_run or args.apply):
        print("❌ استخدم --dry-run أو --apply")
        return

    targets = [
        "README.md",
        "app.py",
        "CONTRIBUTING.md",
        "core/*.py",
        "tests/*.py",
        "docs/*.md",
        "download/*/*.ipynb",
        "download/*/*.md",
        "portfolio/*.html",
    ]

    exclude = [
        'node_modules', '.git', '__pycache__',
        '.venv', 'dist', 'build', 'scripts/',
    ]

    files = set()
    for pattern in targets:
        for path in Path('.').glob(pattern):
            if path.is_file() and not any(ex in str(path) for ex in exclude):
                files.add(path)

    print(f"🧹 {'[DRY RUN] ' if args.dry_run else ''}تنظيف {len(files)} ملف")
    print("═" * 60)

    total_drugs = 0
    total_companies = 0
    changed_files = []

    for path in sorted(files):
        stats = process_file(path, args.dry_run)
        if 'error' in stats:
            print(f"⚠️ {path}: {stats['error']}")
            continue
        if stats['drugs'] + stats['companies'] > 0:
            print(f"✅ {path} — أدوية: {stats['drugs']}, شركات: {stats['companies']}")
            total_drugs += stats['drugs']
            total_companies += stats['companies']
            changed_files.append(path)

    print("═" * 60)
    print(f"📊 المجموع:")
    print(f"   توحيد الأدوية: {total_drugs}")
    print(f"   حذف الشركات: {total_companies}")
    print(f"   ملفات متغيرة: {len(changed_files)}")
    print("═" * 60)


if __name__ == '__main__':
    main()
