"""
linker.py — Tự động chèn Internal Link (liên kết nội bộ) chuẩn SEO.

- Quét danh sách bài viết/sản phẩm trên website (WP REST API + sitemap.xml), có cache 6h.
- Với mỗi bài viết mới: tìm 2-5 cụm từ khớp tự nhiên và bọc thành
    <a href="URL" title="Tên bài viết">Từ khóa trong bài</a>
- QUY TẮC AN TOÀN:
    * Mỗi URL chỉ chèn tối đa 1 lần.
    * Không chèn vào thẻ tiêu đề <h1>..<h6>.
    * Không chèn chồng lên liên kết đã có (tránh <a> lồng <a>), không chèn trong <script>/<style>.
    * Neo text tự nhiên, không phá vỡ từ.
"""
import json
import os
import re
import time
import unicodedata

import requests
from bs4 import BeautifulSoup, NavigableString

SITE = os.environ.get("INTERNAL_LINK_SITE", "https://hieutaphoa.com")
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".linker_cache.json")
CACHE_TTL = int(os.environ.get("INTERNAL_LINK_CACHE_TTL", str(6 * 3600)))
MIN_LINKS = 2
MAX_LINKS = 5
SKIP_PARENTS = {"script", "style", "a", "h1", "h2", "h3", "h4", "h5", "h6", "title"}
STOPWORDS = {"cách", "tại", "của", "và", "là", "cho", "với", "trên", "theo", "sau",
             "khi", "này", "đó", "một", "những", "các", "để", "từ", "trong", "bởi",
             "có", "được", "không", "nếu", "hay", "như", "bạn", "tôi", "nên"}

_cache = {"links": None, "fetched_at": 0}


# ============================================================
# 1) LẤY DANH SÁCH BÀI VIẾT / SẢN PHẨM TRÊN WEBSITE
# ============================================================
def _clean_title(t):
    t = re.sub(r"<[^>]+>", "", t or "")
    t = re.sub(r"\s*[-–|·/:]\s*(HieuTapHoa|hieutaphoa|Trang chủ).*$", "", t)
    t = re.sub(r"\s+", " ", t).strip(" .,;:-|")
    return t


def _fetch_wp_links(site):
    """Lấy link + title chuẩn từ WP REST API (posts + pages)."""
    links = []
    for ept in ("wp/v2/posts", "wp/v2/pages"):
        for page in (1, 2):
            try:
                r = requests.get(f"{site}/wp-json/{ept}",
                                 params={"per_page": 100, "page": page, "_fields": "link,title"},
                                 timeout=12, headers={"User-Agent": "WPAutoPosterPRO/1.0"})
                if r.status_code != 200:
                    break
                data = r.json()
                if not data:
                    break
                for d in data:
                    t = _clean_title((d.get("title") or {}).get("rendered", ""))
                    link = (d.get("link") or "").strip()
                    if t and link and link not in {x["url"] for x in links}:
                        links.append({"title": t, "url": link})
                if len(data) < 100:
                    break
            except Exception:
                break
    return links


def _sitemap_locs(url, depth=0):
    """Đệ quy đọc sitemap.xml (+ sitemap index + sitemaps con)."""
    locs = []
    if depth > 3:
        return locs
    try:
        r = requests.get(url, timeout=12, headers={"User-Agent": "WPAutoPosterPRO/1.0"})
        if r.status_code != 200:
            return locs
        text = r.text
        if "<sitemapindex" in text:
            for m in re.finditer(r"<loc>\s*(.*?)\s*</loc>", text, re.I):
                locs.extend(_sitemap_locs(m.group(1).strip(), depth + 1))
        elif "<urlset" in text:
            for m in re.finditer(r"<loc>\s*(.*?)\s*</loc>", text, re.I):
                locs.append(m.group(1).strip())
    except Exception:
        pass
    return locs


def _slug_title(url):
    slug = re.sub(r"^https?://[^/]+/?", "", url).strip("/").rsplit("/", 1)[-1]
    slug = re.sub(r"[-_+]+", " ", slug).strip()
    return slug[:90] if slug else url


def _load_file_cache():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if time.time() - data.get("fetched_at", 0) < CACHE_TTL and data.get("links"):
                _cache["links"] = data["links"]
                _cache["fetched_at"] = data["fetched_at"]
    except Exception:
        pass


def get_site_links(refresh=False):
    """Trả về [{'title','url'}] các bài viết/sản phẩm trên site. Có cache 6h + cache file."""
    now = time.time()
    if not refresh and _cache["links"] and now - _cache["fetched_at"] < CACHE_TTL:
        return _cache["links"]
    links = []
    try:
        links = _fetch_wp_links(SITE)
    except Exception:
        links = []
    if len(links) < 10:
        try:
            seen = {x["url"] for x in links}
            for loc in _sitemap_locs(f"{SITE}/sitemap.xml"):
                if loc in seen:
                    continue
                seen.add(loc)
                links.append({"title": _slug_title(loc), "url": loc})
        except Exception:
            pass
    _cache["links"] = links
    _cache["fetched_at"] = now
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"fetched_at": now, "links": links}, f, ensure_ascii=False)
    except Exception:
        pass
    return links


_load_file_cache()


