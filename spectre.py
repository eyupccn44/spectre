#!/usr/bin/env python3
"""
Spectre — Website mirroring & passive recon tool
Kullanım: python3 spectre.py [URL] [seçenekler]

YASAL UYARI / LEGAL DISCLAIMER
-------------------------------
Bu araç yalnızca yasal ve izinli güvenlik testleri, eğitim amaçlı kullanım
ve kendi sistemlerinizin analizi için tasarlanmıştır.

İzin alınmamış sistemler üzerinde kullanmak; Türkiye'de 5237 sayılı TCK
Madde 243-245 (bilişim suçları) kapsamında suç teşkil eder.

Kullanıcı, bu aracı yalnızca yasal yetki dahilinde kullanmayı kabul eder.
Geliştirici, kötüye kullanımdan doğan hiçbir hukuki veya cezai sorumluluk
kabul etmez.

This tool is intended solely for authorized security testing, educational
purposes, and analysis of systems you own or have explicit permission to test.
The developer assumes no liability for misuse.
"""

import argparse
import hashlib
import mimetypes
import os
import random
import re
import sys
import threading
import time
import urllib.robotparser
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse, urlencode, parse_qs

import requests
from bs4 import BeautifulSoup
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TransferSpeedColumn,
)
from rich.table import Table
from rich.text import Text
from rich import box

# ─── Sabitler ───────────────────────────────────────────────────────────────

VERSION = "1.1.0"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; Spectre/1.1; +https://github.com/spectre)"
)

# ─── ASCII Banner ────────────────────────────────────────────────────────────

def print_banner():
    from rich.align import Align
    from rich.text import Text
    from rich.columns import Columns

    RED   = "#e94560"
    PURP  = "#533483"
    DARK  = "#0f3460"
    WHITE = "bold white"

    # ── Hayalet şekli ──────────────────────────────────────────────────────
    ghost_lines = [
        ("         ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄",         DARK),
        ("       ▄███████████████████████▄",         DARK),
        ("      ████                   ████",        DARK),
        ("     ███   ██           ██   ███",         DARK),
        ("     ███   ██           ██   ███",         DARK),
        ("     ████                   ████",         DARK),
        (f"     ███   ╭─────────────╮   ███",        DARK),
        (f"     ███   ╰─────────────╯   ███",        DARK),
        ("     ████████████████████████████",        DARK),
        ("      ▀██▄  ▀██▄  ▀██▄  ▀██▄  ▀",         PURP),
        ("           ▀██▄  ▀██▄  ▀██▄",             PURP),
        ("                ▀██▄  ▀██▄",              PURP),
        ("                     ▀",                  PURP),
    ]

    for line, color in ghost_lines:
        t = Text(line, style=color, justify="center")
        # gözler için beyaz renk
        if "██           ██" in line:
            t = Text(justify="center")
            t.append("     ███   ", style=DARK)
            t.append("██", style=WHITE)
            t.append("           ", style=DARK)
            t.append("██", style=WHITE)
            t.append("   ███", style=DARK)
        if "╭─────────────╮" in line:
            t = Text(justify="center")
            t.append("     ███   ", style=DARK)
            t.append("╭─────────────╮", style=RED)
            t.append("   ███", style=DARK)
        if "╰─────────────╯" in line:
            t = Text(justify="center")
            t.append("     ███   ", style=DARK)
            t.append("╰─────────────╯", style=RED)
            t.append("   ███", style=DARK)
        console.print(Align.center(t))

    console.print()

    # ── SPECTRE yazısı ─────────────────────────────────────────────────────
    title_lines = [
        " ███████╗██████╗ ███████╗ ██████╗████████╗██████╗ ███████╗",
        " ██╔════╝██╔══██╗██╔════╝██╔════╝╚══██╔══╝██╔══██╗██╔════╝",
        " ███████╗██████╔╝█████╗  ██║        ██║   ██████╔╝█████╗  ",
        " ╚════██║██╔═══╝ ██╔══╝  ██║        ██║   ██╔══██╗██╔══╝  ",
        " ███████║██║     ███████╗╚██████╗   ██║   ██║  ██║███████╗",
        " ╚══════╝╚═╝     ╚══════╝ ╚═════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝",
    ]
    for line in title_lines:
        console.print(Align.center(Text(line, style=f"bold {RED}")))

    # ── Alt bilgi satırı ───────────────────────────────────────────────────
    info = Text(justify="center")
    info.append("─" * 20, style=PURP)
    info.append(f"  website mirroring & passive recon  ", style="dim")
    info.append(f"v{VERSION}", style=f"bold {PURP}")
    info.append("  " + "─" * 20, style=PURP)
    console.print(Align.center(info))

    # ── Özellik etiketleri (Kali tarzı) ───────────────────────────────────
    tags = Text(justify="center")
    for tag, color in [
        (" mirror ", RED), ("  ", ""), ("stealth ", PURP),
        (" ", ""), ("decoy ", DARK), (" ", ""), ("recon ", "green"),
    ]:
        if tag.strip():
            tags.append(f"[{tag.strip()}]", style=f"bold {color}")
        else:
            tags.append("  ")
    console.print(Align.center(tags))
    console.print()

# ─── Stealth: Gerçekçi tarayıcı User-Agent havuzu ───────────────────────────

UA_POOL = [
    # Chrome / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Chrome / macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.122 Safari/537.36",
    # Firefox / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    # Firefox / macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Safari / macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    # Edge / Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    # Chrome / Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# Tarayıcıya göre gerçekçi başlık setleri
UA_HEADERS: dict[str, dict[str, str]] = {
    "Chrome": {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    },
    "Firefox": {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.8,en-US;q=0.5,en;q=0.3",
        "Accept-Encoding": "gzip, deflate, br",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "TE": "trailers",
    },
    "Safari": {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Upgrade-Insecure-Requests": "1",
    },
}

# ─── Decoy: Zararsız tuzak istek URL kalıpları ───────────────────────────────

DECOY_PATHS = [
    "/favicon.ico",
    "/robots.txt",
    "/sitemap.xml",
    "/humans.txt",
    "/manifest.json",
    "/apple-touch-icon.png",
    "/browserconfig.xml",
    "/.well-known/security.txt",
]

# İndirilecek kaynak türleri
ASSET_TAGS = {
    "img":    ["src", "data-src", "data-original"],
    "script": ["src"],
    "link":   ["href"],
    "source": ["src", "srcset"],
    "video":  ["src", "poster"],
    "audio":  ["src"],
    "iframe": ["src"],
    "embed":  ["src"],
    "object": ["data"],
    "track":  ["src"],
    "input":  ["src"],
}

# Sayfa olarak kabul edilen uzantılar
PAGE_EXTENSIONS = {
    "", ".html", ".htm", ".xhtml", ".xml", ".php", ".asp",
    ".aspx", ".jsp", ".cfm", ".cgi", ".shtml", ".phtml",
}

# Binary / medya uzantıları (link rewrite edilmez içlerindeki linkler)
BINARY_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".svg",
    ".ico", ".bmp", ".tiff", ".mp4", ".webm", ".ogg", ".mp3",
    ".wav", ".flac", ".pdf", ".zip", ".gz", ".tar", ".rar",
    ".woff", ".woff2", ".ttf", ".eot", ".otf", ".exe", ".dmg",
    ".apk", ".ipa", ".bin", ".iso",
}

