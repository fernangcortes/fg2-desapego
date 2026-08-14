"""
Configuração do Gunicorn para o Hub de Desapego Inteligente em VPS Linux.
"""
import multiprocessing

# Endereço de Bind (Socket Unix em /tmp para permissão universal Nginx/Gunicorn)
bind = "unix:/tmp/gunicorn_desapego.sock"

# Quantidade de Workers recomendada: (2 x CPUs) + 1
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"

# Timeouts (180 segundos para dar tempo às chamadas completas da pipeline de IA)
timeout = 180
keepalive = 5

# Logs
accesslog = "/var/log/gunicorn/desapego_access.log"
errorlog = "/var/log/gunicorn/desapego_error.log"
loglevel = "info"

# Process Naming
proc_name = "hub_desapego"
daemon = False
