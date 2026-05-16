# OpenClaw Onboarding Runbook

This runbook connects OpenClaw to Codex, Telegram, and Slack for the AI Shorts Studio PM agent.

## 1. Install OpenClaw

Inside Ubuntu on WSL2:

```bash
npm install -g openclaw@latest
openclaw --version
```

## 2. Run onboarding

```bash
openclaw onboard --install-daemon
```

Follow the wizard:

- Sign in with ChatGPT OAuth.
- Pair the Telegram bot by sending the provided pair code in DM.
- Install the Slack app into the workspace using the generated install URL.

The wizard creates local runtime files under `~/.openclaw/`. Do not commit OAuth output, generated tokens, or user-specific runtime files.

## 3. Validate the gateway

```bash
openclaw doctor
```

Expected:

- OAuth is valid.
- Daemon is running.
- Telegram channel is paired.
- Slack channel is paired.
- Config validation passes.

If available, try automatic remediation:

```bash
openclaw doctor --fix
```

## 4. Install the repo-managed PM workspace

The PM workspace can be symlinked because it contains no private IDs or tokens.

From the repo root inside WSL2:

```bash
export AI_SHORTS_STUDIO_ROOT="$PWD"
printf 'export AI_SHORTS_STUDIO_ROOT="%s"\n' "$PWD" >> ~/.bashrc
mkdir -p ~/.openclaw
ln -sfn "$PWD/infra/openclaw/workspace" ~/.openclaw/workspace
```

## 5. Configure the local gateway config

The checked-in `infra/openclaw/openclaw.json` is a safe reference template with placeholder IDs. Do not overwrite the generated `~/.openclaw/openclaw.json` after onboarding, because the wizard writes channel fields that are required by the installed OpenClaw version.

Write real Telegram and Slack IDs only to the local runtime config:

```bash
openclaw config set channels.telegram.dmPolicy '"pairing"' --strict-json
openclaw config set channels.telegram.allowFrom '["OWNER_TELEGRAM_ID","FRIEND_TELEGRAM_ID"]' --strict-json
openclaw config set channels.slack.dmPolicy '"pairing"' --strict-json
openclaw config set channels.slack.allowFrom '["OWNER_SLACK_ID","FRIEND_SLACK_ID"]' --strict-json
```

Do not commit `~/.openclaw/openclaw.json`, OAuth output, generated tokens, or real user IDs unless the team explicitly decides those IDs are safe to share.

Reload the gateway:

```bash
openclaw gateway restart
openclaw doctor
```

## 6. Confirm schema compatibility

OpenClaw config fields may change between versions. Before relying on routing fields, inspect the installed schema:

```bash
openclaw config schema
openclaw config schema | grep -A5 -E 'agents|multiAgent|channels'
```

OpenClaw `2026.5.3-1` does not accept a top-level `multiAgent` key. Keep the checked-in config minimal and route channels with the installed `openclaw agents` and `openclaw channels` commands if the local gateway requires explicit routing.

## 7. Smoke tests

CLI:

```bash
openclaw agent --message "say hello in Korean"
```

Expected: Korean greeting.

Telegram:

```text
ping
```

Expected after Task 0.8 backend wiring: `pong`.

Slack:

```text
ping
```

Expected after Task 0.8 backend wiring: `pong`.

## 8. Troubleshooting

- If OAuth fails, rerun `codex auth login` and then `openclaw doctor`.
- If Telegram or Slack messages are ignored, verify pairing state and allowlist IDs.
- If `exec` is unavailable to the PM agent, verify `tools.profile` is set to `coding`.
- If the workspace symlink points to the wrong repo, remove it and recreate it from the repo root.