console = Console()


# ─── Yardımcı fonksiyonlar ──────────────────────────────────────────────────

def normalize_url(url: str) -> str:
    """URL'yi normalize et (fragment kaldır, trailing slash düzelt)."""
    p = urlparse(url)
    # Fragment kaldır
    p = p._replace(fragment="")
    return urlunparse(p)


def url_to_path(base_dir: Path, url: str, base_url: str) -> Path:
    """URL'yi yerel dosya yoluna çevir."""
    parsed = urlparse(url)
    base_parsed = urlparse(base_url)

    # Yol bölümü
    path = parsed.path.lstrip("/") or "index.html"

    # Query string varsa hash'le ekle
    if parsed.query:
        query_hash = hashlib.md5(parsed.query.encode()).hexdigest()[:8]
        stem, ext = os.path.splitext(path)
        path = f"{stem}_{query_hash}{ext}"

    # Dizin ise index.html ekle
    if path.endswith("/") or "." not in os.path.basename(path):
        if not path.endswith("/"):
            path += "/"
        path += "index.html"

    # Host farklıysa host klasörü altına al
    if parsed.netloc and parsed.netloc != base_parsed.netloc:
        path = os.path.join(parsed.netloc, path)

    return base_dir / path


def rewrite_css_urls(css_content: str, css_url: str, base_url: str, url_map: dict) -> str:
    """CSS içindeki url() referanslarını yerel yollarla değiştir."""
    def replace_url(match):
        raw = match.group(1).strip("'\"")
        abs_url = normalize_url(urljoin(css_url, raw))
        if abs_url in url_map:
            return f"url('{url_map[abs_url]}')"
        return match.group(0)

    return re.sub(r"url\(([^)]+)\)", replace_url, css_content)


def get_extension(url: str, content_type: str = "") -> str:
    """URL veya Content-Type'dan uzantı belirle."""
    path = urlparse(url).path
    _, ext = os.path.splitext(path)
    if ext:
        return ext.lower()
    # Content-Type'dan tahmin et
    if content_type:
        ct = content_type.split(";")[0].strip()
        ext = mimetypes.guess_extension(ct) or ""
        # Bazı yaygın düzeltmeler
        fixes = {".jpe": ".jpg", ".jpeg": ".jpg"}
        return fixes.get(ext, ext)
    return ""


# ─── Ana sınıf ──────────────────────────────────────────────────────────────

