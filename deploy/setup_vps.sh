#!/bin/bash
# ==============================================================================
# Script de Provisionamento e Setup Inicial do Hub de Desapego em VPS Ubuntu
# ==============================================================================
set -e

APP_DIR="/var/www/hub-desapego"
LOG_DIR="/var/log/gunicorn"

echo "=========================================="
echo "🚀 Iniciando Setup do Hub de Desapego..."
echo "=========================================="

# 1. Atualização do Sistema
echo "📦 Atualizando pacotes do sistema..."
sudo apt update && sudo apt upgrade -y

# 2. Instalação de dependências essenciais do sistema
echo "📦 Instalando Python, Nginx, Certbot e ferramentas essenciais..."
sudo apt install -y python3 python3-pip python3-venv python3-dev nginx certbot python3-certbot-nginx git curl ufw

# 3. Configuração do Firewall (UFW)
echo "🔒 Configurando Firewall UFW (OpenSSH, Nginx Full)..."
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw --force enable

# 4. Criação de diretórios e permissões
echo "📁 Configurando diretórios da aplicação..."
sudo mkdir -p $APP_DIR
sudo mkdir -p $LOG_DIR
sudo mkdir -p $APP_DIR/media
sudo mkdir -p $APP_DIR/staticfiles

sudo chown -R www-data:www-data $APP_DIR
sudo chown -R www-data:www-data $LOG_DIR
sudo chmod -R 775 $APP_DIR/media

# 5. Configuração do Ambiente Virtual Python
echo "🐍 Criando ambiente virtual Python e instalando dependências..."
cd $APP_DIR
sudo -u www-data python3 -m venv $APP_DIR/venv
sudo -u www-data $APP_DIR/venv/bin/pip install --upgrade pip
sudo -u www-data $APP_DIR/venv/bin/pip install -r $APP_DIR/requirements.txt

# 6. Criação do arquivo .env se não existir
if [ ! -f "$APP_DIR/.env" ]; then
    echo "⚠️ Arquivo .env não encontrado. Criando a partir de .env.example..."
    sudo -u www-data cp $APP_DIR/.env.example $APP_DIR/.env
    echo "❗ IMPORTANTE: Lembre-se de editar $APP_DIR/.env com suas chaves de API e SECRET_KEY real."
fi

# 7. Migrações e Coleta de Estáticos
echo "🗄️ Executando migrações do banco de dados SQLite..."
sudo -u www-data $APP_DIR/venv/bin/python manage.py migrate --noinput

echo "🎨 Coletando arquivos estáticos (CSS, JS, PWA)..."
sudo -u www-data $APP_DIR/venv/bin/python manage.py collectstatic --noinput

# 8. Configuração do Systemd para Gunicorn
echo "⚙️ Configurando serviço Systemd do Gunicorn..."
sudo cp $APP_DIR/deploy/gunicorn.service /etc/systemd/system/gunicorn_desapego.service
sudo systemctl daemon-reload
sudo systemctl enable gunicorn_desapego
sudo systemctl restart gunicorn_desapego

# 9. Configuração do Nginx
echo "🌐 Configurando VirtualHost do Nginx..."
sudo cp $APP_DIR/deploy/nginx.conf /etc/nginx/sites-available/hub-desapego
sudo ln -sf /etc/nginx/sites-available/hub-desapego /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

echo "=========================================================================="
echo "🎉 Setup concluído com sucesso!"
echo "➡️ Status do Gunicorn: sudo systemctl status gunicorn_desapego"
echo "➡️ Status do Nginx: sudo systemctl status nginx"
echo "➡️ Para habilitar SSL gratuito com Certbot, execute:"
echo "   sudo certbot --nginx -d seu_dominio.com.br"
echo "=========================================================================="
