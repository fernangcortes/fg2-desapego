"""
Configuração do Gunicorn para o Hub de Desapego Inteligente em VPS Linux.
"""
import multiprocessing

# Endereço de Bind (Socket Unix para máxima performance com Nginx)
bind = "unix:/run/gunicorn_desapego.sock"

# Quantidade de Workers recomendada: (2 x CPUs) + 1
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"

# Timeouts (30 segundos para dar tempo às chamadas de IA se síncronas)
timeout = 60
keepalive = 5

# Logs
accesslog = "/var/log/gunicorn/desapego_access.log"
errorlog = "/var/log/gunicorn/desapego_error.log"
loglevel = "info"

# Process Naming
proc_name = "hub_desapego"
daemon = False
