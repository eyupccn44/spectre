import random
import string
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class TrapContent:
    scenario: str
    files: Dict[str, str]
    description: str
    tags: List[str]


COMPANY_NAMES = [
    "nexatech", "vaultcore", "datastream", "cloudpeak", "infranode",
    "bytewave", "stackforge", "netpulse", "codebase", "devhub",
    "axiscore", "gridlink", "pulsenet", "cipherbase", "solarbit",
]

SCENARIOS = ["env-leaked", "aws-creds", "internal-tool", "db-backup"]


def _rstr(length: int, chars: str = string.ascii_letters + string.digits) -> str:
    return "".join(random.choices(chars, k=length))


def _rpass(length: int = 16) -> str:
    return _rstr(length, string.ascii_letters + string.digits + "!@#$%")


def _aws_key() -> str:
    return "AKIA" + _rstr(16, string.ascii_uppercase + string.digits)


def _aws_secret() -> str:
    return _rstr(40, string.ascii_letters + string.digits + "+/")


def _slack_webhook() -> str:
    return f"https://hooks.slack.com/services/{_rstr(9)}/{_rstr(11)}/{_rstr(24)}"


def _random_company() -> str:
    return random.choice(COMPANY_NAMES)


def generate(scenario: str, canary_url: str, company: str = None) -> TrapContent:
    if not company:
        company = _random_company()
    company = company.lower()

    generators = {
        "env-leaked": _env_leaked,
        "aws-creds": _aws_creds,
        "internal-tool": _internal_tool,
        "db-backup": _db_backup,
    }
    fn = generators.get(scenario, _env_leaked)
    return fn(canary_url, company)


def _env_leaked(canary_url: str, company: str) -> TrapContent:
    key = _aws_key()
    secret = _aws_secret()
    db_pass = _rpass()
    jwt = _rstr(32)
    stripe = "sk_live_" + _rstr(32)
    redis_pass = _rpass(12)

    env = f"""# {company.upper()} — Production Environment
# WARNING: Do not commit this file

DATABASE_URL=postgresql://admin:{db_pass}@db.{company}-prod.internal:5432/production
DB_PASSWORD={db_pass}

AWS_ACCESS_KEY_ID={key}
AWS_SECRET_ACCESS_KEY={secret}
AWS_DEFAULT_REGION=us-east-1

STRIPE_SECRET_KEY={stripe}
STRIPE_WEBHOOK_SECRET=whsec_{_rstr(32)}

JWT_SECRET={jwt}
JWT_EXPIRY=86400

REDIS_URL=redis://:{redis_pass}@cache.{company}-prod.internal:6379/0
REDIS_PASSWORD={redis_pass}

SLACK_WEBHOOK={_slack_webhook()}
SENDGRID_API_KEY=SG.{_rstr(22)}.{_rstr(43)}

HEALTH_ENDPOINT={canary_url}
"""

    readme = f"""# {company}-backend

Internal backend service for {company.capitalize()} platform.

## Setup

```bash
cp .env.example .env
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Environment

Copy `.env.example` to `.env` and fill in the values.
Production credentials are managed by the infra team.

![Build Status]({canary_url}?ref=readme&repo={company}-backend)
"""

    gitignore = """.env
.env.local
.env.production
node_modules/
__pycache__/
*.pyc
dist/
build/
.DS_Store
"""

    requirements = """Django>=4.2
psycopg2-binary>=2.9
redis>=5.0
stripe>=7.0
boto3>=1.34
celery>=5.3
gunicorn>=21.2
"""

    return TrapContent(
        scenario="env-leaked",
        files={
            ".env": env,
            ".gitignore": gitignore,
            "README.md": readme,
            "requirements.txt": requirements,
        },
        description=f"{company}-backend — accidentally committed .env",
        tags=[company, "backend", "python", "production"],
    )


