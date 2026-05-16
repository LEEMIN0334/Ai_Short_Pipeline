# WSL2 Setup Runbook

This runbook prepares the gaming PC WSL2 environment for AI Shorts Studio development and runtime operations.

## 1. Install WSL2

Run PowerShell as Administrator on Windows:

```powershell
wsl --install -d Ubuntu-22.04
```

Restart Windows if prompted, then open Ubuntu and create the Linux user account.

## 2. Install the base toolchain

Inside Ubuntu:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git build-essential ffmpeg fontconfig fonts-noto-cjk
```

Or run the repo script:

```bash
cd ~/Ai_Short_Pipeline
chmod +x infra/wsl2-setup.sh
./infra/wsl2-setup.sh
```

## 3. Verify Node 24

The setup script installs Node through nvm. If installing manually:

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc
nvm install 24
nvm alias default 24
node --version
```

Expected: `v24.x.x`.

## 4. Verify Python 3.12 and uv

Manual installation:

```bash
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.12 python3.12-venv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
python3.12 --version
uv --version
```

## 5. Install and authenticate Codex CLI

```bash
npm install -g @openai/codex
codex --version
codex auth login
```

The OAuth flow stores the local token under `~/.codex/auth.json`. Do not commit that file.

## 6. Clone the repo inside WSL2

Prefer SSH if the machine has a GitHub SSH key:

```bash
cd ~
git clone git@github.com:LEEMIN0334/Ai_Short_Pipeline.git
cd Ai_Short_Pipeline
git switch CJLee
```

HTTPS fallback:

```bash
git clone https://github.com/LEEMIN0334/Ai_Short_Pipeline.git
cd Ai_Short_Pipeline
git switch CJLee
```

## 7. Project smoke check

Once the Python workspace exists:

```bash
cd packages/core
uv sync --extra dev
uv run pytest tests/test_smoke.py -v
```

Expected: smoke test passes. If `packages/core` does not exist yet, skip this step until the backend scaffold lands.

## 8. Troubleshooting

- If `uv` is missing after installation, run `source ~/.bashrc` or call `~/.local/bin/uv`.
- If `node` is missing, run `source ~/.bashrc` and then `nvm use 24`.
- If Korean fonts render incorrectly in FFmpeg output, confirm `fonts-noto-cjk` is installed and run `fc-cache -fv`.
