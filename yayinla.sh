#!/usr/bin/env bash
# Geçici herkese açık link (bilgisayar açıkken çalışır)
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p bin

if [[ ! -x bin/cloudflared ]]; then
  echo "cloudflared indiriliyor..."
  curl -fsSL -o bin/cloudflared \
    https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
  chmod +x bin/cloudflared
fi

if ! curl -fsS -m 2 http://127.0.0.1:5050/ >/dev/null 2>&1; then
  echo "Önce başka bir terminalde sunucuyu başlat:"
  echo "  ./baslat.sh"
  exit 1
fi

echo ""
echo "Herkese açık link birazdan görünecek (trycloudflare.com)."
echo "Bu terminal açık kaldığı sürece site dışarıdan erişilir."
echo ""
exec ./bin/cloudflared tunnel --url http://127.0.0.1:5050
