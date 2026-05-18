#!/usr/bin/env python3
import os, sys, re, time, hashlib, logging, argparse, threading
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

TIMEOUT, MAX_RETRIES, DELAY, WORKERS_PADRAO = 20, 2, 0.2, 8

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0",
]

EXTENSOES = {"imagens":{".jpg",".jpeg",".png",".gif",".webp",".svg",".ico",".avif"},
             "videos":{".mp4",".webm",".mov",".mkv"}, "audio":{".mp3",".wav",".ogg",".m4a"},
             "js":{".js",".mjs"}, "css":{".css"}, "fontes":{".woff",".woff2",".ttf",".otf"}}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("downloader")

def importar_deps():
    try:
        import requests
        from bs4 import BeautifulSoup
        return requests, BeautifulSoup
    except ImportError:
        print("Instalando dependencias...")
        os.system(f"{sys.executable} -m pip install requests beautifulsoup4 lxml -q --break-system-packages")
        import requests
        from bs4 import BeautifulSoup
        return requests, BeautifulSoup

requests_lib, BeautifulSoup = importar_deps()

def hash8(s): return hashlib.md5(s.encode()).hexdigest()[:8]
def sanitizar(nome, n=120): return (re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", nome).strip(". ") or "_")[:n]

def cat_asset(ext):
    ext = ext.lower()
    for cat, exts in EXTENSOES.items():
        if ext in exts: return f"assets/{cat}"
    return "assets/outros"

def url2path(url, pasta, pagina=False):
    p = urlparse(url)
    if pagina:
        cam = p.path.lstrip("/") or "index.html"
        if cam.endswith("/") or "." not in Path(cam).name: cam = cam.rstrip("/") + "/index.html"
        if p.query:
            stem, ext2 = os.path.splitext(cam)
            cam = f"{stem}_{hash8(p.query)}{ext2 or '.html'}" 
        partes = [sanitizar(s) for s in cam.split("/") if s]
        return pasta.joinpath(*partes) if partes else pasta / "index.html"
    else:
        ext = Path(p.path).suffix.lower()
        sub = cat_asset(ext)
        nome = sanitizar(Path(p.path).stem)[:40] or "file"
        return pasta / sub / f"{nome}_{hash8(url)}{ext or '.bin'}" 

def normalizar(url, base):
    try:
        joined = urljoin(base, url.strip())
        p = urlparse(joined)
        clean = urlunparse(p._replace(fragment=""))
        if p.scheme in ("http", "https"): return clean
    except: pass
    return None

def mesmo_dominio(url, dominio, subdominios=False):
    h = urlparse(url).netloc
    if not h: return True
    h_bare = h[4:] if h.startswith("www.") else h
    d_bare = dominio[4:] if dominio.startswith("www.") else dominio
    if h == dominio or h_bare == d_bare: return True
    if subdominios and h.endswith("." + dominio): return True
    return False

def rel_path(origem_url, destino_abs, pasta):
    try:
        origem_dir = url2path(origem_url, pasta, pagina=True).parent
        return os.path.relpath(destino_abs, origem_dir).replace("\\", "/")
    except: return destino_abs

def tam_legivel(b):
    for u in ("B", "KB", "MB", "GB"):
        if b < 1024: return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} TB"

def headers_aleatorios(referer=None, eh_asset=False):
    ua = USER_AGENTS[int(hash(time.time()*1000) % len(USER_AGENTS))]
    hdrs = {"User-Agent": ua, "Accept": "*/*" if eh_asset else "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7", "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive", "DNT": "1"}
    if referer: hdrs["Referer"] = referer
    if not eh_asset:
        hdrs.update({"Upgrade-Insecure-Requests": "1", "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate"})
    else:
        hdrs["Sec-Fetch-Dest"] = "script" if eh_asset == "js" else "style" if eh_asset == "css" else "image"
        hdrs["Sec-Fetch-Mode"] = "no-cors"
    return hdrs
