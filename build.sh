#!/usr/bin/env bash
# Script de build para Render (se ejecuta en cada deploy)

set -o errexit  # Frena si hay errores

pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate