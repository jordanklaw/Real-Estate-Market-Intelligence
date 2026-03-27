# Linux IdeaPad Setup Guide: Headless MCP + Ollama Server

## Architecture

```
MacBook (you sit here)              IdeaPad (headless compute box)
┌─────────────────────┐             ┌──────────────────────────┐
│  Claude Desktop     │  SSH tunnel │  Ollama (qwen3:14b)      │
│  Claude Code        │◄───────────►│  Python MCP server       │
│  Cursor / etc.      │             │  Cron daily brief        │
└─────────────────────┘             └──────────────────────────┘
```

Your Mac has the MCP clients (Claude Desktop, Claude Code, etc.). The IdeaPad is just a compute box running Ollama and the Python server. No accounts, no browser, no GUI needed on the Linux side.

---

## Step 1: Install System Prerequisites (on IdeaPad)

SSH into the IdeaPad from your Mac (or do this during initial physical setup):

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip git curl openssh-server
```

On Fedora:
```bash
sudo dnf install -y python3 python3-pip git curl openssh-server
```

Verify:
```bash
python3 --version   # Should be 3.11+
git --version
```

Make sure SSH is running:
```bash
sudo systemctl enable ssh
sudo systemctl start ssh
```

Note the IdeaPad's IP address:
```bash
ip addr show | grep "inet "
# or
hostname -I
```

---

## Step 2: Set Up SSH Access from Your Mac

On your **MacBook** (one-time setup):

```bash
# Generate an SSH key if you don't have one
ssh-keygen -t ed25519 -C "your_email@example.com"

# Copy your public key to the IdeaPad (replaces password auth)
ssh-copy-id your_user@IDEAPAD_IP

# Test the connection (should log in without a password)
ssh your_user@IDEAPAD_IP
```

### Lock down SSH (optional but recommended)

On the IdeaPad, edit `/etc/ssh/sshd_config`:
```bash
sudo nano /etc/ssh/sshd_config
```
Set these lines:
```
PasswordAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
```
Then restart SSH:
```bash
sudo systemctl restart ssh
```

Now only your Mac's key can log in. No passwords, no root access.

---

## Step 3: Install Ollama (on IdeaPad)

SSH into the IdeaPad from your Mac, then:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Enable Ollama as a service so it starts on boot:
```bash
sudo systemctl enable ollama
sudo systemctl start ollama
```

Pull the default model (~10GB download, needs ~10GB RAM at Q4 quantization):
```bash
ollama pull qwen3:14b
```

If the IdeaPad has less than 16GB RAM, use a smaller model:
```bash
ollama pull qwen3:8b
```

Verify:
```bash
ollama list
curl http://localhost:11434/api/tags
```

---

## Step 4: Clone the Repository (on IdeaPad)

Still SSHed into the IdeaPad:

```bash
cd ~
git clone https://github.com/jordanklaw/Real-Estate-Market-Intelligence.git
cd Real-Estate-Market-Intelligence
```

### Security notes on cloning:
- HTTPS clone is encrypted via TLS -- safe for public repos
- The repo's `.gitignore` already excludes `.env`, `credentials.json`, `token.json` -- no secrets are in the repo
- To verify integrity: `git log --oneline -5` and confirm commits match what you see on GitHub

---

## Step 5: Run the Install Script (on IdeaPad)

```bash
cd ~/Real-Estate-Market-Intelligence
bash sales_prospector_mcp/install.sh
```

This creates a Python virtual environment, installs all pip dependencies, and creates the `briefs/` directory.

---

## Step 6: Create the `.env` File (on IdeaPad)

```bash
cd ~/Real-Estate-Market-Intelligence
cp .env.example .env

# Lock down permissions -- only your user can read it
chmod 600 .env
```

Edit `.env` if you need to change any values. If you used `qwen3:8b` in Step 3, update `OLLAMA_MODEL` accordingly.

---

## Step 7: Verify the Server Starts (on IdeaPad)

```bash
cd ~/Real-Estate-Market-Intelligence
source sales_prospector_mcp/venv/bin/activate

# Run the server (should start without errors)
python sales_prospector_mcp/server.py
# Ctrl+C to stop

# Run tests
python -m pytest tests/ -v
```

---

## Step 8: Connect Your Mac's MCP Client to the IdeaPad

The MCP server on the IdeaPad communicates via stdio (stdin/stdout), which works natively over SSH. No port forwarding needed for the basic setup.

### Option A: Claude Desktop on Mac

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` on your **Mac**:

```json
{
  "mcpServers": {
    "sales_prospector": {
      "command": "ssh",
      "args": [
        "your_user@IDEAPAD_IP",
        "cd ~/Real-Estate-Market-Intelligence && sales_prospector_mcp/venv/bin/python -m sales_prospector_mcp"
      ]
    }
  }
}
```

This tells Claude Desktop to SSH into the IdeaPad and run the MCP server. The MCP protocol works over stdio, so SSH pipes it transparently. No port forwarding required.

Restart Claude Desktop after saving.

### Option B: Claude Code on Mac

Create `.mcp.json` in your project directory on your **Mac**:

```json
{
  "mcpServers": {
    "sales_prospector": {
      "command": "ssh",
      "args": [
        "your_user@IDEAPAD_IP",
        "cd ~/Real-Estate-Market-Intelligence && sales_prospector_mcp/venv/bin/python -m sales_prospector_mcp"
      ]
    }
  }
}
```

### Option C: SSH Tunnel (if client needs HTTP/port-based connection)

If your MCP client requires a network endpoint rather than stdio, use an SSH tunnel from your Mac:

```bash
# On your Mac -- forwards local port to the IdeaPad
ssh -L 8080:localhost:8080 your_user@IDEAPAD_IP
```

