#!/usr/bin/env bash
# data/ klasörünü (hafıza, ayarlar, Google bağlantısı) yedekler. Cron: 0 4 * * * bash ~/yai/deploy/backup.sh
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$DIR/backups"
sqlite3 "$DIR/data/yai.db" ".backup '$DIR/backups/yai-$(date +%F).db'" 2>/dev/null || cp "$DIR/data/yai.db" "$DIR/backups/yai-$(date +%F).db"
ls -1t "$DIR"/backups/yai-*.db | tail -n +15 | xargs -r rm
echo "✅ Yedek alındı"
