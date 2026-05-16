#!/usr/bin/env bash
set -euo pipefail

NODE_VERSION="${NODE_VERSION:-24}"
NVM_VERSION="${NVM_VERSION:-v0.39.7}"

log() {
  printf '\n==> %s\n' "$1"
}

if [[ "$(uname -s)" != "Linux" ]]; then
  printf 'This setup script is intended for Ubuntu on WSL2.\n' >&2
  exit 1
fi

log "Installing Ubuntu system dependencies"
export DEBIAN_FRONTEND=noninteractive
sudo apt update
sudo apt install -y \
  build-essential \
  ca-certificates \
  curl \
  ffmpeg \
  fontconfig \
  fonts-noto-cjk \
  git \
  gnupg \
  lsb-release \
  software-properties-common

log "Installing Node ${NODE_VERSION} via nvm"
if [[ ! -d "$HOME/.nvm" ]]; then
  curl -o- "https://raw.githubusercontent.com/nvm-sh/nvm/${NVM_VERSION}/install.sh" | bash
fi

# shellcheck source=/dev/null
. "$HOME/.nvm/nvm.sh"
nvm install "$NODE_VERSION"
nvm alias default "$NODE_VERSION"
node --version
npm --version

log "Installing Python 3.12 and uv"
if ! command -v python3.12 >/dev/null 2>&1; then
  sudo add-apt-repository -y ppa:deadsnakes/ppa
  sudo apt update
  sudo apt install -y python3.12 python3.12-venv
fi

python3.12 --version

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

if command -v uv >/dev/null 2>&1; then
  uv --version
elif [[ -x "$HOME/.local/bin/uv" ]]; then
  "$HOME/.local/bin/uv" --version
else
  printf 'uv was installed, but it is not on PATH yet. Reload the shell and run: uv --version\n'
fi

log "Installing Codex CLI"
npm install -g @openai/codex
codex --version

cat <<'NEXT_STEPS'

Setup complete.

Next manual steps:
1. Reload the shell:
   source ~/.bashrc
2. Authenticate Codex with ChatGPT OAuth:
   codex auth login
3. Clone the repository inside WSL2 and run the project smoke tests.
NEXT_STEPS
