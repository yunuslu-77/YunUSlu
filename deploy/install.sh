#!/usr/bin/env bash
# YAi'yi sunucuya (Debian/Ubuntu) kurar ve 7/24 çalışan servis yapar.
# Repo klasöründe çalıştır:  bash deploy/install.sh
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="$(whoami)"
cd "$DIR"

echo "📦 Sistem paketleri..."
sudo apt-get update -y
sudo apt-get install -y python3 python3-venv python3-pip ffmpeg git curl

# e2-micro'da 1 GB RAM var; tarayıcı için 2 GB takas alanı ekle
if ! swapon --show | grep -q /swapfile; then
  echo "💾 Takas alanı (swap) ekleniyor..."
  sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
  sudo mkswap /swapfile && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

echo "🐍 Python ortamı..."
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
echo "🌐 Tarayıcı (Chromium)..."
.venv/bin/python -m playwright install --with-deps chromium

if [ ! -f .env ]; then
  cp .env.example .env
  DT=$(python3 -c "import secrets;print(secrets.token_urlsafe(32))")
  PT=$(python3 -c "import secrets;print(secrets.token_urlsafe(32))")
  sed -i "s|^DASHBOARD_TOKEN=.*|DASHBOARD_TOKEN=$DT|; s|^PHONE_TOKEN=.*|PHONE_TOKEN=$PT|" .env
  chmod 600 .env
  echo "📝 .env oluşturuldu. GEMINI_API_KEY ve TELEGRAM_TOKEN değerlerini yaz:  nano $DIR/.env"
fi

echo "🔒 Tailscale (telefon ve panel için özel, şifreli ağ)..."
if ! command -v tailscale >/dev/null; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi
echo "   → 'sudo tailscale up' çalıştırıp çıkan bağlantıyla giriş yap."

echo "⚙️ Servis kuruluyor..."
sed "s|__DIR__|$DIR|g; s|__USER__|$USER_NAME|g" deploy/yai.service | sudo tee /etc/systemd/system/yai.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable yai

echo ""
echo "✅ Kurulum tamam. Sıradakiler:"
echo "  1) nano .env              (GEMINI_API_KEY, TELEGRAM_TOKEN)"
echo "  2) sudo tailscale up      (giriş yap) → IP'n: tailscale ip -4"
echo "  3) sudo systemctl start yai"
echo "  4) Telegram'da bota /start yaz, verdiği ID'yi .env'e TELEGRAM_OWNER_ID olarak ekle"
echo "  5) sudo systemctl restart yai"
echo "Loglar: journalctl -u yai -f"