def _aws_creds(canary_url: str, company: str) -> TrapContent:
    credentials = f"""[default]
aws_access_key_id = {_aws_key()}
aws_secret_access_key = {_aws_secret()}
region = us-east-1

[{company}-prod]
aws_access_key_id = {_aws_key()}
aws_secret_access_key = {_aws_secret()}
region = us-east-1

[{company}-staging]
aws_access_key_id = {_aws_key()}
aws_secret_access_key = {_aws_secret()}
region = eu-west-1
"""

    config = f"""[default]
output = json
region = us-east-1

[profile {company}-prod]
region = us-east-1
output = json

[profile {company}-staging]
region = eu-west-1
output = json
"""

    readme = f"""# AWS Config Backup — {company.upper()}

Credential backup for {company.capitalize()} AWS infrastructure.

**Internal use only — do not distribute.**

![Sync Status]({canary_url}?ref=readme&type=aws-backup)
"""

    return TrapContent(
        scenario="aws-creds",
        files={
            "credentials": credentials,
            "config": config,
            "README.md": readme,
        },
        description=f"{company} AWS credentials backup",
        tags=[company, "aws", "credentials", "infrastructure"],
    )


def _internal_tool(canary_url: str, company: str) -> TrapContent:
    key = _aws_key()
    secret = _aws_secret()
    db_pass = _rpass()

    config = f"""{{
  "company": "{company}",
  "environment": "production",
  "database": {{
    "host": "db.{company}-prod.internal",
    "port": 5432,
    "name": "production",
    "user": "deploy_admin",
    "password": "{db_pass}"
  }},
  "aws": {{
    "access_key_id": "{key}",
    "secret_access_key": "{secret}",
    "region": "us-east-1",
    "s3_bucket": "{company}-prod-assets"
  }},
  "monitoring": {{
    "endpoint": "{canary_url}",
    "interval": 60
  }}
}}
"""

    deploy_sh = f"""#!/bin/bash
# {company.upper()} Deployment Script — Internal Use Only

set -e

DEPLOY_KEY="{key}"
DEPLOY_SECRET="{secret}"
DB_HOST="db.{company}-prod.internal"
DB_PASS="{db_pass}"

echo "[*] Starting {company} deployment..."

curl -s "{canary_url}?event=deploy-start" > /dev/null

aws s3 sync ./dist s3://{company}-prod-assets/ \\
  --aws-access-key-id "$DEPLOY_KEY" \\
  --aws-secret-access-key "$DEPLOY_SECRET"

echo "[+] Deployment complete."
"""

    readme = f"""# {company}-deploy

Internal deployment tooling for {company.capitalize()}.

**DO NOT SHARE EXTERNALLY.**

![Status]({canary_url}?ref=readme)
"""

    return TrapContent(
        scenario="internal-tool",
        files={
            "config.json": config,
            "deploy.sh": deploy_sh,
            "README.md": readme,
        },
        description=f"{company} internal deployment tool",
        tags=[company, "deploy", "internal", "infrastructure"],
    )


def _db_backup(canary_url: str, company: str) -> TrapContent:
    db_pass = _rpass()
    db_user = "backup_admin"
    size_mb = f"{random.randint(200, 999)}.{random.randint(1, 9)}"
    date_str = f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}"

    info = f"""# Database Backup — {company.upper()} Production
# Date: {date_str}
# Size: {size_mb} MB

Host:     db.{company}-prod.internal
Port:     5432
Database: production
User:     {db_user}
Password: {db_pass}

# Restore:
# pg_restore -h db.{company}-prod.internal -U {db_user} -d production backup.dump

# Verify integrity:
curl -s "{canary_url}?action=backup-access&env=prod" > /dev/null
"""

    readme = f"""# DB Backup — {company.upper()}

Production PostgreSQL backup — {date_str}.

Size: {size_mb} MB

![Verified]({canary_url}?ref=readme&type=db-backup)
"""

    return TrapContent(
        scenario="db-backup",
        files={
            "backup_info.txt": info,
            "README.md": readme,
        },
        description=f"{company} production database backup ({date_str})",
        tags=[company, "database", "backup", "postgresql"],
    )
