#!/data/data/com.termux/files/usr/bin/bash
# YAi telefon köprüsü kurulumu (Termux içinde çalıştır):
#   curl -fsSL <ham-dosya-adresi>/install.sh | bash     veya    bash install.sh
set -e
echo "📦 Paketler kuruluyor..."
pkg update -y
pkg install -y python termux-api android-tools
pip install --upgrade websockets

mkdir -p ~/yai ~/.termux/boot
SRC="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
if [ -f "$SRC/bridge.py" ]; then
  cp "$SRC/bridge.py" ~/yai/bridge.py
else
  echo "⚠️ bridge.py bu klasörde yok. ~/yai/bridge.py dosyasını elle kopyala."
fi

if [ ! -f ~/yai/bridge.env ]; then
  read -rp "Sunucu adresi (ör. 100.101.102.103): " HOST
  read -rp "PHONE_TOKEN (sunucudaki .env ile aynı): " TOKEN
  read -rp "Cihaz adı [Telefonum]: " NAME
  cat > ~/yai/bridge.env <<CONF
SERVER_URL=ws://${HOST}:8080/phone/ws
PHONE_TOKEN=${TOKEN}
DEVICE_NAME=${NAME:-Telefonum}
FORWARD_SMS=1
ADB_SERIAL=
CONF
  chmod 600 ~/yai/bridge.env
fi

cat > ~/yai/start.sh <<'RUN'
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
cd ~/yai
pkill -f "python.*bridge.py" 2>/dev/null || true
nohup python bridge.py >> ~/yai/bridge.log 2>&1 &
echo "✅ YAi köprüsü başladı (log: ~/yai/bridge.log)"
RUN
chmod +x ~/yai/start.sh
cp ~/yai/start.sh ~/.termux/boot/yai.sh

echo ""
echo "✅ Kurulum bitti. Şimdi:"
echo "  1) Termux:API uygulamasına izinleri ver (SMS, Rehber, Konum, Kamera, Telefon)."
echo "  2) Ayarlar > Bildirim erişimi > Termux:API'yi aç (bildirim okuma için)."
echo "  3) Termux'a 'Diğer uygulamaların üzerinde göster' iznini ver (uygulama/alarm açma için)."
echo "  4) Pil optimizasyonundan Termux, Termux:API ve Termux:Boot'u çıkar."
echo "  5) Başlat:  ~/yai/start.sh"
