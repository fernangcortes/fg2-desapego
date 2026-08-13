#!/bin/bash
# ==============================================================================
# Script de Atualização Rápida / Deploy Contínuo no VPS
# ==============================================================================
set -e

APP_DIR="/var/www/hub-desapego"

echo "🔄 Atualizando código do repositório..."
cd $APP_DIR
sudo -u www-data git pull origin main

echo "📦 Atualizando dependências Python..."
sudo -u www-data $APP_DIR/venv/bin/pip install -r requirements.txt

echo "🗄️ Aplicando novas migrações..."
sudo -u www-data $APP_DIR/venv/bin/python manage.py migrate --noinput

echo "🎨 Coletando arquivos estáticos..."
sudo -u www-data $APP_DIR/venv/bin/python manage.py collectstatic --noinput

echo "♻️ Recarregando Gunicorn..."
sudo systemctl restart gunicorn_desapego

echo "✅ Deploy concluído com sucesso em $(date)!"
