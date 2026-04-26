# Loki

GitHub Social Engineering Honeypot & Threat Intelligence CLI.

Loki deploys realistic-looking fake repositories and Gists containing monitored credentials. When an attacker finds and interacts with these traps, Loki captures their behavior and profiles the threat.

## How It Works

```
1. Loki creates a convincing fake repo/gist (leaked .env, AWS keys, etc.)
2. A canary token is embedded inside the files
3. When an attacker finds and uses the trap → Loki is notified instantly
4. Attacker IP, location, tool used, and risk level are profiled
```

## Installation

```bash
git clone https://github.com/UmayTech/spectre.git
cd spectre/loki
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Setup

```bash
loki init
# Enter your GitHub Personal Access Token when prompted
# Token needs: gist scope (gist mode) or repo scope (repo mode)
```

## Usage

### Deploy a Trap

```bash
# Gist mode — no server needed
loki trap create --mode gist --scenario env-leaked

# Repo mode — creates a public GitHub repo
loki trap create --mode repo --scenario aws-creds

# Custom company name
loki trap create --mode gist --scenario internal-tool --company acmecorp
```

### Scenarios

| Scenario | Description |
|----------|-------------|
| `env-leaked` | Accidentally committed `.env` with DB, AWS, Stripe credentials |
| `aws-creds` | AWS credentials backup file |
| `internal-tool` | Internal deployment tool with hardcoded secrets |
| `db-backup` | PostgreSQL backup info with connection credentials |

### Monitor

```bash
loki monitor                    # Watch all active traps
loki monitor --trap a0fe2af9    # Watch a specific trap
loki monitor --interval 10      # Custom poll interval (seconds)
```

### Risk Levels

| Trigger | Risk |
|---------|------|
| GitHub CDN auto-render | LOW |
| Browser (manual view) | MEDIUM |
| `curl` / `wget` / `python-requests` | HIGH |
| `git clone` | HIGH |
| Secret scanner (trufflehog, gitleaks) | HIGH |
| `aws-cli` / credential use attempt | CRITICAL |

### Other Commands

```bash
loki trap list                  # List all traps and hit counts
loki trap delete <id>           # Deactivate a trap
loki trap delete <id> --purge   # Deactivate and remove from GitHub
loki report                     # Terminal threat report
loki report --format json       # JSON export (pipe to SIEM)
loki analyze <ip>               # Profile an IP address
```

## Modes

| Mode | Requires | Description |
|------|----------|-------------|
| `gist` | GitHub token (gist scope) | Deploys as a public GitHub Gist |
| `repo` | GitHub token (repo scope) | Creates a public GitHub repository |
| `local` | ngrok | Local git server exposed via ngrok |

## Data & Privacy

- All credentials in trap files are randomly generated — no real data is used.
- Canary tokens are powered by [webhook.site](https://webhook.site) (free, no account needed).
- IP geolocation uses [ip-api.com](https://ip-api.com) (free, no account needed).
- All trap/trigger data is stored locally in `~/.loki/loki.db`.

## Tech Stack

- Python 3.9+
- [Typer](https://typer.tiangolo.com/) + [Rich](https://rich.readthedocs.io/) — CLI & terminal UI
- [PyGitHub](https://pygithub.readthedocs.io/) — GitHub API
- SQLite — local storage
- webhook.site — canary token backend
- ip-api.com — IP geolocation

## Legal

This tool is intended for **authorized security testing and research only**.
Deploy traps only in environments you own or have explicit permission to test.
