# Tailscale Mesh Setup Runbook

Use Tailscale to expose the gaming PC services privately to the owner and development partner. Do not expose the dashboard publicly during MVP.

## 1. Create or join the tailnet

Sign in at https://tailscale.com with the team account or the owner's personal account.

Use the free personal plan unless the project later needs organization-level controls.

## 2. Install Tailscale on the gaming PC

Inside Ubuntu on WSL2:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Complete the browser auth flow.

## 3. Install Tailscale on client devices

Install Tailscale on:

- Owner laptop
- Development partner laptop
- Owner phone
- Development partner phone, if mobile approval will be tested

Sign in to the same tailnet.

## 4. Confirm device status

On the gaming PC:

```bash
tailscale status
tailscale ip -4
```

Record the gaming PC hostname. Example: `shorts-studio`.

## 5. Enable or verify MagicDNS

In the Tailscale admin console:

1. Open DNS settings.
2. Ensure MagicDNS is enabled.
3. Confirm the gaming PC has a stable, recognizable machine name.

## 6. Connectivity tests

From another device in the tailnet:

```bash
ping shorts-studio
```

If the dashboard is running later:

```text
http://shorts-studio:3000
```

Before the dashboard exists, a connection refusal is acceptable. DNS resolution and routing are the important checks.

## 7. Operating rules

- Keep the dashboard bound to the private network during MVP.
- Do not publish dashboard ports through public tunnels unless a separate security review approves it.
- Remove lost devices from the tailnet immediately.
- Keep owner and development partner devices clearly named in the admin console.

## 8. Troubleshooting

- If MagicDNS fails, use `tailscale ip -4` and test the private IP directly.
- If WSL2 cannot accept inbound traffic, test from Windows host first and then review WSL networking mode.
- If login state expires, rerun `sudo tailscale up`.
