# Pinned to bookworm (Debian 12, GCC 12) because UASM's source has
# -Wimplicit-function-declaration warnings that GCC 14 (Debian 13/trixie)
# now treats as hard errors. GCC 12 keeps them as warnings so the build
# completes. UASM still links fine — `strupr` is provided by its Unix
# portability layer in another .c file.
FROM python:3.12-slim-bookworm

# Install C/ASM toolchains needed by the sandbox Analyse/Compile features.
# Root is available here (image build time) — no sudo needed, unlike the
# native Python runtime on Render where the filesystem is read-only.
#   gcc                  — native Linux C compiler
#   gcc-mingw-w64-x86-64 — cross-compiler for Windows-targeted C (#include <windows.h> etc.)
#   nasm                 — assembler for NASM-style x86/x86-64 ASM
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        gcc-mingw-w64-x86-64 \
        nasm \
    && rm -rf /var/lib/apt/lists/*

# UASM (MASM-compatible assembler) is best-effort. Upstream HEAD currently
# has Windows-only includes (e.g. dbgcv.c → <direct.h>) that break the
# Linux build, so we don't fail the image if it doesn't compile — the app's
# `_analyse_assembly` already soft-degrades on missing MASM with a regex
# sanity-check + warning. When upstream is buildable again, this layer will
# silently start producing /usr/local/bin/uasm and the app will pick it up.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git make g++ \
    && rm -rf /var/lib/apt/lists/* \
    && ( \
        git clone --depth 1 https://github.com/Terraspace/UASM.git /tmp/uasm \
        && make -C /tmp/uasm -f gccLinux64.mak \
            EXTRA_C_FLAGS="-Wno-error=implicit-function-declaration" \
        && cp /tmp/uasm/GccUnixR/uasm /usr/local/bin/uasm \
        && echo "INFO: UASM installed at /usr/local/bin/uasm" \
        || echo "WARN: UASM build failed — MASM-style ASM analysis will degrade to a regex sanity check" \
    ) \
    && rm -rf /tmp/uasm \
    && apt-get purge -y --auto-remove git make g++

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
