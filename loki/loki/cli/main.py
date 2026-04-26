import json
import sys
import time
import threading
from pathlib import Path
from typing import Optional
from datetime import datetime

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich.columns import Columns
from rich import box

from loki.core import generator as gen_mod
from loki.core import canary as canary_mod
from loki.core import monitor as monitor_mod
from loki.core.profiler import profile_ip, analyze_ua, combined_risk, format_risk
from loki.github.gist import GistManager
from loki.github.repo import RepoManager
from loki.db.storage import Storage

app = typer.Typer(
    name="loki",
    help="GitHub Social Engineering Honeypot & Threat Intelligence",
    add_completion=False,
    rich_markup_mode="rich",
)
trap_app = typer.Typer(help="Manage honeypot traps")
app.add_typer(trap_app, name="trap")

console = Console()
CONFIG_PATH = Path.home() / ".loki" / "config.json"

BANNER = """[bold red]
 ██╗      ██████╗ ██╗  ██╗██╗
 ██║     ██╔═══██╗██║ ██╔╝██║
 ██║     ██║   ██║█████╔╝ ██║
 ██║     ██║   ██║██╔═██╗ ██║
 ███████╗╚██████╔╝██║  ██╗██║
 ╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝[/bold red]
[dim]  GitHub Honeypot & Threat Intelligence[/dim]
"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        console.print("[red]✗[/red] Not initialized. Run [cyan]loki init[/cyan] first.")
        raise typer.Exit(1)
    return json.loads(CONFIG_PATH.read_text())


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


def _mode_badge(mode: str) -> str:
    badges = {
        "gist": "[cyan]GIST[/cyan]",
        "repo": "[blue]REPO[/blue]",
        "local": "[yellow]LOCAL[/yellow]",
    }
    return badges.get(mode, mode.upper())


def _active_badge(active: int) -> str:
    return "[green]●[/green] ACTIVE" if active else "[dim]○ INACTIVE[/dim]"


# ── Commands ───────────────────────────────────────────────────────────────────

@app.callback(invoke_without_command=True)
def callback(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        console.print(BANNER)
        console.print("  Run [cyan]loki --help[/cyan] to see available commands.\n")


@app.command()
def init(
    token: Optional[str] = typer.Option(None, "--token", "-t", help="GitHub Personal Access Token"),
):
    """Initialize Loki and save configuration."""
    console.print(BANNER)
    console.print(Panel("[bold]Initializing Loki[/bold]", border_style="red", expand=False))

    if not token:
        token = typer.prompt(
            "GitHub Personal Access Token (leave empty for local/gist-public mode)",
            default="",
            hide_input=True,
        )

    cfg = {"github_token": token, "version": "1.0.0"}
    save_config(cfg)

    Storage()

    console.print("\n[green]✓[/green] Config saved at [dim]~/.loki/config.json[/dim]")
    console.print("[green]✓[/green] Database initialized at [dim]~/.loki/loki.db[/dim]")
    console.print("\n[bold]Ready.[/bold] Run [cyan]loki trap create[/cyan] to deploy your first trap.\n")


# ── trap create ────────────────────────────────────────────────────────────────

@trap_app.command("create")
def trap_create(
    mode: str = typer.Option("gist", "--mode", "-m", help="gist | repo | local"),
    scenario: str = typer.Option("env-leaked", "--scenario", "-s", help="env-leaked | aws-creds | internal-tool | db-backup"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Custom trap name"),
    company: Optional[str] = typer.Option(None, "--company", "-c", help="Company name to use in fake files"),
):
    """Deploy a new honeypot trap to GitHub."""
    cfg = load_config()
    token = cfg.get("github_token", "")
    storage = Storage()

    if mode not in ("gist", "repo", "local"):
        console.print(f"[red]✗[/red] Unknown mode: {mode}. Use gist | repo | local")
        raise typer.Exit(1)

    if scenario not in gen_mod.SCENARIOS:
        console.print(f"[red]✗[/red] Unknown scenario. Use: {', '.join(gen_mod.SCENARIOS)}")
        raise typer.Exit(1)

    # Step 1 — Canary token
    with console.status("[bold red]Creating canary token...[/bold red]"):
        try:
            token_obj = canary_mod.create_token(memo=f"loki-{scenario}")
        except RuntimeError as e:
            console.print(f"[red]✗[/red] {e}")
            raise typer.Exit(1)

    # Step 2 — Generate fake files
    with console.status("[bold red]Generating trap content...[/bold red]"):
        trap_content = gen_mod.generate(scenario, token_obj.url, company)

    trap_name = name or trap_content.description
    platform_url = None
    extra = {}

    # Step 3 — Deploy
    if mode == "gist":
        if not token:
            console.print("[yellow]⚠[/yellow]  No GitHub token — deploying as anonymous public gist.")
        with console.status("[bold red]Deploying gist...[/bold red]"):
            try:
                gist_mgr = GistManager(token or None)
                gist = gist_mgr.create(
                    files=trap_content.files,
                    description=trap_content.description,
                    public=True,
                )
                platform_url = gist["html_url"]
                extra["gist_id"] = gist["id"]
            except Exception as e:
                console.print(f"[red]✗[/red] Gist creation failed: {e}")
                raise typer.Exit(1)

    elif mode == "repo":
        if not token:
            console.print("[red]✗[/red] Repo mode requires a GitHub token.")
            raise typer.Exit(1)
        repo_name = (company or "infra") + "-" + scenario.replace("-", "")[:8]
        with console.status("[bold red]Creating repo and pushing files...[/bold red]"):
            try:
                repo_mgr = RepoManager(token)
                user = repo_mgr.get_user()
                owner = user["login"]
                repo_data = repo_mgr.create(repo_name, trap_content.description, private=False)
                repo_mgr.push_files(owner, repo_name, trap_content.files)
                platform_url = repo_data["html_url"]
                extra["repo_name"] = repo_name
                extra["owner"] = owner
            except Exception as e:
                console.print(f"[red]✗[/red] Repo creation failed: {e}")
                raise typer.Exit(1)

    elif mode == "local":
        console.print("[yellow]⚠[/yellow]  Local mode: expose manually via [cyan]ngrok http 8080[/cyan] and share the URL.")
        platform_url = f"http://localhost:8080 (expose with ngrok)"

    # Step 4 — Persist
    trap_id = storage.save_trap(
        name=trap_name,
        mode=mode,
        scenario=scenario,
        platform_url=platform_url,
        canary_uuid=token_obj.uuid,
        canary_url=token_obj.url,
        extra=extra,
    )

    # Result
    console.print()
    console.print(Panel(
        f"[bold green]✓ Trap deployed successfully[/bold green]\n\n"
        f"  [dim]ID[/dim]        {trap_id}\n"
        f"  [dim]Mode[/dim]      {_mode_badge(mode)}\n"
        f"  [dim]Scenario[/dim]  {scenario}\n"
        f"  [dim]URL[/dim]       [link={platform_url}]{platform_url}[/link]\n"
        f"  [dim]Canary[/dim]    {token_obj.url}\n\n"
        f"  Run [cyan]loki monitor[/cyan] to watch for triggers.",
        border_style="green",
        title="[bold]Loki[/bold]",
        expand=False,
    ))


# ── trap list ──────────────────────────────────────────────────────────────────

@trap_app.command("list")
def trap_list():
    """List all traps."""
    storage = Storage()
    traps = storage.get_traps()

    if not traps:
        console.print("[dim]No traps found. Run [cyan]loki trap create[/cyan] to get started.[/dim]")
        return

    table = Table(
        box=box.ROUNDED,
        border_style="red",
        header_style="bold red",
        show_lines=False,
    )
    table.add_column("ID", style="dim", width=10)
    table.add_column("Scenario", width=16)
    table.add_column("Mode", width=8)
    table.add_column("Status", width=14)
    table.add_column("Hits", justify="right", width=6)
    table.add_column("URL")

    for trap in traps:
        hits = storage.trigger_count(trap["id"])
        url = trap.get("platform_url") or "[dim]—[/dim]"
        table.add_row(
            trap["id"],
            trap["scenario"],
            _mode_badge(trap["mode"]),
            _active_badge(trap["active"]),
            f"[bold yellow]{hits}[/bold yellow]" if hits else "0",
            url[:60] + ("…" if len(url) > 60 else ""),
        )

    console.print(BANNER)
    console.print(table)
    console.print(f"\n  [dim]{len(traps)} trap(s) total[/dim]\n")


# ── trap delete ────────────────────────────────────────────────────────────────

@trap_app.command("delete")
def trap_delete(
    trap_id: str = typer.Argument(..., help="Trap ID to deactivate"),
    purge: bool = typer.Option(False, "--purge", help="Also delete from GitHub"),
):
    """Deactivate a trap (optionally remove from GitHub)."""
    cfg = load_config()
    storage = Storage()
    trap = storage.get_trap(trap_id)

    if not trap:
        console.print(f"[red]✗[/red] Trap [bold]{trap_id}[/bold] not found.")
        raise typer.Exit(1)

    if purge:
        token = cfg.get("github_token", "")
        extra = json.loads(trap.get("extra") or "{}")

        if trap["mode"] == "gist" and "gist_id" in extra and token:
            with console.status("Deleting gist..."):
                GistManager(token).delete(extra["gist_id"])
            console.print("[green]✓[/green] Gist deleted from GitHub.")

        elif trap["mode"] == "repo" and "repo_name" in extra and token:
            with console.status("Deleting repo..."):
                RepoManager(token).delete(extra["owner"], extra["repo_name"])
            console.print("[green]✓[/green] Repo deleted from GitHub.")

        canary_uuid = trap.get("canary_uuid")
        if canary_uuid:
            canary_mod.delete_token(canary_uuid)

    storage.deactivate_trap(trap_id)
    console.print(f"[green]✓[/green] Trap [bold]{trap_id}[/bold] deactivated.")


# ── monitor ────────────────────────────────────────────────────────────────────

@app.command()
def monitor(
    trap_id: Optional[str] = typer.Option(None, "--trap", "-t", help="Watch a specific trap ID"),
    interval: int = typer.Option(15, "--interval", "-i", help="Poll interval in seconds"),
):
    """Watch for canary triggers in real time."""
    storage = Storage()
    traps = storage.get_traps(active_only=True)

    if not traps:
        console.print("[dim]No active traps. Run [cyan]loki trap create[/cyan] first.[/dim]")
        raise typer.Exit()

    console.print(BANNER)
    console.print(Panel(
        f"[bold]Monitoring {len(traps)} active trap(s)[/bold] — polling every [cyan]{interval}s[/cyan]\n"
        f"Press [bold]Ctrl+C[/bold] to stop.",
        border_style="red",
        expand=False,
    ))
    console.print()

    def on_trigger(tid: str, trigger):
        trap = storage.get_trap(tid)
        scenario = trap["scenario"] if trap else tid

        ua_str = str(trigger.user_agent or "")
        actor_label, ua_risk = analyze_ua(ua_str)
        ip_profile = profile_ip(trigger.ip)
        ip_risk = ip_profile.risk_level if ip_profile else "LOW"
        final_risk = combined_risk(ip_risk, ua_risk)

        # Border color by risk
        border = {"CRITICAL": "red", "HIGH": "red", "MEDIUM": "yellow", "LOW": "dim"}.get(final_risk, "dim")

        # Alert header
        if final_risk == "CRITICAL":
            header = f"[bold red]🚨 CRITICAL THREAT — CANARY TRIGGERED[/bold red]"
        elif final_risk == "HIGH":
            header = f"[bold red]⚡ HIGH RISK — CANARY TRIGGERED[/bold red]"
        elif final_risk == "MEDIUM":
            header = f"[yellow]⚠  CANARY TRIGGERED[/yellow]"
        else:
            header = f"[dim]● CANARY TRIGGERED (auto-render)[/dim]"

        lines = [
            f"\n{header}  [dim]{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC[/dim]",
            f"  [dim]Trap[/dim]        {tid} ({scenario})",
            f"  [dim]Actor[/dim]       {actor_label}",
            f"  [dim]Risk[/dim]        {format_risk(final_risk)}",
            f"  [dim]IP[/dim]          {trigger.ip}",
        ]

        if ip_profile:
            lines.append(f"  [dim]Location[/dim]    {ip_profile.city}, {ip_profile.country} ({ip_profile.country_code})")
            lines.append(f"  [dim]ISP/Org[/dim]     {ip_profile.isp}")
            if ip_profile.is_proxy:
                lines.append("  [dim]Proxy/VPN[/dim]   [yellow]Yes[/yellow]")
            if ip_profile.is_tor:
                lines.append("  [dim]Tor[/dim]         [bold red]Yes — anonymized connection[/bold red]")

        lines.append(f"  [dim]User-Agent[/dim]  {ua_str[:80]}")
        lines.append(f"  [dim]Method[/dim]      {trigger.method}")
        if trigger.query:
            query_str = json.dumps(trigger.query) if isinstance(trigger.query, dict) else str(trigger.query)
            lines.append(f"  [dim]Query[/dim]       {query_str[:80]}")

        console.print(Panel("\n".join(lines), border_style=border, expand=False))

    try:
        monitor_mod.watch(storage, on_trigger, interval=interval, trap_id=trap_id)
    except KeyboardInterrupt:
        console.print("\n[dim]Monitoring stopped.[/dim]\n")


# ── report ─────────────────────────────────────────────────────────────────────

@app.command()
def report(
    trap_id: Optional[str] = typer.Option(None, "--trap", "-t", help="Report for a specific trap"),
    fmt: str = typer.Option("table", "--format", "-f", help="table | json"),
):
    """Generate a threat intelligence report."""
    storage = Storage()
    triggers = storage.get_triggers(trap_id)

    if fmt == "json":
        console.print_json(json.dumps(triggers, indent=2))
        return

    console.print(BANNER)

    if not triggers:
        console.print("[dim]No triggers recorded yet.[/dim]\n")
        return

    table = Table(
        box=box.ROUNDED,
        border_style="red",
        header_style="bold red",
        title=f"[bold]Threat Report[/bold] — {len(triggers)} trigger(s)",
    )
    table.add_column("Trap", width=10)
    table.add_column("IP", width=16)
    table.add_column("Country", width=8)
    table.add_column("ISP", width=22)
    table.add_column("Risk", width=10)
    table.add_column("User-Agent", width=30)
    table.add_column("Time")

    for t in triggers:
        ip = t.get("ip", "unknown")
        profile = profile_ip(ip)
        country = profile.country_code if profile else "??"
        isp = (profile.isp[:20] + "…") if profile and len(profile.isp) > 20 else (profile.isp if profile else "—")
        risk = format_risk(profile.risk_level) if profile else "—"
        ua = t.get("user_agent", "")[:28] + ("…" if len(t.get("user_agent", "")) > 28 else "")
        triggered_at = (t.get("triggered_at") or "")[:16]

        table.add_row(
            t.get("trap_id", ""),
            ip,
            country,
            isp,
            risk,
            ua,
            triggered_at,
        )

    console.print(table)
    console.print()


# ── analyze ────────────────────────────────────────────────────────────────────

@app.command()
def analyze(
    ip: str = typer.Argument(..., help="IP address to profile"),
):
    """Profile an IP address."""
    console.print(BANNER)
    with console.status(f"[bold red]Profiling {ip}...[/bold red]"):
        profile = profile_ip(ip)

    if not profile:
        console.print(f"[red]✗[/red] Could not profile IP: {ip}")
        raise typer.Exit(1)

    console.print(Panel(
        f"  [dim]IP[/dim]           {profile.ip}\n"
        f"  [dim]Country[/dim]      {profile.country} ({profile.country_code})\n"
        f"  [dim]Region[/dim]       {profile.region}\n"
        f"  [dim]City[/dim]         {profile.city}\n"
        f"  [dim]ISP[/dim]          {profile.isp}\n"
        f"  [dim]Org[/dim]          {profile.org}\n"
        f"  [dim]Proxy/VPN[/dim]    {'[yellow]Yes[/yellow]' if profile.is_proxy else 'No'}\n"
        f"  [dim]Tor[/dim]          {'[bold red]Yes[/bold red]' if profile.is_tor else 'No'}\n"
        f"  [dim]Coordinates[/dim]  {profile.latitude}, {profile.longitude}\n"
        f"  [dim]Risk Level[/dim]   {format_risk(profile.risk_level)}",
        title=f"[bold]IP Profile — {ip}[/bold]",
        border_style="red",
        expand=False,
    ))


if __name__ == "__main__":
    app()
