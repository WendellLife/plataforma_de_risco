#!/usr/bin/env bash
# Build do Render. Migração ANTES de a nova versão da aplicação subir.
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --noinput
python manage.py migrate --noinput

# Popula a biblioteca NR-12 e os dados de demonstração no primeiro deploy.
# Remova esta linha quando o ambiente passar a receber dado real de cliente.
python manage.py seed_demo