# ============================================================
# 2) CHÈN INTERNAL LINK
# ============================================================
def _candidate_phrases(title):
    """Từ title tạo các cụm từ khớp (2-4 từ), ưu tiên cụm dài nhất trước.
    Nếu title ngắn (<=6 từ) thì chính title đầy đủ được ưu tiên đầu tiên."""
    words = [w for w in re.split(r"\s+", title) if len(w) >= 2]
    phrases = []
    if 2 <= len(words) <= 6 and not _all_stopwords(" ".join(words)):
        phrases.append(" ".join(words))
    for n in range(min(4, len(words)), 1, -1):  # chỉ cụm >= 2 từ
        for i in range(len(words) - n + 1):
            p = " ".join(words[i:i + n])
            if p not in phrases and not _all_stopwords(p):
                phrases.append(p)
    return phrases


def _block_subphrases(used, phrase):
    """Chặn luôn các cụm con của phrase đã dùng để anchor không bị trùng lặp/đè nhau.
    Lưu theo dạng chuẩn hoá (không dấu) để chặn đúng."""
    words = _normalize(phrase).split()
    used.add(_normalize(phrase))
    for n in range(1, len(words)):
        for i in range(len(words) - n + 1):
            used.add(" ".join(words[i:i + n]))


def _all_stopwords(p):
    ws = [w for w in p.lower().split() if w]
    return bool(ws) and all(w in STOPWORDS for w in ws)


def _normalize(s):
    """Chuẩn hoá chuỗi: bỏ dấu tiếng Việt, đ/Đ->d, lowercase (so khớp không phân biệt dấu)."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("đ", "d").replace("Đ", "d")
    return s.lower()


def _build_norm(text):
    """Trả về (chuỗi đã chuẩn hoá, idx_map) với idx_map[n] = vị trí ký tự gốc của ký tự chuẩn hoá thứ n."""
    norm = []
    idx_map = []
    for i, ch in enumerate(text):
        base = _normalize(ch)
        if base:
            norm.append(base)
            idx_map.append(i)
    return "".join(norm), idx_map


def _is_inside(node, tags):
    for p in node.parents:
        if getattr(p, "name", None) in tags:
            return True
    return False


def _collect_candidates(soup):
    """Các text node hợp lệ để chèn link (không nằm trong heading/a/script/style)."""
    out = []
    for node in soup.find_all(string=True):
        if not (node.string and node.string.strip()):
            continue
        if _is_inside(node, SKIP_PARENTS):
            continue
        out.append(node)
    return out


def _wrap_first(soup, node, phrase, url, title):
    """Bọc cụm từ khớp đầu tiên trong text node thành <a href url title title>phrase</a>.
    So khớp KHÔNG phân biệt dấu tiếng Việt (slug 'cat bao quy dau' vẫn khớp 'cắt bao quy đầu'),
    anchor giữ nguyên chữ gốc trong bài."""
    text = node.string or ""
    if not text or len(phrase) < 2:
        return False
    if getattr(node, "parent", None) is None:  # node đã bị tách khỏi cây (đã chèn trước đó)
        return False
    n_text, idx_map = _build_norm(text)
    n_phrase = _normalize(phrase)
    pos = n_text.find(n_phrase)
    if pos < 0:
        return False
    # ranh giới từ: không nằm giữa ký tự chữ/số
    before = n_text[:pos]
    after = n_text[pos + len(n_phrase):]
    if (before and before[-1].isalnum()) or (after and after[0].isalnum()):
        return False
    start = idx_map[pos]
    end = idx_map[pos + len(n_phrase) - 1] + 1
    before_orig = NavigableString(text[:start])
    a = soup.new_tag("a", href=url, title=title)
    a.string = text[start:end]
    after_orig = NavigableString(text[end:])
    node.replace_with(before_orig, a, after_orig)
    return True


def auto_insert_links(html_content, site_links=None, min_links=MIN_LINKS, max_links=MAX_LINKS):
    """Chèn 2-5 internal link vào HTML bài viết; trả về HTML đã xử lý.
    - Mỗi URL chỉ chèn 1 lần.
    - Không chèn vào <h1>..<h6>, <a>, <script>, <style>.
    - Neo text tự nhiên (giữ nguyên chữ trong bài)."""
    if not html_content or not isinstance(html_content, str):
        return html_content
    try:
        soup = BeautifulSoup(html_content, "html.parser")
    except Exception:
        return html_content
    if site_links is None:
        try:
            site_links = get_site_links()
        except Exception:
            site_links = []
    if not site_links:
        return html_content  # chưa lấy được sitemap -> giữ nguyên bài viết

    candidates = _collect_candidates(soup)

    inserted = 0
    used_urls = set()
    used_phrases = set()
    for link in site_links:
        if inserted >= max_links:
            break
        url = (link.get("url") or "").strip()
        title = _clean_title(link.get("title") or "")
        if not url or url in used_urls or not title:
            continue
        for phrase in _candidate_phrases(title):
            low = _normalize(phrase)
            if low in used_phrases or len(phrase) < 2:
                continue
            for node in candidates:
                if _wrap_first(soup, node, phrase, url, title):
                    used_urls.add(url)
                    _block_subphrases(used_phrases, phrase)
                    inserted += 1
                    candidates = _collect_candidates(soup)  # refresh sau khi chèn
                    break
            if url in used_urls:
                break
    return str(soup) if inserted else html_content
