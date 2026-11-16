#!/data/data/com.termux/files/usr/bin/bash
# YAi'yi doğrudan telefonda (Termux) çalıştırır. Kart, sunucu veya Tailscale gerekmez.
# Kullanım (Termux içinde):
#   pkg install -y git && git clone -b ccr-bea6ae63-isiiit https://github.com/yunuslu-77/YunUSlu.git ~/yai
#   bash ~/yai/deploy/termux_install.sh
set -e
cd "$(dirname "$0")/.."
DIR="$(pwd)"

echo "📦 Termux paketleri kuruluyor (birkaç dakika sürebilir)..."
pkg update -y
pkg install -y python git ffmpeg termux-api rust binutils python-cryptography libxml2 libxslt

echo "🐍 Python kütüphaneleri kuruluyor (pydantic derlenirken 10-20 dk sürebilir, telefonu şarja tak)..."
export ANDROID_API_LEVEL="$(getprop ro.build.version.sdk)"
export CARGO_BUILD_JOBS=2
pip install --upgrade pip wheel
pip install -r requirements-termux.txt

if [ ! -f .env ]; then
  cp .env.example .env
  DT=$(python -c "import secrets;print(secrets.token_urlsafe(32))")
  PT=$(python -c "import secrets;print(secrets.token_urlsafe(32))")
  sed -i "s|^DASHBOARD_TOKEN=.*|DASHBOARD_TOKEN=$DT|; s|^PHONE_TOKEN=.*|PHONE_TOKEN=$PT|" .env
  # Her şey aynı telefonda: sadece telefonun içinden erişilebilsin
  sed -i "s|^DASHBOARD_HOST=.*|DASHBOARD_HOST=127.0.0.1|; s|^PUBLIC_URL=.*|PUBLIC_URL=http://127.0.0.1:8080|" .env
  chmod 600 .env
fi

cat > ~/yai-start.sh <<RUN
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
cd "$DIR"
pkill -f "python -m bot.main" 2>/dev/null || true
nohup python -m bot.main >> "$DIR/data/yai.log" 2>&1 &
echo "✅ YAi başladı. Log: tail -f $DIR/data/yai.log"
RUN
chmod +x ~/yai-start.sh
mkdir -p ~/.termux/boot "$DIR/data"
cp ~/yai-start.sh ~/.termux/boot/yai.sh

cat > ~/yai-backup.sh <<RUN
#!/data/data/com.termux/files/usr/bin/bash
# Hafızayı ve ayarları telefonun Download klasörüne yedekler (önce bir kez: termux-setup-storage)
mkdir -p ~/storage/downloads/YAi-yedek
cp "$DIR/data/yai.db" ~/storage/downloads/YAi-yedek/yai-\$(date +%F).db
cp "$DIR/.env" ~/storage/downloads/YAi-yedek/env-\$(date +%F).txt
[ -f "$DIR/data/google_token.json" ] && cp "$DIR/data/google_token.json" ~/storage/downloads/YAi-yedek/
echo "✅ Yedek: Download/YAi-yedek"
RUN
chmod +x ~/yai-backup.sh

echo ""
echo "✅ Kurulum bitti. Şimdi:"
echo "  1) nano $DIR/.env   → GEMINI_API_KEY ve TELEGRAM_TOKEN satırlarını doldur (Ctrl+O, Enter, Ctrl+X)"
echo "  2) ~/yai-start.sh   → botu başlat"
echo "  3) Telegram'da botuna /start yaz → verdiği ID'yi .env'de TELEGRAM_OWNER_ID= satırına yaz → ~/yai-start.sh"
echo "  4) Telegram'da /uygulama → kodu YAi uygulamasına yapıştır"
echo "  5) Ayarlar > Uygulamalar > Termux ve Termux:Boot > Pil > Kısıtlama yok"
