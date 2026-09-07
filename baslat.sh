#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PATH="/home/zgebkr/anaconda3/bin:$PATH"
echo "Seferim başlıyor → http://127.0.0.1:5050"
exec python app.py
