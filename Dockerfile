# Pharma SDL v0.20.0 — صورة واحدة للمنصة: بوابة API + لوحة Streamlit
# (P16: الحاوية تعمل بمستخدم غير root — أي اختراق للحاوية يصطدم بصلاحيات محدودة)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PHARMA_SDL_DATA_DIR=/app/data

WORKDIR /app

# الاعتماديات أولاً — طبقة كاش مستقرة (تبني أسرع عند تغيير الكود فقط)
COPY requirements.txt ./
RUN pip install -r requirements.txt

# الكود والأصول المُتحقق منها (مستقبلات PDBQT + بيانات العرض)
COPY core/ ./core/
COPY pharma_sdl/ ./pharma_sdl/
COPY data/ ./data/
COPY app.py ./

# مستخدم تشغيل غير root + ملكية مجلد البيانات الدائم (الأحجام المركبة ترثها)
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# بوابة الـAPI-First — OpenAPI التفاعلي على /docs
CMD ["uvicorn", "pharma_sdl.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
