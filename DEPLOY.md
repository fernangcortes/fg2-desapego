# 🚀 Guia de Deploy em VPS Linux (Ubuntu) - Hub de Desapego Inteligente

Este guia detalha o processo completo de instalação e deploy em produção em qualquer VPS Linux (Ubuntu 22.04 LTS ou 24.04 LTS) utilizando **Python 3.12**, **Gunicorn**, **Nginx**, **Systemd** e **SQLite**.

---

## 1. Requisitos do Servidor VPS
- **VPS Recomendada:** Ubuntu 22.04 ou 24.04 LTS (1 GB de RAM e 1 vCPU é suficiente para ~300 itens). Exemplos: Hetzner (€3.5/mês), DigitalOcean ($4-6/mês) ou Linode.
- **Acesso:** SSH com privilégios de `sudo`.
- **Domínio apontado:** Registros DNS tipo `A` apontando seu domínio (ex: `desapego.meudominio.com.br`) para o IP público do VPS.

---

## 2. Passo a Passo de Instalação (Primeira Vez)

### Passo 1: Conectar no Servidor via SSH
```bash
ssh root@SEU_IP_DO_VPS
```

### Passo 2: Clonar o Repositório
Crie a pasta de destino `/var/www/hub-desapego` e clone o projeto:
```bash
sudo mkdir -p /var/www/hub-desapego
sudo chown -R $USER:$USER /var/www/hub-desapego
git clone https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git /var/www/hub-desapego
cd /var/www/hub-desapego
```

### Passo 3: Tornar os scripts executáveis e Rodar o Setup Automatizado
```bash
chmod +x deploy/*.sh
sudo ./deploy/setup_vps.sh
```

O script cuidará de:
1. Atualizar o sistema operacional.
2. Instalar Python 3, pip, venv, Nginx, Certbot e UFW.
3. Configurar firewall liberando portas 22 (SSH), 80 (HTTP) e 443 (HTTPS).
4. Criar o ambiente virtual e instalar todos os pacotes.
5. Aplicar migrações do banco de dados SQLite.
6. Coletar arquivos estáticos (`collectstatic`).
7. Ativar e iniciar o serviço **Systemd** (`gunicorn_desapego`) e o **Nginx**.

---

## 3. Configuração do `.env` e Chaves de API em Produção

Edite o arquivo `.env` na raiz do projeto:
```bash
sudo nano /var/www/hub-desapego/.env
```

Preencha com suas configurações reais de produção:
```ini
# Configurações do Django
DEBUG=False
SECRET_KEY=gere-uma-chave-longa-e-secreta-aqui-123456!@#$%^
ALLOWED_HOSTS=seudominio.com.br,www.seudominio.com.br,SEU_IP_VPS

# 1. Visão Computacional (Obtenha em https://aistudio.google.com/ ou https://console.groq.com/)
GEMINI_API_KEY=AIzaSy...
GROQ_API_KEY=gsk_...

# 2. Pesquisa de Mercado de Preços (Obtenha em https://tavily.com/ ou https://serper.dev/)
TAVILY_API_KEY=tvly-...
SERPER_API_KEY=...

# 3. Copywriting (Obtenha em https://platform.deepseek.com/)
DEEPSEEK_API_KEY=sk-...

# 4. Notificações no Telegram (Opcional - Crie um bot no @BotFather)
TELEGRAM_BOT_TOKEN=123456789:ABCdef...
TELEGRAM_CHAT_ID=987654321
```

Após salvar (`Ctrl + O`, `Enter`, `Ctrl + X`), reinicie o serviço para carregar as novas variáveis:
```bash
sudo systemctl restart gunicorn_desapego
```

---

## 4. Configurar Domínio e SSL/HTTPS Gratuito (Let's Encrypt)

1. Edite o arquivo do Nginx substituindo `seudominio.com.br` pelo seu domínio real:
   ```bash
   sudo nano /etc/nginx/sites-available/hub-desapego
   ```
2. Teste e recarregue o Nginx:
   ```bash
   sudo nginx -t
   sudo systemctl reload nginx
   ```
3. Emita o certificado SSL HTTPS automático via Certbot:
   ```bash
   sudo certbot --nginx -d seudominio.com.br -d www.seudominio.com.br
   ```

O Certbot configurará a renovação automática a cada 90 dias via cron.

---

## 5. Criação do Superusuário Inicial no VPS

Para acessar o painel administrativo (`/admin/`):
```bash
sudo -u www-data /var/www/hub-desapego/venv/bin/python /var/www/hub-desapego/manage.py createsuperuser
```

---

## 6. Rotina de Atualizações Contínuas (Deploy Rápido)

Sempre que fizer alterações no código e enviar para o GitHub, basta rodar no VPS:
```bash
cd /var/www/hub-desapego
sudo ./deploy/deploy.sh
```

---

## 7. Rotina Automática de Backups Diários (SQLite + Mídia)

Para rodar o backup diariamente às 03:00 da manhã:
```bash
sudo crontab -e
```
Adicione a seguinte linha no final do arquivo:
```cron
0 3 * * * /var/www/hub-desapego/deploy/backup_sqlite.sh > /var/log/desapego_backup.log 2>&1
```

Os backups serão salvos em `/var/backups/hub-desapego/` com rotação automática de 30 dias.

---

## 8. Comandos Úteis de Diagnóstico

- **Ver status da aplicação:**
  ```bash
  sudo systemctl status gunicorn_desapego
  ```
- **Ver logs da aplicação em tempo real:**
  ```bash
  sudo journalctl -u gunicorn_desapego -f
  ```
- **Ver logs do Gunicorn:**
  ```bash
  tail -f /var/log/gunicorn/desapego_error.log
  ```
- **Ver logs do Nginx:**
  ```bash
  tail -f /var/log/nginx/desapego_error.log
  ```
- **Reiniciar todos os serviços:**
  ```bash
  sudo systemctl restart gunicorn_desapego && sudo systemctl restart nginx
  ```
