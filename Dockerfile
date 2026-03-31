# ─── Stage 1: builder ──────────────────────────────────────────────────────
# Устанавливает зависимости в виртуальное окружение.
# Нужны build-time инструменты (gcc, libpq-dev), которые в runtime не нужны.
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ─── Stage 2: runtime ──────────────────────────────────────────────────────
# Минимальный образ: только runtime-библиотеки + скопированный venv из builder.
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# psycopg2 (libpq5) + WeasyPrint (Cairo, Pango, GDK-Pixbuf, шрифты)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi8 \
    shared-mime-info \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /venv /venv
ENV PATH="/venv/bin:$PATH"

COPY . .

RUN python manage.py collectstatic --noinput --settings=config.settings.prod || true

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
