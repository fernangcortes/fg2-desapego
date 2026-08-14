#!/bin/bash
# ==============================================================================
# Script de Atualização Rápida / Deploy Contínuo no VPS
# ==============================================================================
set -e

APP_DIR="/var/www/hub-desapego"

echo "🔄 Atualizando código do repositório..."
cd $APP_DIR
git pull origin main

echo "📦 Atualizando dependências Python..."
$APP_DIR/venv/bin/pip install -r requirements.txt

echo "🗄️ Aplicando novas migrações..."
$APP_DIR/venv/bin/python manage.py migrate --noinput

echo "🎨 Coletando arquivos estáticos..."
$APP_DIR/venv/bin/python manage.py collectstatic --noinput

echo "🔒 Ajustando permissões para www-data..."
chown -R www-data:www-data $APP_DIR/media $APP_DIR/staticfiles $APP_DIR/db.sqlite3 2>/dev/null || true

echo "🌐 Atualizando e recarregando Nginx..."
if [ -f /etc/nginx/sites-available/hub-desapego ]; then
    cp $APP_DIR/deploy/nginx.conf /etc/nginx/sites-available/hub-desapego
    nginx -t && systemctl reload nginx
fi

echo "♻️ Recarregando Gunicorn..."
systemctl restart gunicorn_desapego

echo "✅ Deploy concluído com sucesso em $(date)!"
