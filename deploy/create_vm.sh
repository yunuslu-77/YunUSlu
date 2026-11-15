#!/usr/bin/env bash
# Google Cloud'da ÜCRETSİZ (Always Free) e2-micro sanal makine oluşturur.
# Google Cloud Shell'de (console.cloud.google.com → sağ üstte >_ simgesi) çalıştır:
#   bash create_vm.sh PROJE_ID
set -euo pipefail
PROJECT="${1:?Kullanım: bash create_vm.sh PROJE_ID}"
ZONE="${ZONE:-us-central1-a}"   # Ücretsiz bölgeler: us-west1, us-central1, us-east1
NAME="${NAME:-yai}"

gcloud config set project "$PROJECT"
gcloud services enable compute.googleapis.com gmail.googleapis.com calendar-json.googleapis.com \
  drive.googleapis.com docs.googleapis.com sheets.googleapis.com generativelanguage.googleapis.com

gcloud compute instances create "$NAME" \
  --zone="$ZONE" \
  --machine-type=e2-micro \
  --image-family=debian-12 --image-project=debian-cloud \
  --boot-disk-size=30GB --boot-disk-type=pd-standard \
  --tags=yai

echo ""
echo "✅ Sanal makine hazır. Bağlanmak için:"
echo "   gcloud compute ssh $NAME --zone=$ZONE"
echo "Sonra makinede:"
echo "   git clone https://github.com/yunuslu-77/YunUSlu.git yai && cd yai && bash deploy/install.sh"
