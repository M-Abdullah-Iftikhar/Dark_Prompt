FROM python:3.12-slim

# Install C/ASM toolchains needed by the sandbox Analyse/Compile features.
# Root is available here (image build time) — no sudo needed, unlike the
# native Python runtime on Render where the filesystem is read-only.
#   gcc                  — native Linux C compiler
#   gcc-mingw-w64-x86-64 — cross-compiler for Windows-targeted C (#include <windows.h> etc.)
#   nasm                 — assembler for x86/x86-64 ASM
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        gcc-mingw-w64-x86-64 \
        nasm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps before copying the rest of the code so Docker can cache
# this layer and skip it on rebuilds where only source files changed.
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Collect static files at image-build time (no DB needed).
# settings.py's _is_build_phase guard disables SECRET_KEY / ALLOWED_HOSTS
# checks for management commands, so this works without any env vars set.
RUN DJANGO_DEBUG=0 python manage.py collectstatic --no-input

EXPOSE 10000

# Migrations run at container startup — they need the live DATABASE_URL
# which Render only injects at runtime, not during image build.
CMD ["sh", "-c", "python manage.py migrate --no-input && gunicorn darkprompt.wsgi:application --bind 0.0.0.0:${PORT:-10000} --workers 2 --timeout 300"]
