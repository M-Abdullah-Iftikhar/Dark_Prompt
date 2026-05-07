#!/usr/bin/env bash
# Render build hook — installs deps, collects static files, runs migrations.
# Invoked once per deploy. Anything time-consuming should live here, NOT in
# the start command (which runs every container boot).
set -o errexit  # exit on error
set -o nounset
set -o pipefail

echo "==> Installing Python dependencies"
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Collecting static files"
python manage.py collectstatic --no-input

echo "==> Applying database migrations"
python manage.py migrate --no-input

echo "==> Build complete."
