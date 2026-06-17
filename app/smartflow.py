import os
import threading
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

_EPAPER_BASE = "https://epaper.esakal.com/smartepaper/ui/home.aspx"

# Location code → epaper city name as used in the epaper URL
_LOCATION_TO_CITY: dict[str, str] = {
    "PNE": "Pune", "MBI": "Mumbai", "MBRU": "Mumbai", "MUM": "Mumbai",
    "NGP": "Nagpur", "NSK": "Nashik", "DEL": "Delhi", "KOP": "Kolhapur",
    "AUR": "Aurangabad", "SRT": "Surat", "NWC": "Nandurbar",
    "AMR": "Amravati", "LTR": "Latur", "SLR": "Solapur", "ALB": "Alibag",
    "JLN": "Jalna", "SNG": "Sangli", "SAT": "Satara", "KLH": "Kolhapur",
    "CHN": "Chandrapur", "AKL": "Akola", "BHR": "Bhandara", "NND": "Nanded",
    "OSM": "Osmanabad", "BLR": "Buldhana", "WAR": "Wardha", "YTM": "Yavatmal",
    "GND": "Gondia", "GDH": "Gadchiroli", "RJR": "Rajapur",
}

def _epaper_url(location: str, date_id: str, page: str = "") -> str:
    city = _LOCATION_TO_CITY.get(location[:3] if len(location) > 3 else location)
    if not city:
        city = _LOCATION_TO_CITY.get(location)
    if city and len(date_id) >= 8:
        formatted = f"{date_id[:4]}-{date_id[4:6]}-{date_id[6:8]}"
        url = f"{_EPAPER_BASE}?q={city}/Main/{formatted}"
        if page and page.isdigit():
            url += f"/{page}"
        return url
    return _EPAPER_BASE


_index: list[dict] = []
_index_ready = threading.Event()
_index_lock = threading.Lock()


def _date_to_ms(date_str: str) -> int:
    try:
        dt = datetime.strptime(date_str.strip()[:8], "%Y%m%d").replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except Exception:
        return 0


def _parse_file(path: str) -> dict | None:
    try:
        tree = ET.parse(path)
        root = tree.getroot()

        basename = os.path.basename(path)
        parts = basename.split("_")
        file_date = parts[0].replace("-", "") if parts else ""
        story_id = parts[1] if len(parts) > 1 else basename

        news_item = root.find("NewsItem")
        if news_item is None:
            return None

        # Date from NewsManagement > FirstCreated
        date_id = file_date
        news_mgmt = news_item.find("NewsManagement")
        if news_mgmt is not None:
            fc = news_mgmt.find("FirstCreated")
            if fc is not None and fc.text:
                date_id = fc.text.strip()

        # Structure: NewsComponent > NewsComponent[xml:lang] > NewsComponent > content
        outer = news_item.find("NewsComponent")
        if outer is None:
            return None
        lang_comp = outer.find("NewsComponent")
        if lang_comp is None:
            return None
        inner = lang_comp.find("NewsComponent")
        if inner is None:
            return None

        headline = ""
        body = ""
        edition = ""
        page = ""

        news_lines = inner.find("NewsLines")
        if news_lines is not None:
            hl = news_lines.find("HeadLine")
            if hl is not None and hl.text:
                headline = hl.text.strip()

        admin = inner.find("AdministrativeMetadata")
        if admin is not None:
            for prop in admin.findall("Property"):
                fname = prop.get("FormalName", "")
                if fname == "Location":
                    edition = prop.get("Value", "")
                elif fname == "Edition" and not edition:
                    edition = prop.get("Value", "")
                elif fname == "PageNumber":
                    page = prop.get("Value", "")

        content_item = inner.find("ContentItem")
        if content_item is not None:
            dc = content_item.find("DataContent")
            if dc is not None and dc.text:
                body = dc.text.strip()

        if not headline and not body:
            return None

        # Strip audit trailer appended to some bodies
        if "Associated Media Ids" in body:
            body = body[:body.index("Associated Media Ids")].strip()

        pub_ms = _date_to_ms(date_id)
        return {
            "id": story_id,
            "headline": headline,
            "published-at": pub_ms,
            "slug": story_id.lower(),
            "url": _epaper_url(edition, date_id, page),
            "_body": body,
            "_edition": edition,
            "_page": page,
            "_source": "print",
            "access": "public",
        }
    except Exception as e:
        print(f"[smartflow] parse error {path}: {e}")
        return None


def _build_index(xml_dir: str) -> None:
    files = list(Path(xml_dir).rglob("*.xml"))
    print(f"[smartflow] Found {len(files)} XML files in {xml_dir}")
    articles: list[dict] = []
    for f in [str(f) for f in files]:
        article = _parse_file(f)
        if article:
            articles.append(article)
    articles.sort(key=lambda a: a.get("published-at", 0), reverse=True)
    with _index_lock:
        global _index
        _index = articles
    _index_ready.set()
    print(f"[smartflow] Indexed {len(articles)} print articles")


def _load_from_url(url: str) -> None:
    import json as _json
    import urllib.request as _req
    print(f"[smartflow] downloading index from {url}")
    try:
        with _req.urlopen(url, timeout=120) as r:
            articles = _json.loads(r.read().decode("utf-8"))
        articles.sort(key=lambda a: a.get("published-at", 0), reverse=True)
        with _index_lock:
            global _index
            _index = articles
        _index_ready.set()
        print(f"[smartflow] loaded {len(articles)} print articles from URL")
    except Exception as e:
        print(f"[smartflow] failed to load index from URL: {e}")


def init(xml_dir: str, index_url: str = "") -> None:
    if index_url:
        t = threading.Thread(target=_load_from_url, args=(index_url,), daemon=True)
        t.start()
        return
    print(f"[smartflow] init called with dir: {xml_dir!r}")
    if not xml_dir or not os.path.isdir(xml_dir):
        print(f"[smartflow] XML dir not found, skipping: {xml_dir!r}")
        return
    t = threading.Thread(target=_build_index, args=(xml_dir,), daemon=True)
    t.start()


def is_ready() -> bool:
    return _index_ready.is_set()


def search(query: str, limit: int = 5) -> list[dict]:
    if not _index_ready.is_set():
        _index_ready.wait(timeout=1.0)
        if not _index_ready.is_set():
            return []

    words = [w.lower() for w in query.split() if len(w) > 1]
    if not words:
        return []

    with _index_lock:
        articles = _index[:]

    scored: list[tuple[int, int, dict]] = []
    for article in articles:
        hl = article.get("headline", "").lower()
        body = article.get("_body", "").lower()
        score = sum(hl.count(w) * 3 + body.count(w) for w in words)
        if score > 0:
            scored.append((score, article.get("published-at", 0), article))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [a for _, _, a in scored[:limit]]