class Spectre:
    def __init__(self, args):
        self.start_url = normalize_url(args.url)
        self.base_parsed = urlparse(self.start_url)
        self.base_domain = self.base_parsed.netloc
        self.output_dir = Path(args.output or self.base_domain).resolve()
        self.max_depth = args.depth
        self.threads = args.threads
        self.delay = args.delay
        self.user_agent = args.user_agent or DEFAULT_USER_AGENT
        self.respect_robots = not args.no_robots
        self.stay_on_domain = not args.allow_external
        self.include_pattern = re.compile(args.include) if args.include else None
        self.exclude_pattern = re.compile(args.exclude) if args.exclude else None
        self.timeout = args.timeout
        self.video_timeout = args.video_timeout
        self.max_size = args.max_size * 1024 * 1024 if args.max_size else None
        self.no_videos = args.no_videos
        self.stealth = args.stealth
        self.decoy = args.decoy
        self.decoy_ratio = args.decoy_ratio  # her N gerçek istekte 1 decoy
        self.verbose = args.verbose
        self.log_file = args.log

        # Stealth: User-Agent rotasyon durumu
        self._ua_pool = UA_POOL.copy()
        random.shuffle(self._ua_pool)
        self._ua_index = 0
        self._ua_lock = threading.Lock()
        self._request_count = 0  # decoy tetikleme sayacı

        # Durum
        self.visited: set[str] = set()
        self.queued: set[str] = set()
        self.failed: list[tuple[str, str]] = []
        self.url_to_local: dict[str, str] = {}  # url -> yerel göreli yol
        self.lock = threading.Lock()
        self.stats = {
            "downloaded": 0,
            "skipped": 0,
            "errors": 0,
            "bytes": 0,
            "pages": 0,
        }

        # Robots.txt
        self.robots = urllib.robotparser.RobotFileParser()
        if self.respect_robots:
            robots_url = f"{self.base_parsed.scheme}://{self.base_domain}/robots.txt"
            self.robots.set_url(robots_url)
            try:
                self.robots.read()
            except Exception:
                pass

        # HTTP oturumu
        self.session = requests.Session()
        if self.stealth:
            # Stealth modda başlangıç UA'sı — her istekte rotate edilecek
            initial_ua = self._ua_pool[0]
            browser = self._detect_browser(initial_ua)
            headers = dict(UA_HEADERS.get(browser, UA_HEADERS["Chrome"]))
            headers["User-Agent"] = initial_ua
        else:
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "tr,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
            }
        self.session.headers.update(headers)

        # Log dosyası
        self.log_handle = None
        if self.log_file:
            self.log_handle = open(self.log_file, "w", encoding="utf-8")

        # Progress
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            TextColumn("[cyan]{task.fields[done]}[/cyan]/[white]{task.fields[total_count]}[/white]"),
            TextColumn("•"),
            TimeElapsedColumn(),
            console=console,
        )
        self.main_task: TaskID | None = None

    # ── Stealth yardımcıları ─────────────────────────────────────────────────

    @staticmethod
    def _detect_browser(ua: str) -> str:
        if "Firefox" in ua:
            return "Firefox"
        if "Safari" in ua and "Chrome" not in ua:
            return "Safari"
        return "Chrome"

    def _next_ua(self) -> tuple[str, dict[str, str]]:
        """Havuzdan sıradaki User-Agent'ı ve uygun başlıkları döndür."""
        with self._ua_lock:
            ua = self._ua_pool[self._ua_index % len(self._ua_pool)]
            self._ua_index += 1
        browser = self._detect_browser(ua)
        headers = dict(UA_HEADERS.get(browser, UA_HEADERS["Chrome"]))
        headers["User-Agent"] = ua
        return ua, headers

    def _stealth_delay(self):
        """
        Stealth modda insan benzeri gecikme:
        base delay + rastgele jitter (±%40).
        delay=0 ise 0.3-1.2s arası otomatik eklenir.
        """
        base = self.delay if self.delay > 0 else random.uniform(0.3, 1.2)
        jitter = base * random.uniform(-0.4, 0.4)
        time.sleep(max(0.05, base + jitter))

    def _maybe_send_decoy(self):
        """
        Decoy modda: her decoy_ratio gerçek istekte bir kez
        sunucuya gerçekçi ama zararsız bir istek atar
        (favicon, robots.txt, manifest.json vb.)
        """
        with self._ua_lock:
            self._request_count += 1
            count = self._request_count
        if count % self.decoy_ratio != 0:
            return
        path = random.choice(DECOY_PATHS)
        decoy_url = f"{self.base_parsed.scheme}://{self.base_domain}{path}"
        try:
            ua, hdrs = self._next_ua() if self.stealth else (self.user_agent, {})
            hdrs["User-Agent"] = ua if self.stealth else self.user_agent
            # Decoy için sahte Referer — sanki kullanıcı içeriden tıkladı
            hdrs["Referer"] = self.start_url
            self.session.get(decoy_url, headers=hdrs, timeout=10, stream=False)
            self.log(f"[DECOY] {decoy_url}", "INFO")
        except Exception:
            pass  # decoy başarısız olsa önemli değil

    # ── Log ─────────────────────────────────────────────────────────────────

    def log(self, msg: str, level: str = "INFO"):
        timestamp = time.strftime("%H:%M:%S")
        if self.log_handle:
            self.log_handle.write(f"[{timestamp}] [{level}] {msg}\n")
            self.log_handle.flush()
        if self.verbose or level in ("ERROR", "WARN"):
            color = {"INFO": "white", "OK": "green", "WARN": "yellow", "ERROR": "red"}.get(level, "white")
            console.print(f"  [{color}][{level}][/{color}] {msg}")

    def is_allowed(self, url: str) -> bool:
        """URL'nin indirilmesine izin var mı?"""
        parsed = urlparse(url)

        # Sadece http/https
        if parsed.scheme not in ("http", "https"):
            return False

        # Domain kısıtlaması
        if self.stay_on_domain and parsed.netloc != self.base_domain:
            return False

        # Robots.txt
        if self.respect_robots and not self.robots.can_fetch(self.user_agent, url):
            return False

        # Kullanıcı filtreleri
        if self.include_pattern and not self.include_pattern.search(url):
            return False
        if self.exclude_pattern and self.exclude_pattern.search(url):
            return False

        return True

    def fetch(self, url: str) -> requests.Response | None:
        """URL'yi indir, None döndürürse başarısız."""
        try:
            # ── Gecikme ─────────────────────────────────────────────────────
            if self.stealth:
                self._stealth_delay()
            elif self.delay > 0:
                time.sleep(self.delay)

            # ── Decoy tuzak isteği (arka planda) ────────────────────────────
            if self.decoy:
                threading.Thread(target=self._maybe_send_decoy, daemon=True).start()

            # ── Başlık rotasyonu (stealth) ───────────────────────────────────
            if self.stealth:
                ua, extra_headers = self._next_ua()
                # Referer: sanki önceki sayfadan geliyoruz
                parsed = urlparse(url)
                extra_headers["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"
            else:
                extra_headers = {}

            # Video/büyük medya için bağlantı timeout'unu uzat
            ext = get_extension(url)
            is_likely_video = ext in {
                ".mp4", ".webm", ".mkv", ".avi", ".mov", ".flv",
                ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a",
                ".ts", ".m2ts",
            }
            timeout = (10, self.video_timeout) if is_likely_video else self.timeout

            resp = self.session.get(
                url,
                headers=extra_headers if extra_headers else None,
                timeout=timeout,
                stream=True,
                allow_redirects=True,
            )

            # Boyut kontrolü (Content-Length varsa önceden kontrol et)
            if self.max_size:
                content_length = int(resp.headers.get("Content-Length", 0))
                if content_length and content_length > self.max_size:
                    self.log(f"Boyut limiti aşıldı ({content_length//1024//1024}MB): {url}", "WARN")
                    resp.close()
                    return None

            resp.raise_for_status()
            return resp

        except requests.exceptions.TooManyRedirects:
            self.log(f"Çok fazla yönlendirme: {url}", "WARN")
        except requests.exceptions.ConnectionError:
            self.log(f"Bağlantı hatası: {url}", "ERROR")
        except requests.exceptions.Timeout:
            self.log(f"Zaman aşımı: {url}", "ERROR")
        except requests.exceptions.HTTPError as e:
            self.log(f"HTTP {e.response.status_code}: {url}", "WARN")
        except Exception as e:
            self.log(f"Bilinmeyen hata ({url}): {e}", "ERROR")

        return None

    def save_file(self, local_path: Path, content: bytes):
        """Dosyayı diske kaydet (küçük dosyalar için)."""
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(content)

    def save_streaming(self, local_path: Path, resp: requests.Response) -> int:
        """
        Büyük dosyaları (video vb.) chunk chunk diske yaz.
        Tüm içeriği RAM'e yüklemez. İndirilen byte sayısını döner.
        """
        local_path.parent.mkdir(parents=True, exist_ok=True)
        total_bytes = 0
        chunk_size = 1024 * 1024  # 1 MB chunk
        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    total_bytes += len(chunk)
                    # Boyut limiti streaming sırasında da kontrol et
                    if self.max_size and total_bytes > self.max_size:
                        self.log(f"Boyut limiti aşıldı, kesiliyor: {local_path.name}", "WARN")
                        break
        return total_bytes

    def extract_links(self, soup: BeautifulSoup, page_url: str) -> list[str]:
        """HTML'den tüm bağlantıları çıkar."""
        links = []

        # <a href>
        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()
            if href and not href.startswith(("#", "javascript:", "mailto:", "tel:")):
                links.append(urljoin(page_url, href))

        # <area href>
        for tag in soup.find_all("area", href=True):
            links.append(urljoin(page_url, tag["href"]))

        return [normalize_url(l) for l in links]

    def extract_assets(self, soup: BeautifulSoup, page_url: str) -> list[str]:
        """HTML'den CSS, JS, resim vb. asset URL'lerini çıkar."""
        assets = []

        for tag_name, attrs in ASSET_TAGS.items():
            for tag in soup.find_all(tag_name):
                for attr in attrs:
                    val = tag.get(attr, "").strip()
                    if not val or val.startswith("data:"):
                        continue
                    # srcset desteği
                    if attr == "srcset":
                        for part in val.split(","):
                            src = part.strip().split()[0]
                            if src:
                                assets.append(urljoin(page_url, src))
                    else:
                        assets.append(urljoin(page_url, val))

        # Inline style içindeki url()
        for tag in soup.find_all(style=True):
            for m in re.finditer(r"url\(['\"]?([^)'\"]+)['\"]?\)", tag["style"]):
                assets.append(urljoin(page_url, m.group(1)))

        # <style> blokları
        for style in soup.find_all("style"):
            for m in re.finditer(r"url\(['\"]?([^)'\"]+)['\"]?\)", style.get_text()):
                assets.append(urljoin(page_url, m.group(1)))

        return [normalize_url(a) for a in assets if a]

    def rewrite_html(self, soup: BeautifulSoup, page_url: str, local_path: Path) -> str:
        """HTML içindeki linkleri yerel yollarla değiştir."""
        page_local = local_path.parent

        def to_relative(url: str) -> str | None:
            norm = normalize_url(url)
            if norm in self.url_to_local:
                target = self.output_dir / self.url_to_local[norm]
                try:
                    return os.path.relpath(target, page_local)
                except ValueError:
                    return self.url_to_local[norm]
            return None

        # <a href>
        for tag in soup.find_all("a", href=True):
            rel = to_relative(urljoin(page_url, tag["href"]))
            if rel:
                tag["href"] = rel

        # Asset tag'leri
        for tag_name, attrs in ASSET_TAGS.items():
            for tag in soup.find_all(tag_name):
                for attr in attrs:
                    val = tag.get(attr, "").strip()
                    if not val or val.startswith("data:"):
                        continue
                    if attr == "srcset":
                        new_parts = []
                        for part in val.split(","):
                            parts = part.strip().split()
                            if parts:
                                rel = to_relative(urljoin(page_url, parts[0]))
                                if rel:
                                    parts[0] = rel
                                new_parts.append(" ".join(parts))
                        tag[attr] = ", ".join(new_parts)
                    else:
                        rel = to_relative(urljoin(page_url, val))
                        if rel:
                            tag[attr] = rel

        return str(soup)

    def process_page(self, url: str, depth: int) -> list[tuple[str, int]]:
        """
        Bir sayfayı işle:
        - İndir
        - Kaydet
        - Yeni linkler döndür
        """
        resp = self.fetch(url)
        if not resp:
            with self.lock:
                self.stats["errors"] += 1
                self.failed.append((url, "fetch failed"))
            return []

        content_type = resp.headers.get("Content-Type", "").lower()

        # Yerel yol hesapla
        local_path = url_to_path(self.output_dir, url, self.start_url)

        # Uzantı düzelt
        if "text/html" in content_type and not str(local_path).endswith(".html"):
            local_path = local_path.with_suffix(".html")
        elif "text/css" in content_type and not str(local_path).endswith(".css"):
            local_path = local_path.with_suffix(".css")

        # url_to_local kaydı (streaming başlamadan kaydet ki diğer thread'ler bulabilsin)
        relative = str(local_path.relative_to(self.output_dir))
        with self.lock:
            self.url_to_local[url] = relative

        new_links: list[tuple[str, int]] = []

        # ── Video / büyük medya ── streaming ile indir, RAM'e yüklenme ─────────
        is_video = any(t in content_type for t in (
            "video/", "audio/", "application/octet-stream",
        )) or get_extension(url) in {
            ".mp4", ".webm", ".mkv", ".avi", ".mov", ".flv", ".wmv",
            ".m4v", ".ts", ".m2ts", ".mpeg", ".mpg",
            ".mp3", ".wav", ".flac", ".aac", ".ogg", ".opus", ".m4a",
        }

        if is_video:
            if self.no_videos:
                self.log(f"Video atlandı: {url}", "INFO")
                with self.lock:
                    self.stats["skipped"] += 1
                return []

            content_length = int(resp.headers.get("Content-Length", 0))
            size_str = f"{content_length/1024/1024:.1f} MB" if content_length else "? MB"
            self.log(f"Video indiriliyor ({size_str}): {local_path.name}", "INFO")

            nbytes = self.save_streaming(local_path, resp)
            with self.lock:
                self.stats["bytes"] += nbytes
                self.stats["downloaded"] += 1
            self.log(f"[OK] Video kaydedildi ({nbytes/1024/1024:.1f} MB): {local_path.relative_to(self.output_dir)}", "OK")
            return []

        # ── Metin tabanlı içerik — RAM'e yükle ──────────────────────────────────
        content = resp.content
        with self.lock:
            self.stats["bytes"] += len(content)
            self.stats["downloaded"] += 1

        if "text/html" in content_type:
            with self.lock:
                self.stats["pages"] += 1

            try:
                html = content.decode(resp.encoding or "utf-8", errors="replace")
            except Exception:
                html = content.decode("latin-1", errors="replace")

            soup = BeautifulSoup(html, "lxml")

            # Linkleri çıkar
            if depth < self.max_depth:
                for link in self.extract_links(soup, url):
                    if self.is_allowed(link):
                        with self.lock:
                            if link not in self.visited and link not in self.queued:
                                self.queued.add(link)
                                new_links.append((link, depth + 1))

            # Assetleri kuyruğa ekle (depth kısıtı olmadan)
            for asset in self.extract_assets(soup, url):
                if self.is_allowed(asset) or not self.stay_on_domain:
                    with self.lock:
                        if asset not in self.visited and asset not in self.queued:
                            self.queued.add(asset)
                            new_links.append((asset, depth))

            # Rewrite ve kaydet
            rewritten = self.rewrite_html(soup, url, local_path)
            self.save_file(local_path, rewritten.encode("utf-8", errors="replace"))
            self.log(f"[OK] Sayfa: {local_path.relative_to(self.output_dir)}", "OK")

        elif "text/css" in content_type:
            try:
                css = content.decode(resp.encoding or "utf-8", errors="replace")
                for m in re.finditer(r"url\(['\"]?([^)'\"]+)['\"]?\)", css):
                    asset = normalize_url(urljoin(url, m.group(1)))
                    if self.is_allowed(asset) or not self.stay_on_domain:
                        with self.lock:
                            if asset not in self.visited and asset not in self.queued:
                                self.queued.add(asset)
                                new_links.append((asset, depth))
                self.save_file(local_path, content)
                self.log(f"[OK] CSS: {local_path.relative_to(self.output_dir)}", "OK")
            except Exception:
                self.save_file(local_path, content)
        else:
            self.save_file(local_path, content)
            self.log(f"[OK] Dosya: {local_path.relative_to(self.output_dir)}", "OK")

        return new_links

    def run(self):
        """Ana indirme döngüsü."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        modes = []
        if self.stealth:
            modes.append("[bold magenta]STEALTH[/bold magenta]")
        if self.decoy:
            modes.append(f"[bold yellow]DECOY[/bold yellow] (1/{self.decoy_ratio})")
        mode_str = "  ".join(modes) if modes else "[dim]normal[/dim]"

        console.print(Panel.fit(
            f"[bold #e94560]Spectre v{VERSION}[/bold #e94560]\n"
            f"[white]Hedef:[/white] [yellow]{self.start_url}[/yellow]\n"
            f"[white]Çıktı:[/white] [green]{self.output_dir}[/green]\n"
            f"[white]Derinlik:[/white] {self.max_depth}  "
            f"[white]Thread:[/white] {self.threads}  "
            f"[white]Gecikme:[/white] {'jitter' if self.stealth else f'{self.delay}s'}\n"
            f"[white]Mod:[/white] {mode_str}",
            title="[bold]Website Kopyalama Başlıyor[/bold]",
            border_style="blue",
        ))

        start_time = time.time()

        # İlk URL'yi kuyruğa ekle
        queue: deque[tuple[str, int]] = deque()
        queue.append((self.start_url, 0))
        self.queued.add(self.start_url)

        with self.progress:
            self.main_task = self.progress.add_task(
                "İndiriliyor...",
                total=1,
                done=0,
                total_count=1,
            )

            with ThreadPoolExecutor(max_workers=self.threads) as executor:
                futures = {}

                def submit_url(url, depth):
                    if url not in self.visited:
                        self.visited.add(url)
                        fut = executor.submit(self.process_page, url, depth)
                        futures[fut] = (url, depth)

                # İlk URL'yi gönder
                submit_url(self.start_url, 0)

                while futures or queue:
                    # Kuyruktan yeni URL'leri gönder
                    while queue and len(futures) < self.threads * 4:
                        url, depth = queue.popleft()
                        if url not in self.visited:
                            submit_url(url, depth)

                    if not futures:
                        break

                    # Bir tane tamamlanmasını bekle
                    completed_futs = as_completed(list(futures.keys()))
                    fut = next(completed_futs)
                    done_futures = [fut]

                    # Aynı anda tamamlanmış olabilecek diğerlerini de topla
                    done_futures += [f for f in list(futures.keys()) if f is not fut and f.done()]

                    for fut in done_futures:
                        url, depth = futures.pop(fut)
                        try:
                            new_links = fut.result()
                            for link, d in new_links:
                                if link not in self.visited:
                                    queue.append((link, d))
                        except Exception as e:
                            self.log(f"İşlem hatası ({url}): {e}", "ERROR")
                            with self.lock:
                                self.stats["errors"] += 1

                        # Progress güncelle
                        total = len(self.visited) + len(queue)
                        self.progress.update(
                            self.main_task,
                            advance=1,
                            total=max(total, 1),
                            done=self.stats["downloaded"],
                            total_count=max(total, 1),
                        )

        elapsed = time.time() - start_time
        self._print_summary(elapsed)

        if self.log_handle:
            self.log_handle.close()

    def _print_summary(self, elapsed: float):
        """İndirme özeti tablosunu yazdır."""
        size_mb = self.stats["bytes"] / (1024 * 1024)

        table = Table(box=box.ROUNDED, border_style="green", title="[bold]İndirme Özeti[/bold]")
        table.add_column("Metrik", style="cyan", no_wrap=True)
        table.add_column("Değer", style="white")

        table.add_row("Toplam indirilen", str(self.stats["downloaded"]))
        table.add_row("Sayfalar", str(self.stats["pages"]))
        table.add_row("Hatalar", f"[red]{self.stats['errors']}[/red]" if self.stats["errors"] else "0")
        table.add_row("Toplam boyut", f"{size_mb:.2f} MB")
        table.add_row("Geçen süre", f"{elapsed:.1f}s")
        table.add_row("Ortalama hız", f"{size_mb/elapsed:.2f} MB/s" if elapsed > 0 else "-")
        table.add_row("Çıktı dizini", str(self.output_dir))

        console.print()
        console.print(table)

        if self.failed:
            console.print(f"\n[red]Başarısız URL'ler ({len(self.failed)}):[/red]")
            for url, reason in self.failed[:20]:
                console.print(f"  [dim]•[/dim] {url} [red]({reason})[/red]")
            if len(self.failed) > 20:
                console.print(f"  [dim]... ve {len(self.failed)-20} tane daha[/dim]")

        console.print(f"\n[bold green]✓ Tamamlandı![/bold green] Site [yellow]{self.output_dir}[/yellow] dizinine kaydedildi.\n")


# ─── CLI ────────────────────────────────────────────────────────────────────

# ─── Pasif Analiz Modülü ────────────────────────────────────────────────────

# Teknoloji imzaları
TECH_SIGNATURES: dict[str, list[tuple[str, str]]] = {
    # CMS
    "WordPress":       [("path", r"wp-content/"), ("path", r"wp-includes/"), ("html", r"wp-json")],
    "Joomla":          [("path", r"components/com_"), ("html", r"/media/jui/")],
    "Drupal":          [("html", r'drupal\.settings'), ("path", r"sites/default/files")],
    "Magento":         [("path", r"skin/frontend/"), ("html", r"Mage\.Cookies")],
    "Shopify":         [("html", r"Shopify\.theme"), ("path", r"cdn\.shopify\.com")],
    "Ghost":           [("html", r'content="Ghost '), ("path", r"/ghost/api/")],
    # Framework
    "Laravel":         [("html", r"laravel_session"), ("path", r"/vendor/laravel/")],
    "Django":          [("html", r"csrfmiddlewaretoken"), ("path", r"/static/admin/")],
    "Ruby on Rails":   [("html", r"authenticity_token"), ("path", r"/assets/application-")],
    "ASP.NET":         [("html", r"__VIEWSTATE"), ("path", r"\.aspx")],
    "Spring Boot":     [("html", r"Whitelabel Error"), ("path", r"/actuator/")],
    # Frontend
    "React":           [("js", r"__reactFiber|React\.createElement|_jsx\("), ("html", r'id="root"')],
    "Vue.js":          [("js", r"Vue\.component|createApp\(|__vue_app__"), ("html", r"v-app|v-bind")],
    "Angular":         [("html", r"ng-version|ng-app"), ("js", r"platformBrowserDynamic")],
    "Next.js":         [("html", r"__NEXT_DATA__"), ("path", r"/_next/static/")],
    "Nuxt.js":         [("html", r"__NUXT__"), ("path", r"/_nuxt/")],
    "jQuery":          [("js", r"jquery[.-](\d[\d.]+)?(\.min)?\.js|jQuery\.fn\.jquery"), ("html", r"jquery")],
    "Bootstrap":       [("path", r"bootstrap[.-](\d[\d.]+)?(\.min)?\.css"), ("html", r'class="(?:container|row|col-)')],
    "Tailwind":        [("html", r'class="[^"]*(?:flex|grid|px-|py-|text-[a-z]+-\d{3})')],
    # Sunucu / dil
    "PHP":             [("path", r"\.php"), ("html", r"PHPSESSID")],
    "Node.js":         [("js", r"require\(['\"]express|http\.createServer")],
    "GraphQL":         [("path", r"/graphql"), ("js", r"gql`|useQuery\(|ApolloClient")],
}

# Hassas dosya yolları
SENSITIVE_PATHS = [
    ".env", ".env.local", ".env.production", ".env.backup",
    ".git/config", ".git/HEAD", ".gitignore",
    "config.php", "wp-config.php", "configuration.php", "settings.php",
    "database.yml", "database.php", "db.php",
    "backup.sql", "dump.sql", "db_backup.sql", "database.sql",
    "config.yml", "config.yaml", "config.json", "secrets.json",
    "id_rsa", "id_dsa", "server.key", "private.key",
    "docker-compose.yml", "docker-compose.yaml",
    "Dockerfile", ".dockerenv",
    "phpinfo.php", "info.php", "test.php", "debug.php",
    "admin/", "administrator/", "phpmyadmin/", "adminer.php",
    "log/", "logs/", "error.log", "access.log",
    "composer.json", "package.json", "requirements.txt", "Gemfile",
    ".htpasswd", ".htaccess",
    "crossdomain.xml", "clientaccesspolicy.xml",
    "web.config", "applicationHost.config",
    "sftp-config.json", "deployment-config.json",
]

# Gizli bilgi regex kalıpları
SECRET_PATTERNS: list[tuple[str, str, str]] = [
    # (isim, regex, örnek_format)
    ("AWS Access Key",       r"AKIA[0-9A-Z]{16}",                                          "AKIAIOSFODNN7EXAMPLE"),
    ("AWS Secret Key",       r'aws.{0,20}secret.{0,20}["\']([A-Za-z0-9/+=]{40})["\']',    "..."),
    ("Google API Key",       r"AIza[0-9A-Za-z\-_]{35}",                                    "AIzaSy..."),
    ("Google OAuth",         r"[0-9]+-[0-9A-Za-z_]{32}\.apps\.googleusercontent\.com",     "..."),
    ("Stripe Live Key",      r"sk_live_[0-9a-zA-Z]{24,}",                                  "sk_live_..."),
    ("Stripe Pub Key",       r"pk_live_[0-9a-zA-Z]{24,}",                                  "pk_live_..."),
    ("GitHub Token",         r"gh[pousr]_[A-Za-z0-9_]{36,}",                               "ghp_..."),
    ("JWT Token",            r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", "eyJ..."),
    ("Private Key",          r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----",              "-----BEGIN..."),
    ("Generic Password",     r'(?i)password["\s]*[=:]["\s]*["\'][^"\']{6,}["\']',          'password="..."'),
    ("Generic Secret",       r'(?i)(?:secret|api_?key|auth_?token|access_?token)["\s]*[=:]["\s]*["\'][A-Za-z0-9_\-]{8,}["\']', "secret=..."),
    ("Basic Auth URL",       r"https?://[^:@\s]+:[^:@\s]+@[^\s]+",                        "https://user:pass@..."),
    ("SendGrid Key",         r"SG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}",              "SG...."),
    ("Slack Token",          r"xox[baprs]-[0-9A-Za-z\-]+",                                 "xoxb-..."),
    ("Twilio Key",           r"SK[0-9a-fA-F]{32}",                                         "SK..."),
    ("Firebase URL",         r"https://[a-z0-9-]+\.firebaseio\.com",                       "https://app.firebaseio.com"),
    ("Mailchimp Key",        r"[0-9a-f]{32}-us[0-9]{1,2}",                                 "abc....-us1"),
]

# Endpoint arama kalıpları
ENDPOINT_PATTERNS = [
    r'(?:url|href|src|action|endpoint|api)\s*[=:]\s*["\']([/][^"\'<>\s]{3,})["\']',
    r'(?:fetch|axios\.(?:get|post|put|delete|patch)|http\.(?:get|post))\s*\(["\']([^"\']{4,})["\']',
    r'["\'](?:\/api\/|\/v\d\/|\/rest\/|\/graphql)[^"\'<>\s]*["\']',
    r'(?:route|path|endpoint)\s*[:=]\s*["\']([^"\']{4,})["\']',
]

# İç ağ IP kalıpları
INTERNAL_IP_RE = re.compile(
    r'\b(?:192\.168\.\d{1,3}\.\d{1,3}'
    r'|10\.\d{1,3}\.\d{1,3}\.\d{1,3}'
    r'|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}'
    r'|127\.0\.0\.\d{1,3}'
    r'|localhost)\b'
)
EMAIL_RE    = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
PHONE_RE    = re.compile(r'(?:\+90|0)[\s\-]?[2-5]\d{2}[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}')
COMMENT_RE  = re.compile(r'<!--(.*?)-->', re.DOTALL)


class Finding:
    """Tek bir analiz bulgusu."""
    __slots__ = ("category", "severity", "file", "line", "detail")

    SEVERITY_ORDER = {"KRİTİK": 0, "YÜKSEK": 1, "ORTA": 2, "DÜŞÜK": 3, "BİLGİ": 4}
    SEVERITY_COLOR = {
        "KRİTİK": "bold red",
        "YÜKSEK": "red",
        "ORTA":   "yellow",
        "DÜŞÜK":  "cyan",
        "BİLGİ":  "dim",
    }

    def __init__(self, category: str, severity: str, file: str, detail: str, line: int = 0):
        self.category = category
        self.severity = severity
        self.file     = file
        self.line     = line
        self.detail   = detail


class MirrorAnalyzer:
    """
    Mirror dizinindeki dosyaları tamamen yerel olarak analiz eder.
    Hedefe hiçbir HTTP isteği atmaz.
    """

    def __init__(self, mirror_dir: Path, report_file: Path | None = None):
        self.mirror_dir  = mirror_dir.resolve()
        self.report_file = report_file
        self.findings: list[Finding] = []
        self.techs: set[str] = set()
        self.endpoints: set[str] = set()
        self.emails: set[str] = set()
        self.phones: set[str] = set()
        self.ips: set[str] = set()
        self._file_count = 0

    # ── Yardımcı ────────────────────────────────────────────────────────────

    def _add(self, category: str, severity: str, file: Path, detail: str, line: int = 0):
        rel = str(file.relative_to(self.mirror_dir))
        self.findings.append(Finding(category, severity, rel, detail, line))

    def _read_text(self, path: Path) -> str:
        for enc in ("utf-8", "latin-1"):
            try:
                return path.read_text(encoding=enc, errors="replace")
            except Exception:
                pass
        return ""

    # ── Tarayıcılar ─────────────────────────────────────────────────────────

    def _scan_sensitive_files(self):
        """Mirror'da hassas dosya yollarını ara."""
        for rel in SENSITIVE_PATHS:
            target = self.mirror_dir / rel
            if target.exists():
                severity = "KRİTİK" if any(x in rel for x in (
                    ".env", "config", "password", "secret", "id_rsa",
                    "backup", ".sql", "htpasswd", "private.key",
                )) else "YÜKSEK"
                self._add("Hassas Dosya", severity, target, f"Erişilebilir: {rel}")

    def _scan_technologies(self, path: Path, content: str, is_js: bool):
        """Teknoloji imzalarını tespit et."""
        rel = str(path.relative_to(self.mirror_dir))
        for tech, sigs in TECH_SIGNATURES.items():
            if tech in self.techs:
                continue
            for scope, pattern in sigs:
                if scope == "path" and re.search(pattern, rel, re.I):
                    self.techs.add(tech)
                    break
                elif scope == "html" and not is_js and re.search(pattern, content, re.I):
                    self.techs.add(tech)
                    break
                elif scope == "js" and is_js and re.search(pattern, content):
                    self.techs.add(tech)
                    break

    def _scan_secrets(self, path: Path, content: str):
        """Gizli anahtar ve credential kalıplarını ara."""
        for name, pattern, _ in SECRET_PATTERNS:
            for m in re.finditer(pattern, content):
                line_no = content[:m.start()].count("\n") + 1
                snippet = m.group(0)[:80].replace("\n", " ")
                severity = "KRİTİK" if any(x in name for x in (
                    "AWS", "Private Key", "Stripe Live", "GitHub"
                )) else "YÜKSEK"
                self._add("Gizli Bilgi", severity, path, f"{name}: {snippet}", line_no)

    def _scan_endpoints(self, path: Path, content: str):
        """Gömülü API endpoint ve yollarını çıkar."""
        for pattern in ENDPOINT_PATTERNS:
            for m in re.finditer(pattern, content, re.I):
                ep = m.group(1) if m.lastindex else m.group(0).strip("\"'")
                ep = ep.strip()
                if ep and len(ep) > 3 and ep not in self.endpoints:
                    self.endpoints.add(ep)

    def _scan_html(self, path: Path, content: str):
        """HTML dosyasını analiz et."""
        soup = BeautifulSoup(content, "lxml")

        # Form analizi
        for form in soup.find_all("form"):
            method  = (form.get("method") or "GET").upper()
            action  = form.get("action", "(mevcut sayfa)")
            fields  = form.find_all("input")

            hidden  = [f for f in fields if f.get("type", "").lower() == "hidden"]
            has_csrf = any(
                re.search(r"csrf|token|nonce|_token", f.get("name", "") or f.get("id", ""), re.I)
                for f in fields
            )
            has_file = any(f.get("type", "").lower() == "file" for f in fields)

            detail = f'method={method} action="{action}"'
            if hidden:
                names = [f.get("name", "?") for f in hidden]
                detail += f" | hidden=[{', '.join(names)}]"
            if not has_csrf and method == "POST":
                detail += " | ⚠ CSRF TOKEN YOK"
                self._add("Form", "ORTA", path, detail)
            else:
                self._add("Form", "BİLGİ", path, detail)

            if has_file:
                self._add("Form", "ORTA", path,
                          f'Dosya yükleme formu: action="{action}"')

        # HTML yorum satırları
        for m in COMMENT_RE.finditer(content):
            comment = m.group(1).strip()
            if len(comment) < 4:
                continue
            # Credential içerebilecek yorumlar
            if re.search(r'(?i)(password|passwd|secret|token|key|todo|fixme|hack|debug|admin|credentials?)', comment):
                snippet = comment[:120].replace("\n", " ")
                self._add("Yorum Sızıntısı", "ORTA", path, f"<!-- {snippet} -->")
            # İç IP içeren yorumlar
            for ip in INTERNAL_IP_RE.findall(comment):
                self.ips.add(ip)

        # E-posta
        for email in EMAIL_RE.findall(content):
            if not email.endswith((".png", ".jpg", ".svg", ".css", ".js")):
                self.emails.add(email)

        # Telefon (TR formatı)
        for phone in PHONE_RE.findall(content):
            self.phones.add(phone)

        # İç IP (tüm HTML'de)
        for ip in INTERNAL_IP_RE.findall(content):
            self.ips.add(ip)

        # Meta generator
        gen = soup.find("meta", {"name": re.compile("generator", re.I)})
        if gen and gen.get("content"):
            self._add("Teknoloji", "BİLGİ", path, f"Meta generator: {gen['content']}")

        # Script src'leri endpoint olarak kaydet
        for tag in soup.find_all("script", src=True):
            src = tag["src"]
            if src.startswith("/") or src.startswith("http"):
                self.endpoints.add(src)

    def _scan_js(self, path: Path, content: str):
        """JavaScript dosyasını analiz et."""
        self._scan_secrets(path, content)
        self._scan_endpoints(path, content)
        self._scan_technologies(path, content, is_js=True)

        # İç IP
        for ip in INTERNAL_IP_RE.findall(content):
            self.ips.add(ip)

        # Yorum satırı içindeki sızıntılar
        for m in re.finditer(r'//\s*(.+)', content):
            line = m.group(1)
            if re.search(r'(?i)(password|secret|token|key|todo\s*:\s*auth|debug|credentials?)', line):
                snippet = line[:100]
                self._add("Yorum Sızıntısı", "DÜŞÜK", path, f"// {snippet}")

        # Console.log içindeki hassas bilgiler
        for m in re.finditer(r'console\.(log|warn|error|debug)\s*\(([^)]{10,})\)', content):
            args = m.group(2)
            if re.search(r'(?i)(password|token|secret|key|auth)', args):
                self._add("Debug Kodu", "DÜŞÜK", path,
                          f"console.{m.group(1)}({args[:80]})")

    def _scan_config_files(self, path: Path, content: str):
        """JSON/YAML/ENV config dosyalarını analiz et."""
        self._scan_secrets(path, content)
        for ip in INTERNAL_IP_RE.findall(content):
            self.ips.add(ip)
        for email in EMAIL_RE.findall(content):
            self.emails.add(email)

    # ── Ana akış ────────────────────────────────────────────────────────────

    def run(self) -> list[Finding]:
        console.print(Panel.fit(
            f"[bold cyan]Mirror Analizi Başlıyor[/bold cyan]\n"
            f"[white]Dizin:[/white] [yellow]{self.mirror_dir}[/yellow]",
            border_style="magenta",
        ))

        # 1. Hassas dosya taraması
        self._scan_sensitive_files()

        # 2. Dosya bazlı tarama
        all_files = list(self.mirror_dir.rglob("*"))
        scannable  = [f for f in all_files if f.is_file()]
        self._file_count = len(scannable)

        progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold magenta]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("• {task.completed}/{task.total} dosya"),
            TimeElapsedColumn(),
            console=console,
        )

        with progress:
            task = progress.add_task("Taranıyor...", total=len(scannable))
            for path in scannable:
                progress.advance(task)
                suffix = path.suffix.lower()

                if suffix in (".html", ".htm", ".xhtml", ".shtml"):
                    content = self._read_text(path)
                    self._scan_technologies(path, content, is_js=False)
                    self._scan_html(path, content)
                    self._scan_secrets(path, content)

                elif suffix in (".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx"):
                    content = self._read_text(path)
                    self._scan_js(path, content)

                elif suffix in (".css",):
                    content = self._read_text(path)
                    self._scan_technologies(path, content, is_js=False)
                    for ip in INTERNAL_IP_RE.findall(content):
                        self.ips.add(ip)

                elif suffix in (".json", ".yaml", ".yml", ".env", ".ini", ".conf", ".config", ".xml", ".toml"):
                    content = self._read_text(path)
                    self._scan_config_files(path, content)

                elif suffix in (".php", ".py", ".rb", ".java", ".go", ".cs"):
                    content = self._read_text(path)
                    self._scan_secrets(path, content)

        self._print_report()

        if self.report_file:
            self._save_json_report()

        return self.findings

    # ── Rapor ───────────────────────────────────────────────────────────────

    def _print_report(self):
        console.print()

        # ── Teknoloji tespiti
        if self.techs:
            t = Table(box=box.SIMPLE, title="[bold]Tespit Edilen Teknolojiler[/bold]",
                      border_style="cyan", show_header=False)
            t.add_column("Tech", style="bold green")
            for tech in sorted(self.techs):
                t.add_row(tech)
            console.print(t)

        # ── Bulgular (severity'ye göre sıralı)
        severity_order = Finding.SEVERITY_ORDER
        grouped: dict[str, list[Finding]] = {}
        for f in sorted(self.findings, key=lambda x: severity_order.get(x.severity, 9)):
            grouped.setdefault(f.category, []).append(f)

        if self.findings:
            t = Table(
                box=box.ROUNDED,
                title="[bold]Analiz Bulguları[/bold]",
                border_style="magenta",
                show_lines=True,
            )
            t.add_column("Önem",      style="bold", no_wrap=True, width=10)
            t.add_column("Kategori",  style="bold cyan", no_wrap=True)
            t.add_column("Dosya",     style="dim", max_width=40)
            t.add_column("Detay",     max_width=60)

            for f in sorted(self.findings, key=lambda x: (severity_order.get(x.severity, 9), x.file)):
                color = Finding.SEVERITY_COLOR.get(f.severity, "white")
                line_info = f":{f.line}" if f.line else ""
                t.add_row(
                    f"[{color}]{f.severity}[/{color}]",
                    f.category,
                    f"{f.file}{line_info}",
                    f.detail,
                )
            console.print(t)
        else:
            console.print("[green]Bulgu bulunamadı.[/green]")

        # ── Endpoint'ler
        if self.endpoints:
            ep_sorted = sorted(self.endpoints)[:50]
            t = Table(box=box.SIMPLE, title=f"[bold]Keşfedilen Endpoint'ler[/bold] ({len(self.endpoints)} adet)",
                      border_style="blue", show_header=False)
            t.add_column("EP", style="cyan")
            for ep in ep_sorted:
                t.add_row(ep)
            if len(self.endpoints) > 50:
                t.add_row(f"[dim]... ve {len(self.endpoints)-50} tane daha[/dim]")
            console.print(t)

        # ── Kişisel bilgiler
        info_parts = []
        if self.emails:
            info_parts.append(f"E-posta: [yellow]{', '.join(sorted(self.emails)[:10])}[/yellow]")
        if self.phones:
            info_parts.append(f"Telefon: [yellow]{', '.join(sorted(self.phones)[:5])}[/yellow]")
        if self.ips:
            info_parts.append(f"İç IP: [red]{', '.join(sorted(self.ips)[:10])}[/red]")

        if info_parts:
            console.print(Panel(
                "\n".join(info_parts),
                title="[bold]Sızdırılan Bilgiler[/bold]",
                border_style="yellow",
            ))

        # ── Özet
        counts = {}
        for f in self.findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1

        summary_parts = [f"[bold]Taranan:[/bold] {self._file_count} dosya"]
        for sev in ("KRİTİK", "YÜKSEK", "ORTA", "DÜŞÜK", "BİLGİ"):
            if sev in counts:
                color = Finding.SEVERITY_COLOR[sev]
                summary_parts.append(f"[{color}]{sev}: {counts[sev]}[/{color}]")

        console.print(Panel(" | ".join(summary_parts), border_style="green"))

        if self.report_file:
            console.print(f"\n[green]Rapor kaydedildi:[/green] {self.report_file}")

    def _save_json_report(self):
        import json
        data = {
            "mirror_dir": str(self.mirror_dir),
            "technologies": sorted(self.techs),
            "emails": sorted(self.emails),
            "phones": sorted(self.phones),
            "internal_ips": sorted(self.ips),
            "endpoints": sorted(self.endpoints),
            "findings": [
                {
                    "category": f.category,
                    "severity": f.severity,
                    "file": f.file,
                    "line": f.line,
                    "detail": f.detail,
                }
                for f in sorted(self.findings,
                                key=lambda x: Finding.SEVERITY_ORDER.get(x.severity, 9))
            ],
        }
        self.report_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )


