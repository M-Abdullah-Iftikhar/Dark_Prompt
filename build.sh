#!/usr/bin/env bash
# Render build hook — installs deps, collects static files, runs migrations.
# Invoked once per deploy. Anything time-consuming should live here, NOT in
# the start command (which runs every container boot).
set -o errexit  # exit on error
set -o nounset
set -o pipefail

echo "==> Installing system toolchains (MinGW + NASM for the sandbox)"
# Render's build phase normally has root; falls back to sudo if not. If apt
# isn't available at all, we don't fail the deploy — the app degrades to
# "missing toolchain" notes for the Analyse/Compile buttons.
if command -v apt-get >/dev/null 2>&1; then
  (apt-get update -y \
    && apt-get install -y --no-install-recommends gcc-mingw-w64-x86-64 nasm) \
  || (sudo apt-get update -y \
    && sudo apt-get install -y --no-install-recommends gcc-mingw-w64-x86-64 nasm) \
  || echo "WARN: apt install failed — sandbox C/ASM analysis will be disabled"
else
  echo "WARN: apt-get not available — sandbox C/ASM analysis will be disabled"
fi

echo "==> Installing Python dependencies"
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Collecting static files"
python manage.py collectstatic --no-input

echo "==> Applying database migrations"
python manage.py migrate --no-input

echo "==> Build complete."
