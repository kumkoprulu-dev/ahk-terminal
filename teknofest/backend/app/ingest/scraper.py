"""Web kazıma — katılım bankası sayfalarından temiz metin.

Gerçek banka sayfaları menü/breadcrumb/footer gürültüsüyle doludur ve oran
bilgisi ana içerik bölgesindedir. Bu modül:
  * tarayıcı UA ile httpx (bazı bankalar varsayılan istemciyi 404'ler),
  * <title>/<h1> başlığını ayrı yakalar (ürün adı için),
  * nav/breadcrumb/menu/footer gibi gürültü kapsayıcılarını ayıklar,
  * ana içeriği paragraf metnine indirger.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Gürültü kabı sınıf/id kalıpları — fazla geniş eşleşmeyi önlemek için
# spesifik tutuldu (ör. "nav" yerine "navbar"; aksi halde "navigation"/içerik ezilir)
_NOISE_HINTS = (
    "breadcrumb", "mega-menu", "megamenu", "main-menu", "mainmenu", "top-menu",
    "navbar", "site-header", "site-footer", "cookie", "kvkk", "newsletter",
    "modal", "popup", "offcanvas", "skip-link",
)


@dataclass
class Table:
    caption: str
    headers: list[str]
    rows: list[list[str]]

    def to_markdown(self) -> str:
        out = []
        if self.caption:
            out.append(f"**{self.caption}**")
        if self.headers:
            out.append("| " + " | ".join(self.headers) + " |")
            out.append("| " + " | ".join("---" for _ in self.headers) + " |")
        for r in self.rows:
            out.append("| " + " | ".join(r) + " |")
        return "\n".join(out)


@dataclass
class Page:
    url: str
    title: str = ""
    text: str = ""
    ok: bool = False
    status: int | None = None
    chunks: list[str] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)


def fetch_page(url: str, timeout: float = 20.0) -> Page:
    """URL'yi çek, başlık + temiz ana metni döndür."""
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": _UA}) as c:
            r = c.get(url)
            status = r.status_code
            html = r.text if r.status_code == 200 else ""
    except Exception:
        return Page(url=url, ok=False, status=None)
    if not html:
        return Page(url=url, ok=False, status=status)
    title, text, chunks, tables = _parse(html)
    return Page(url=url, title=title, text=text, chunks=chunks, tables=tables,
                ok=bool(text), status=status)


def fetch_clean(url: str, timeout: float = 20.0) -> str:
    """Geriye-uyumlu: yalnız temiz metni döndür."""
    return fetch_page(url, timeout).text


def render_page(url: str, timeout_ms: int = 30000) -> Page:
    """JS-SPA sayfalarını Playwright ile RENDER edip çıkar.

    Playwright kurulu değilse veya hata olursa boş Page döner (çağıran taraf
    örnek-fallback'e düşer). httpx içerik vermeyen bankalar (ör. Emlak) için.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return Page(url=url, ok=False, status=None)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            pg = browser.new_page(user_agent=_UA)
            pg.goto(url, timeout=timeout_ms, wait_until="networkidle")
            html = pg.content()
            browser.close()
    except Exception:
        return Page(url=url, ok=False, status=None)
    title, text, chunks, tables = _parse(html)
    return Page(url=url, title=title, text=text, chunks=chunks, tables=tables,
                ok=bool(text), status=200)


def _is_noise(el) -> bool:
    attrs = getattr(el, "attrs", None)
    if not attrs:
        return False
    cls = attrs.get("class") or []
    ident = " ".join(str(v) for v in cls)
    ident += " " + str(attrs.get("id") or "") + " " + str(attrs.get("role") or "")
    ident = ident.lower()
    return any(h in ident for h in _NOISE_HINTS)


def _extract_tables(soup) -> list[Table]:
    """HTML <table>'larını yapısal çıkar (başlık + sütun + satırlar)."""
    out: list[Table] = []
    for t in soup.find_all("table"):
        trs = t.find_all("tr")
        if not trs:
            continue
        grid: list[list[str]] = []
        for tr in trs:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            if any(cells):
                grid.append(cells)
        if not grid:
            continue
        # Caption: <caption> ya da tek-hücreli ilk satır (başlık görevi gören)
        caption = ""
        cap = t.find("caption")
        if cap and cap.get_text(strip=True):
            caption = cap.get_text(" ", strip=True)
        elif len(grid[0]) == 1:
            caption = grid[0][0]
            grid = grid[1:]
        headers = grid[0] if grid else []
        rows = grid[1:] if len(grid) > 1 else []
        out.append(Table(caption=caption, headers=headers, rows=rows))
    return out


def _parse(html: str) -> tuple[str, str, list[str], list[Table]]:
    soup = BeautifulSoup(html, "lxml")
    tables = _extract_tables(soup)

    # Başlık: <title> ya da ilk <h1>
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        title = h1.get_text(" ", strip=True)
    # "| Kuveyt Türk" gibi son ekleri kırp
    for sep in ("|", " - ", "—"):
        if sep in title:
            title = title.split(sep)[0].strip()

    # Sert gürültüyü kaldır. NOT: <form> KALDIRILMAZ — ASP.NET WebForms siteleri
    # (ör. Türkiye Finans) tüm sayfayı tek <form> içine sarar; silinirse içerik gider.
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "svg"]):
        tag.decompose()
    # Sınıf/rol ipucuyla gürültü kaplarını kaldır
    for el in soup.find_all(True):
        if _is_noise(el):
            el.decompose()

    # Ana içerik adayı: main/article yeterince doluysa onu, değilse body kullan.
    def _collect(root) -> list[str]:
        out = []
        for el in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th", "dt", "dd", "span"]):
            txt = el.get_text(" ", strip=True)
            if txt and len(txt) > 2:
                out.append(txt)
        return out

    body_chunks = _collect(soup.body or soup)
    chunks = body_chunks
    for cand in (soup.find("main"), soup.find("article"), soup.find(attrs={"role": "main"})):
        if cand is not None:
            cc = _collect(cand)
            # Yalnız ana içerik gövdenin önemli kısmını taşıyorsa tercih et
            if len("\n".join(cc)) > 300 and len("\n".join(cc)) > 0.4 * len("\n".join(body_chunks)):
                chunks = cc
                break

    # Sıra koruyarak tekrarı ele
    seen: set[str] = set()
    out: list[str] = []
    for c in chunks:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return title, "\n".join(out), out, tables


def clean_html(html: str) -> str:
    return _parse(html)[1]
