#!/usr/bin/env bash
# Kalıcı yayın: GitHub + Render (ücretsiz)
set -euo pipefail
cd "$(dirname "$0")"

echo "=== 1) GitHub CLI kontrol ==="
if ! command -v gh >/dev/null 2>&1; then
  echo "gh yok — indiriliyor..."
  curl -fsSL -o /tmp/gh.tgz https://github.com/cli/cli/releases/download/v2.67.0/gh_2.67.0_linux_amd64.tar.gz
  tar -xzf /tmp/gh.tgz -C /tmp
  mkdir -p "$HOME/.local/bin"
  cp /tmp/gh_2.67.0_linux_amd64/bin/gh "$HOME/.local/bin/gh"
  export PATH="$HOME/.local/bin:$PATH"
fi

export PATH="$HOME/.local/bin:$PATH"

echo "=== 2) GitHub girişi ==="
if ! gh auth status >/dev/null 2>&1; then
  echo "Tarayıcıda GitHub'a giriş açılacak..."
  gh auth login -p https -w
fi

echo "=== 3) Repo oluştur + yükle ==="
if ! git remote get-url origin >/dev/null 2>&1; then
  gh repo create seferim --public --source=. --remote=origin --push
else
  BRANCH="$(git branch --show-current)"
  git push -u origin "$BRANCH"
fi

REPO_URL="$(gh repo view --json url -q .url)"
echo ""
echo "Repo hazır: $REPO_URL"
echo ""
echo "=== 4) Render (kalıcı site) ==="
echo "1) https://dashboard.render.com/select-repo?type=blueprint"
echo "   veya https://render.com → Sign up with GitHub"
echo "2) Bu repoyu seç: seferim"
echo "3) Blueprint / Web Service oluştur → Deploy"
echo "4) Biten adres: https://seferim-xxxx.onrender.com"
echo ""
echo "Render açılıyor..."
xdg-open "https://dashboard.render.com/select-repo?type=web" 2>/dev/null || true
echo "Bitti. Render'daki canlı linki buraya yapıştır."