# ────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spectre",
        description="Spectre — website mirroring & passive recon tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python3 spectre.py https://example.com
  python3 spectre.py https://example.com -o ./mirror -d 3 -t 8 --analyze
  python3 spectre.py https://example.com --stealth --decoy --analyze --report out.json
  python3 spectre.py --analyze-only ./mirror_dizini
        """,
    )

    parser.add_argument("url", nargs="?", help="İndirilecek sitenin URL'si")

    io_group = parser.add_argument_group("Çıktı seçenekleri")
    io_group.add_argument("-o", "--output", metavar="DİZİN",
                          help="Çıktı dizini (varsayılan: alan adı)")
    io_group.add_argument("--log", metavar="DOSYA",
                          help="İşlem logunu dosyaya yaz")
    io_group.add_argument("-v", "--verbose", action="store_true",
                          help="Ayrıntılı çıktı")

    crawl_group = parser.add_argument_group("Tarama seçenekleri")
    crawl_group.add_argument("-d", "--depth", type=int, default=5, metavar="N",
                              help="Maksimum bağlantı derinliği (varsayılan: 5)")
    crawl_group.add_argument("-t", "--threads", type=int, default=4, metavar="N",
                              help="Eşzamanlı indirme thread sayısı (varsayılan: 4)")
    crawl_group.add_argument("--delay", type=float, default=0.0, metavar="SN",
                              help="İstekler arası gecikme saniye (varsayılan: 0)")
    crawl_group.add_argument("--timeout", type=int, default=30, metavar="SN",
                              help="İstek zaman aşımı saniye (varsayılan: 30)")
    crawl_group.add_argument("--video-timeout", type=int, default=3600, metavar="SN",
                              help="Video indirme zaman aşımı saniye (varsayılan: 3600)")
    crawl_group.add_argument("--max-size", type=int, metavar="MB",
                              help="Maksimum dosya boyutu MB (varsayılan: sınırsız)")
    crawl_group.add_argument("--allow-external", action="store_true",
                              help="Farklı domainlerdeki linkleri de takip et")
    crawl_group.add_argument("--no-robots", action="store_true",
                              help="robots.txt kurallarını yoksay")
    crawl_group.add_argument("--no-videos", action="store_true",
                              help="Video ve ses dosyalarını atla")

    filter_group = parser.add_argument_group("Filtre seçenekleri")
    filter_group.add_argument("--include", metavar="REGEX",
                               help="Sadece bu desene uyan URL'leri indir")
    filter_group.add_argument("--exclude", metavar="REGEX",
                               help="Bu desene uyan URL'leri atla")

    req_group = parser.add_argument_group("İstek seçenekleri")
    req_group.add_argument("--user-agent", metavar="UA",
                            help="Özel User-Agent başlığı")

    anon_group = parser.add_argument_group("Gizlilik seçenekleri")
    anon_group.add_argument("--stealth", action="store_true",
                             help="Stealth modu: UA rotasyonu, gerçekçi başlıklar, insan benzeri gecikmeler")
    anon_group.add_argument("--decoy", action="store_true",
                             help="Decoy modu: gerçek istekler arasına zararsız tuzak istekler karıştır")
    anon_group.add_argument("--decoy-ratio", type=int, default=5, metavar="N",
                             help="Her N istekte 1 decoy gönder (varsayılan: 5)")

    analyze_group = parser.add_argument_group("Analiz seçenekleri")
    analyze_group.add_argument("--analyze", action="store_true",
                                help="Mirror bittikten sonra otomatik pasif analiz yap")
    analyze_group.add_argument("--analyze-only", metavar="DİZİN",
                                help="Sadece mevcut bir mirror dizinini analiz et (indirme yapma)")
    analyze_group.add_argument("--report", metavar="DOSYA",
                                help="Analiz raporunu JSON dosyasına kaydet")

    parser.add_argument("--version", action="version", version=f"Spectre {VERSION}")

    return parser


def main():
    print_banner()

    parser = build_parser()

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    report_path = Path(args.report) if args.report else None

    # ── Sadece analiz modu ───────────────────────────────────────────────────
    if args.analyze_only:
        mirror_dir = Path(args.analyze_only)
        if not mirror_dir.is_dir():
            console.print(f"[red]Hata: Dizin bulunamadı: {mirror_dir}[/red]")
            sys.exit(1)
        try:
            MirrorAnalyzer(mirror_dir, report_path).run()
        except KeyboardInterrupt:
            console.print("\n[yellow]⚠ Analiz durduruldu.[/yellow]\n")
            sys.exit(130)
        sys.exit(0)

    # ── Normal mirror modu ───────────────────────────────────────────────────
    if not args.url:
        parser.print_help()
        sys.exit(0)

    if not args.url.startswith(("http://", "https://")):
        args.url = "https://" + args.url

    try:
        mirror = Spectre(args)
        mirror.run()

        # Mirror bittikten sonra analiz
        if args.analyze:
            console.print()
            MirrorAnalyzer(mirror.output_dir, report_path).run()

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ İndirme kullanıcı tarafından durduruldu.[/yellow]\n")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]Hata: {e}[/red]\n")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