Then point your MCP client to `http://localhost:8080` on your Mac. The tunnel makes it look local.

---

## Step 9: Daily Brief via Cron (Optional, on IdeaPad)

The daily brief runs entirely on the IdeaPad with no client needed. It writes HTML files to `briefs/`.

### Without email (simplest):

```bash
crontab -e
# Add this line (runs at 5:30 AM PST / 12:30 UTC, Mon-Fri):
30 12 * * 1-5 cd ~/Real-Estate-Market-Intelligence && sales_prospector_mcp/venv/bin/python daily_brief.py
```

Read briefs from your Mac:
```bash
# Pull a brief to your Mac
scp your_user@IDEAPAD_IP:~/Real-Estate-Market-Intelligence/briefs/latest.html .
open latest.html

# Or read over SSH
ssh your_user@IDEAPAD_IP "ls ~/Real-Estate-Market-Intelligence/briefs/"
```

### With email (requires Gmail OAuth):

This needs a one-time browser-based OAuth flow, which is harder on a headless box. Options:
1. Do the OAuth flow on your Mac, then `scp` the `credentials.json` and `token.json` to the IdeaPad
2. Temporarily set up X forwarding: `ssh -X your_user@IDEAPAD_IP` and run the script (needs a browser installed)
3. Skip email entirely and just pull briefs via `scp`

---

## Security Checklist (IdeaPad)

| Item | Status |
|------|--------|
| SSH key-based auth (no passwords) | Set up in Step 2 |
| Root SSH login disabled | Set in Step 2 |
| `.env` file permissions locked (`chmod 600`) | Set in Step 6 |
| No secrets in git repo (`.gitignore` covers them) | Already configured |
| Ollama runs locally (no data leaves the IdeaPad) | By default |
| HTTPS clone (encrypted transfer from GitHub) | Step 4 |
| No accounts/logins needed on Linux box | By design |

---

## Mac Security

### SSH Keys
- Use a passphrase on your ed25519 key (`ssh-keygen -t ed25519` will prompt for one). macOS Keychain stores it so you only type it once per login.
- Your private key (`~/.ssh/id_ed25519`) should be `600` permissions -- it already is by default, but verify: `ls -la ~/.ssh/id_ed25519`
- Never copy the private key anywhere. Only the `.pub` file goes to the IdeaPad.

### MCP Client Config
- `claude_desktop_config.json` contains the SSH command to your IdeaPad. If someone gets your Mac login, they get SSH access to the IdeaPad too. This is fine as long as your Mac has:
  - FileVault disk encryption enabled (System Settings > Privacy & Security > FileVault)
  - A strong login password
  - Auto-lock on sleep/screensaver

### `.env` and Credentials
- If you keep a local clone of the repo on your Mac for development, make sure you never commit `.env`, `credentials.json`, or `token.json`. The `.gitignore` already covers this, but double-check with `git status` before pushing.
- If you store an `ANTHROPIC_API_KEY` in `.env` on either machine, that key can make API calls on your account. Treat it like a password.

### GitHub Access
- Use a Personal Access Token (PAT) with minimal scopes if you push via HTTPS, or SSH keys for git too
- Enable 2FA on your GitHub account if you haven't already

### Network
- If you SSH into the IdeaPad over your home LAN, you're fine. If you ever SSH over the internet (e.g., from a coffee shop to home), the SSH encryption protects you, but consider:
  - Changing the IdeaPad's SSH port from 22 to something non-standard (`Port 2222` in `/etc/ssh/sshd_config`) to reduce drive-by scanning
  - Using `fail2ban` on the IdeaPad to block brute-force attempts
  - Since you already disabled password auth (keys only), you're already protected from the main attack vector

### The short version
FileVault on, passphrase on your SSH key, never commit secrets, 2FA on GitHub. That covers 99% of the risk surface for this setup.

---

## Quick Reference: Full Command Sequence

### On IdeaPad (first-time physical access or via SSH):
```bash
# System deps
sudo apt update && sudo apt install -y python3 python3-venv python3-pip git curl openssh-server
sudo systemctl enable ssh && sudo systemctl start ssh

# Ollama
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable ollama && sudo systemctl start ollama
ollama pull qwen3:14b

# Clone and install
cd ~
git clone https://github.com/jordanklaw/Real-Estate-Market-Intelligence.git
cd Real-Estate-Market-Intelligence
bash sales_prospector_mcp/install.sh

# Create .env
cp .env.example .env
chmod 600 .env

# Verify
source sales_prospector_mcp/venv/bin/activate
python sales_prospector_mcp/server.py   # Ctrl+C to stop
python -m pytest tests/ -v
```

### On your Mac (one-time):
```bash
# SSH key setup
ssh-keygen -t ed25519
ssh-copy-id your_user@IDEAPAD_IP

# MCP client config (Claude Desktop)
# Edit ~/Library/Application Support/Claude/claude_desktop_config.json
# with the SSH-based config from Step 8
```

### On your Mac (daily use):
```bash
# Just open Claude Desktop -- it SSHes into the IdeaPad automatically
# Or manually:
ssh your_user@IDEAPAD_IP
```

---

## Troubleshooting

**Ollama not responding:**
```bash
ssh your_user@IDEAPAD_IP "sudo systemctl status ollama"
ssh your_user@IDEAPAD_IP "curl http://localhost:11434/api/tags"
```

**MCP server won't start:**
```bash
ssh your_user@IDEAPAD_IP "cd ~/Real-Estate-Market-Intelligence && sales_prospector_mcp/venv/bin/python -c 'import sales_prospector_mcp'"
```

**SSH connection refused:**
```bash
# On IdeaPad, check SSH is running:
sudo systemctl status ssh
# Check firewall:
sudo ufw status
sudo ufw allow ssh
```
