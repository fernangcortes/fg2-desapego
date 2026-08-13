#!/bin/bash
# ==============================================================================
# Script de Backup Automático do Banco SQLite e Fotos de Mídia
# ==============================================================================
set -e

APP_DIR="/var/www/hub-desapego"
BACKUP_DIR="/var/backups/hub-desapego"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

mkdir -p $BACKUP_DIR

echo "📦 Criando backup do banco SQLite e fotos em $BACKUP_DIR..."

# Backup SQLite em arquivo consistente
sqlite3 $APP_DIR/db.sqlite3 ".backup '$BACKUP_DIR/db_backup_$TIMESTAMP.sqlite3'"

# Backup compactado das fotos de mídia
tar -czf "$BACKUP_DIR/media_backup_$TIMESTAMP.tar.gz" -C $APP_DIR media

# Mantém apenas os backups dos últimos 30 dias para economizar disco
find $BACKUP_DIR -type f -mtime +30 -name "*backup*" -delete

echo "✅ Backup finalizado com sucesso: db_backup_$TIMESTAMP.sqlite3 e media_backup_$TIMESTAMP.tar.gz"
