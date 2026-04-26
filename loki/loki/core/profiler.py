import requests
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class IPProfile:
    ip: str
    country: str
    country_code: str
    region: str
    city: str
    isp: str
    org: str
    is_proxy: bool
    is_tor: bool
    latitude: float
    longitude: float
    risk_level: str


# ── IP Profiling ───────────────────────────────────────────────────────────────

def profile_ip(ip: str) -> Optional[IPProfile]:
    if ip in ("unknown", "127.0.0.1", "::1"):
        return None
    try:
        resp = requests.get(
            f"http://ip-api.com/json/{ip}",
            params={"fields": "status,country,countryCode,regionName,city,isp,org,proxy,hosting,lat,lon"},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            return None

        is_proxy = data.get("proxy", False)
        is_hosting = data.get("hosting", False)

        return IPProfile(
            ip=ip,
            country=data.get("country", "Unknown"),
            country_code=data.get("countryCode", "??"),
            region=data.get("regionName", "Unknown"),
            city=data.get("city", "Unknown"),
            isp=data.get("isp", "Unknown"),
            org=data.get("org", "Unknown"),
            is_proxy=is_proxy,
            is_tor=is_proxy and is_hosting,
            latitude=data.get("lat", 0.0),
            longitude=data.get("lon", 0.0),
            risk_level=_ip_risk(is_proxy, is_hosting),
        )
    except Exception:
        return None


def _ip_risk(is_proxy: bool, is_hosting: bool) -> str:
    if is_proxy and is_hosting:
        return "CRITICAL"
    if is_proxy:
        return "HIGH"
    if is_hosting:
        return "MEDIUM"
    return "LOW"


# ── User-Agent Analysis ────────────────────────────────────────────────────────

# (actor_type, label, ua_risk)
_UA_RULES = [
    # GitHub infrastructure — not a real threat
    (["github-camo", "github-assets"],          "GitHub Proxy (auto-render)",        "NONE"),
    # Credential exploitation tools
    (["aws-cli", "aws-sdk", "boto", "s3cmd"],   "AWS Tool — credential use attempt", "CRITICAL"),
    (["terraform", "pulumi", "ansible"],         "IaC Tool — credential use attempt", "CRITICAL"),
    # Git operations — repo was cloned
    (["git/", "libgit", "go-git", "jgit"],      "Git Client — repo cloned",          "HIGH"),
    # Secret scanners
    (["trufflehog", "gitleaks", "gitrob",
      "semgrep", "detect-secrets"],             "Secret Scanner detected trap",      "HIGH"),
    # Generic download tools
    (["curl", "wget", "httpie", "aria2",
      "python-requests", "python-urllib",
      "go-http-client", "java-http"],           "Download Tool (credential harvest)","HIGH"),
    # Browsers — human manually inspecting
    (["chrome", "firefox", "safari",
      "edge", "opera", "brave"],               "Browser — manual inspection",       "MEDIUM"),
]

_RISK_ORDER = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
_RISK_LABEL = {0: "LOW", 1: "LOW", 2: "MEDIUM", 3: "HIGH", 4: "CRITICAL"}


def analyze_ua(user_agent: str) -> Tuple[str, str]:
    """Return (actor_label, ua_risk_level)."""
    ua = (user_agent or "").lower()
    for patterns, label, risk in _UA_RULES:
        if any(p in ua for p in patterns):
            return label, risk
    return "Unknown Client", "MEDIUM"


# ── Combined Risk ──────────────────────────────────────────────────────────────

def combined_risk(ip_risk: str, ua_risk: str) -> str:
    """Merge IP risk and UA risk — UA dominates; both elevated → bump one level."""
    if ua_risk == "NONE":
        return "LOW"

    ip_val = _RISK_ORDER.get(ip_risk, 1)
    ua_val = _RISK_ORDER.get(ua_risk, 2)
    merged = max(ip_val, ua_val)

    # Both independently elevated → escalate
    if ip_val >= 2 and ua_val >= 2:
        merged = min(merged + 1, 4)

    return _RISK_LABEL[merged]


# ── Formatting ─────────────────────────────────────────────────────────────────

def format_risk(level: str) -> str:
    colors = {
        "CRITICAL": "[bold red on dark_red] CRITICAL [/bold red on dark_red]",
        "HIGH":     "[bold red]HIGH[/bold red]",
        "MEDIUM":   "[bold yellow]MEDIUM[/bold yellow]",
        "LOW":      "[green]LOW[/green]",
    }
    return colors.get(level, level)
