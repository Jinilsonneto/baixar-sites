#!/usr/bin/env python3
# BAIXADOR DE SITE — MODO OFFLINE TOTAL
# Uso basico:   python3 baixar_site_offline.py https://exemplo.com
# Cloudflare:   python3 baixar_site_offline.py https://exemplo.com --cloud
# CAPTCHA:      python3 baixar_site_offline.py https://exemplo.com --captcha

import os, re, sys, time, hashlib, logging, argparse, threading, signal
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse
from collections import deque
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime

def instalar(pacote):
    os.system(f"{sys.executable} -m pip install {pacote} --break-system-packages -q")

def importar_requests():
    try:
        import requests
        from bs4 import BeautifulSoup
        return requests, BeautifulSoup
    except ImportError:
        print("Instalando dependencias basicas...")
        instalar("requests beautifulsoup4 lxml")
        import requests
        from bs4 import BeautifulSoup
        return requests, BeautifulSoup

def importar_cloudscraper():
    try:
        import cloudscraper
        return cloudscraper
    except ImportError:
        print("Instalando cloudscraper...")
        instalar("cloudscraper")
        import cloudscraper
        return cloudscraper

def importar_selenium():
    try:
        import undetected_chromedriver as uc
        return uc
    except ImportError:
        print("Instalando undetected-chromedriver...")
        instalar("undetected-chromedriver selenium")
        import undetected_chromedriver as uc
        return uc

requests_lib, BeautifulSoup = importar_requests()

TIMEOUT        = 30
MAX_RETRIES    = 3
DELAY          = 0.3
WORKERS_PADRAO = 5
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

EXTENSOES = {
    "imagens": {".jpg",".jpeg",".png",".gif",".webp",".svg",".ico",".bmp",".tiff",".avif"},
    "videos":  {".mp4",".webm",".avi",".mov",".mkv",".flv",".m4v",".wmv"},
    "audio":   {".mp3",".wav",".ogg",".flac",".aac",".m4a",".opus"},
    "js":      {".js",".mjs",".cjs"},
    "css":     {".css"},
    "docs":    {".pdf",".doc",".docx",".xls",".xlsx",".ppt",".pptx",".txt",".md"},
    "fontes":  {".woff",".woff2",".ttf",".eot",".otf"},
    "dados":   {".json",".xml",".yaml",".yml"},
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("offline")

def sanitizar(nome, n=180):
    nome = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", nome)
    return (nome.strip(". ") or "_")[:n]

def hash8(s):
    return hashlib.md5(s.encode()).hexdigest()[:8]

def cat_asset(ext):
    ext = ext.lower()
    for cat, exts in EXTENSOES.items():
        if ext in exts:
            return f"assets/{cat}"
    return "assets/outros"

def url2path(url, pasta, pagina=False):
    p = urlparse(url)
    if pagina:
        cam = p.path.lstrip("/") or "index.html"
        if cam.endswith("/") or "." not in Path(cam).name:
            cam = cam.rstrip("/") + "/index.html"
        if p.query:
            stem, ext2 = os.path.splitext(cam)
            cam = f"{stem}_{hash8(p.query)}{ext2 or '.html'}"
        partes = [sanitizar(s) for s in cam.split("/") if s]
        return pasta.joinpath(*partes) if partes else pasta / "index.html"
    else:
        ext = Path(p.path).suffix.lower()
        sub = cat_asset(ext)
        nome = sanitizar(Path(p.path).stem)[:60] or "recurso"
        return pasta / sub / f"{nome}_{hash8(url)}{ext or '.bin'}"

def normalizar(url, base):
    try:
        joined = urljoin(base, url.strip())
        p = urlparse(joined)
        clean = urlunparse(p._replace(fragment=""))
        if p.scheme in ("http", "https"):
            return clean
    except Exception:
        pass
    return None

def mesmo_dominio(url, dominio, subdominios=False):
    h = urlparse(url).netloc
    if not h: return True
    if h == dominio: return True
    if subdominios and h.endswith("." + dominio): return True
    return False

def rel_path(origem_url, destino_abs, pasta, origem_pagina=True):
    try:
        origem_dir = url2path(origem_url, pasta, pagina=origem_pagina).parent
        return os.path.relpath(destino_abs, origem_dir).replace("\\", "/")
    except Exception:
        return destino_abs

def tam_legivel(b):
    for u in ("B", "KB", "MB", "GB"):
        if b < 1024: return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} TB"

# ══════════════════════════════════════════════════════════════════════════════
# MODO CAPTCHA
# ══════════════════════════════════════════════════════════════════════════════

class SessaoCaptcha:
    def __init__(self, url_inicial):
        self.cookies = {}
        self.user_agent = USER_AGENT
        self._resolver(url_inicial)

    def _resolver(self, url):
        uc = importar_selenium()
        print()
        print("=" * 65)
        print("  MODO CAPTCHA ATIVADO")
        print("=" * 65)
        print("  Um navegador Chrome vai abrir agora.")
        print("  1. Resolva o CAPTCHA ou faca login se necessario.")
        print("  2. Quando a pagina carregar normalmente, volte aqui.")
        print("  3. Pressione ENTER para o programa continuar.")
        print("=" * 65)
        print()

        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--start-maximized")

        # Detectar versao do Chrome instalado automaticamente
        def detectar_versao_chrome():
            import subprocess
            for cmd in ["google-chrome --version", "google-chrome-stable --version",
                        "chromium-browser --version", "chromium --version"]:
                try:
                    out = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL)
                    versao = out.decode().strip().split()[-1]  # ex: "145.0.7632.116"
                    return int(versao.split(".")[0])           # retorna 145
                except Exception:
                    continue
            return None

        versao = detectar_versao_chrome()
        if versao:
            log.info(f"Chrome detectado: versao {versao}")

        driver = None
        try:
            driver = uc.Chrome(
                options=options,
                headless=False,
                version_main=versao,  # None = automatico, numero = forcado
            )
            driver.get(url)
            input("  Pressione ENTER quando estiver pronto para continuar...")
            self.cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
            self.user_agent = driver.execute_script("return navigator.userAgent")
            log.info(f"Cookies capturados: {len(self.cookies)}")
        except Exception as e:
            log.warning(f"Erro ao abrir navegador: {e}")
        finally:
            if driver:
                try: driver.quit()
                except Exception: pass

    def aplicar_na_session(self, session):
        for nome, valor in self.cookies.items():
            session.cookies.set(nome, valor)
        session.headers.update({"User-Agent": self.user_agent})
        return session

# ══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

class BaixadorOffline:

    def __init__(self, url_inicial, workers=WORKERS_PADRAO, prof_max=0, delay=DELAY,
                 subdominios=False, modo_cloud=False, modo_captcha=False):

        self.url_inicial  = url_inicial.rstrip("/")
        p = urlparse(self.url_inicial)
        self.dominio      = p.netloc
        self.esquema      = p.scheme
        self.workers      = workers
        self.prof_max     = prof_max
        self.delay        = delay
        self.subdominios  = subdominios
        self.modo_cloud   = modo_cloud
        self.modo_captcha = modo_captcha

        self.pasta = Path(sanitizar(self.dominio))
        self.pasta.mkdir(parents=True, exist_ok=True)
        for sub in ("assets/imagens","assets/css","assets/js","assets/fontes",
                    "assets/midia","assets/audio","assets/videos","assets/docs",
                    "assets/dados","assets/outros"):
            (self.pasta / sub).mkdir(parents=True, exist_ok=True)

        if modo_cloud:
            log.info("Modo Cloudflare ativado -- usando cloudscraper")
            cs = importar_cloudscraper()
            self.session = cs.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "mobile": False}
            )
        else:
            self.session = requests_lib.Session()

        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        })

        if modo_captcha:
            sessao_cap = SessaoCaptcha(self.url_inicial)
            sessao_cap.aplicar_na_session(self.session)

        self._lock      = threading.Lock()
        self._visitados = set()
        self._mapa      = {}
        self._fila      = deque()
        self._paginas   = []
        self._baixados  = 0
        self._erros     = 0
        self._bytes     = 0

        modos = []
        if modo_cloud:   modos.append("Cloudflare bypass")
        if modo_captcha: modos.append("CAPTCHA manual")
        if not modos:    modos.append("padrao")

        log.info(f"Site:    {self.url_inicial}")
        log.info(f"Pasta:   {self.pasta.resolve()}")
        log.info(f"Modo:    {' + '.join(modos)}")
        log.info(f"Workers: {self.workers}  |  Profundidade: {'ilimitada' if not self.prof_max else self.prof_max}")

    def _get(self, url, stream=False):
        for t in range(1, MAX_RETRIES + 1):
            try:
                r = self.session.get(url, timeout=TIMEOUT, stream=stream, allow_redirects=True)
                r.raise_for_status()
                if self._detectar_captcha(r):
                    log.warning(f"CAPTCHA/bloqueio detectado em: {url}")
                    log.warning("Use --captcha para resolver manualmente ou --cloud para Cloudflare.")
                    return None
                return r
            except Exception as e:
                if t == MAX_RETRIES:
                    log.debug(f"Falha: {url} -> {e}")
                    return None
                time.sleep(t * 1.5)
        return None

    def _detectar_captcha(self, r):
        if r.status_code in (403, 429, 503):
            if "text/html" in r.headers.get("Content-Type", ""):
                texto = r.text.lower()
                for i in ["captcha","recaptcha","hcaptcha","cloudflare","ray id",
                           "challenge","access denied","are you human","bot protection"]:
                    if i in texto:
                        return True
        return False

    def _marcar(self, url):
        with self._lock:
            if url in self._visitados: return False
            self._visitados.add(url)
            return True

    def _registrar(self, url, caminho):
        with self._lock:
            self._mapa[url] = caminho

    def _local(self, url):
        with self._lock:
            return self._mapa.get(url)

    def _agendar(self, url, prof, pagina=False):
        with self._lock:
            if url not in self._visitados:
                self._fila.append((url, prof, pagina))

    def _proximo(self):
        with self._lock:
            return self._fila.popleft() if self._fila else None

    def _reescrever_css(self, css, url_base, prof):
        def sub_url(m):
            href = m.group(1).strip("'\" ")
            if href.startswith(("data:", "#", "about:")): return m.group(0)
            abs_url = normalizar(href, url_base)
            if not abs_url: return m.group(0)
            local = self._baixar_asset(abs_url, url_base, prof)
            if local: return f"url('{rel_path(url_base, local, self.pasta, False)}')"
            return m.group(0)

        def sub_import(m):
            href = m.group(1).strip("'\" ")
            abs_url = normalizar(href, url_base)
            if not abs_url: return m.group(0)
            local = self._baixar_asset(abs_url, url_base, prof)
            if local: return f'@import "{rel_path(url_base, local, self.pasta, False)}"'
            return m.group(0)

        css = re.sub(r'url\(\s*([^)]+?)\s*\)', sub_url, css)
        css = re.sub(r'@import\s+url\(\s*([^)]+?)\s*\)', sub_import, css)
        css = re.sub(r'@import\s+["\']([^"\']+)["\']', sub_import, css)
        return css

    def _baixar_asset(self, url, url_base, prof):
        local = self._local(url)
        if local: return local

        caminho = url2path(url, self.pasta, pagina=False)
        self._registrar(url, str(caminho))
        if caminho.exists(): return str(caminho)

        caminho.parent.mkdir(parents=True, exist_ok=True)
        ext = caminho.suffix.lower()
        eh_midia = ext in {".mp4",".webm",".avi",".mov",".mkv",".mp3",".flac",".wav",".ogg"}

        r = self._get(url, stream=eh_midia)
        if not r:
            with self._lock: self._erros += 1
            return None

        ct = r.headers.get("Content-Type", "")
        try:
            if eh_midia:
                with open(caminho, "wb") as f:
                    for chunk in r.iter_content(65536): f.write(chunk)
            elif "text/css" in ct:
                texto = self._reescrever_css(r.content.decode("utf-8", errors="replace"), url, prof)
                caminho.write_bytes(texto.encode("utf-8"))
            else:
                caminho.write_bytes(r.content)
            with self._lock:
                self._baixados += 1
                self._bytes    += caminho.stat().st_size
        except Exception as e:
            log.debug(f"Erro salvando {url}: {e}")
            with self._lock: self._erros += 1
            return None

        time.sleep(self.delay)
        return str(caminho)

    def _processar_html(self, url, conteudo, prof):
        soup = BeautifulSoup(conteudo, "lxml")
        base_tag = soup.find("base", href=True)
        url_base = normalizar(base_tag["href"], url) if base_tag else url
        if url_base is None: url_base = url
        if base_tag: base_tag.decompose()

        for s in soup.find_all("script"):
            if s.string and "serviceWorker" in (s.string or ""):
                s.string = "/* service worker removido */"
        for m in soup.find_all("meta", attrs={"http-equiv": re.compile("refresh", re.I)}):
            m.decompose()

        TAGS = [
            ("img",    ["src","data-src","data-lazy","data-lazy-src","data-original"]),
            ("source", ["src","srcset"]),
            ("video",  ["src","poster"]),
            ("audio",  ["src"]),
            ("track",  ["src"]),
            ("script", ["src"]),
            ("link",   ["href"]),
            ("a",      ["href"]),
            ("iframe", ["src"]),
            ("embed",  ["src"]),
            ("object", ["data"]),
            ("input",  ["src"]),
        ]

        for tag_nome, attrs in TAGS:
            for el in soup.find_all(tag_nome):
                for atr in attrs:
                    val = el.get(atr, "")
                    if not val: continue
                    val = str(val).strip()
                    if val.startswith(("data:","javascript:","#","mailto:","tel:","about:","blob:")): continue

                    if atr == "srcset":
                        partes = []
                        for parte in val.split(","):
                            parte = parte.strip()
                            if not parte: continue
                            tokens = parte.split()
                            abs_url = normalizar(tokens[0], url_base)
                            if abs_url:
                                local = self._baixar_asset(abs_url, url_base, prof)
                                if local: tokens[0] = rel_path(url, local, self.pasta)
                            partes.append(" ".join(tokens))
                        el[atr] = ", ".join(partes)
                        continue

                    abs_url = normalizar(val, url_base)
                    if not abs_url: continue

                    if tag_nome == "a" and atr == "href":
                        if mesmo_dominio(abs_url, self.dominio, self.subdominios):
                            if not self.prof_max or prof < self.prof_max:
                                self._agendar(abs_url, prof + 1, pagina=True)
                        cam_local = url2path(abs_url, self.pasta, pagina=True)
                        self._registrar(abs_url, str(cam_local))
                        el[atr] = rel_path(url, str(cam_local), self.pasta)
                        continue

                    if tag_nome == "link" and atr == "href":
                        rels = [r.lower() for r in (el.get("rel") or [])]
                        if any(r in rels for r in ("stylesheet","preload","modulepreload",
                                                    "icon","shortcut","apple-touch-icon","manifest")):
                            local = self._baixar_asset(abs_url, url_base, prof)
                            if local: el[atr] = rel_path(url, local, self.pasta)
                        continue

                    local = self._baixar_asset(abs_url, url_base, prof)
                    if local: el[atr] = rel_path(url, local, self.pasta)

        for el in soup.find_all(style=True):
            el["style"] = self._reescrever_css(el["style"], url_base, prof)
        for st in soup.find_all("style"):
            if st.string: st.string = self._reescrever_css(st.string, url_base, prof)
        if not soup.find("meta", charset=True):
            mc = soup.new_tag("meta", charset="utf-8")
            if soup.head: soup.head.insert(0, mc)

        return soup.encode(formatter="html5")

    def _processar_url(self, url, prof, eh_pagina):
        if not self._marcar(url): return
        if not mesmo_dominio(url, self.dominio, self.subdominios): return

        log.info(f"[P{prof}] {url}")
        r = self._get(url)
        if not r:
            with self._lock: self._erros += 1
            return

        ct = r.headers.get("Content-Type", "").lower()
        url_final = r.url or url

        if "text/html" in ct:
            caminho = url2path(url_final, self.pasta, pagina=True)
            if not caminho.suffix: caminho = caminho.with_suffix(".html")
            conteudo = self._processar_html(url_final, r.content, prof)
            titulo = url_final
            try:
                s = BeautifulSoup(r.content, "lxml")
                t = s.find("title")
                if t and t.string: titulo = t.string.strip()
            except Exception: pass
            with self._lock:
                self._paginas.append({"url": url_final, "caminho": str(caminho),
                                      "titulo": titulo, "prof": prof})
        elif "text/css" in ct:
            caminho = url2path(url_final, self.pasta, pagina=False).with_suffix(".css")
            conteudo = self._reescrever_css(
                r.content.decode("utf-8", errors="replace"), url_final, prof).encode("utf-8")
        elif "javascript" in ct:
            caminho = url2path(url_final, self.pasta, pagina=False)
            if caminho.suffix not in {".js",".mjs",".cjs"}: caminho = caminho.with_suffix(".js")
            conteudo = r.content
        else:
            caminho = url2path(url_final, self.pasta, pagina=False)
            conteudo = r.content

        caminho.parent.mkdir(parents=True, exist_ok=True)
        if not caminho.exists(): caminho.write_bytes(conteudo)
        self._registrar(url, str(caminho))
        self._registrar(url_final, str(caminho))

        with self._lock:
            self._baixados += 1
            self._bytes    += len(conteudo)
        time.sleep(self.delay)

    def _ler_sitemap(self, sm_url):
        r = self._get(sm_url)
        if not r: return
        locs = re.findall(r"<loc>\s*(.+?)\s*</loc>", r.text)
        for loc in locs:
            loc = loc.strip()
            if loc.endswith(".xml"): self._ler_sitemap(loc)
            elif mesmo_dominio(loc, self.dominio, self.subdominios):
                self._agendar(loc, 0, pagina=True)

    def _descobrir_sitemap(self):
        candidatos = [f"{self.esquema}://{self.dominio}/sitemap.xml",
                      f"{self.esquema}://{self.dominio}/sitemap_index.xml"]
        r = self._get(f"{self.esquema}://{self.dominio}/robots.txt")
        if r:
            for linha in r.text.splitlines():
                if linha.lower().startswith("sitemap:"):
                    candidatos.insert(0, linha.split(":", 1)[1].strip())
        for sm in candidatos: self._ler_sitemap(sm)
        log.info(f"Sitemap: {len(self._fila)} URLs encontradas")

    def _gerar_indice(self):
        itens = ""
        for pg in sorted(self._paginas, key=lambda p: (p["prof"], p["url"])):
            try: rel = os.path.relpath(pg["caminho"], self.pasta).replace("\\", "/")
            except Exception: rel = pg["caminho"]
            itens += (f'<li class="p{pg["prof"]}">'
                      f'<a href="{rel}">{pg["titulo"]}</a>'
                      f'<span class="url">{pg["url"]}</span></li>\n')

        html = f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Indice Offline -- {self.dominio}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;padding:2rem;line-height:1.6}}
h1{{font-size:1.8rem;color:#38bdf8;margin-bottom:1rem}}
h1 span{{color:#94a3b8;font-size:1rem;font-weight:normal}}
.stats{{display:flex;gap:1rem;margin:1rem 0;flex-wrap:wrap}}
.stat{{background:#1e293b;border-radius:8px;padding:.5rem 1rem;border-left:4px solid #38bdf8}}
.stat strong{{display:block;font-size:1.4rem;color:#fff}}
.stat small{{color:#94a3b8;font-size:.8rem}}
#busca{{width:100%;padding:.7rem 1rem;font-size:1rem;background:#1e293b;border:1px solid #334155;
        border-radius:8px;color:#e2e8f0;margin:1rem 0;outline:none}}
#busca:focus{{border-color:#38bdf8}}
ul{{list-style:none}}
li{{border-bottom:1px solid #1e293b;padding:.5rem .25rem}}
li:hover{{background:#1e293b;border-radius:6px}}
li a{{color:#38bdf8;text-decoration:none;font-weight:500;word-break:break-all}}
li a:hover{{text-decoration:underline}}
.url{{display:block;font-size:.75rem;color:#64748b;word-break:break-all}}
li.p0 a{{color:#f472b6}} li.p1 a{{color:#a78bfa}} .oculto{{display:none}}
footer{{margin-top:2rem;color:#475569;font-size:.8rem}}
</style></head><body>
<h1>Indice Offline <span>-- {self.dominio}</span></h1>
<div class="stats">
  <div class="stat"><strong>{len(self._paginas)}</strong><small>paginas</small></div>
  <div class="stat"><strong>{self._baixados}</strong><small>arquivos</small></div>
  <div class="stat"><strong>{tam_legivel(self._bytes)}</strong><small>baixados</small></div>
  <div class="stat"><strong>{datetime.now().strftime('%d/%m/%Y %H:%M')}</strong><small>arquivado em</small></div>
</div>
<input id="busca" type="search" placeholder="Buscar pagina..." autocomplete="off">
<ul id="lista">{itens}</ul>
<footer>Gerado por BaixadorOffline -- {self.url_inicial}</footer>
<script>
const b=document.getElementById('busca'),its=document.querySelectorAll('#lista li');
b.addEventListener('input',()=>{{const q=b.value.toLowerCase();
  its.forEach(li=>li.classList.toggle('oculto',q&&!li.textContent.toLowerCase().includes(q)));
}});
</script></body></html>"""

        idx = self.pasta / "_indice_offline.html"
        idx.write_text(html, encoding="utf-8")
        log.info(f"Indice: {idx.resolve()}")

    def crawl(self):
        inicio = time.time()
        self._interrompido = False

        # ── Capturar Ctrl+C para gerar indice antes de sair ───────────────────
        def _handle_sigint(sig, frame):
            if self._interrompido:
                # Segundo Ctrl+C: sair imediatamente
                print("\n\nForçando saida...")
                os._exit(1)
            self._interrompido = True
            print("\n\n  Ctrl+C detectado — aguarde, gerando indice offline...")

        signal.signal(signal.SIGINT, _handle_sigint)

        log.info("Verificando sitemap...")
        self._descobrir_sitemap()
        self._agendar(self.url_inicial, 0, pagina=True)
        log.info(f"Iniciando download com {self.workers} workers...")
        print()

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futuros = set()

            def submeter():
                n = 0
                while True:
                    if self._interrompido: break
                    item = self._proximo()
                    if item is None: break
                    url, prof, pag = item
                    with self._lock:
                        if url in self._visitados: continue
                    f = executor.submit(self._processar_url, url, prof, pag)
                    futuros.add(f)
                    n += 1
                return n

            submeter()

            while futuros:
                done, _ = wait(futuros, timeout=2.0, return_when=FIRST_COMPLETED)
                for f in done:
                    futuros.discard(f)
                    try: f.result()
                    except Exception as e: log.debug(f"Worker erro: {e}")

                if self._interrompido:
                    # Cancelar futuros pendentes e sair do loop
                    for f in futuros:
                        f.cancel()
                    futuros.clear()
                    break

                novos = submeter()
                with self._lock:
                    b, pend, ativos = self._baixados, len(self._fila), len(futuros)
                print(f"\r  Baixados: {b}  |  Na fila: {pend}  |  Ativos: {ativos}    ", end="", flush=True)
                if not done and not novos and not futuros: break

        print()

        # Sempre gera o indice, seja download completo ou interrompido
        if self._interrompido:
            log.info(f"Download interrompido. Paginas salvas ate agora: {len(self._paginas)}")
        self._gerar_indice()
        self._relatorio(time.time() - inicio)

        # Restaurar handler padrao do Ctrl+C
        signal.signal(signal.SIGINT, signal.SIG_DFL)

    def _relatorio(self, dur):
        log.info("=" * 65)
        log.info("Download concluido!")
        log.info(f"   Paginas HTML   : {len(self._paginas)}")
        log.info(f"   Arquivos total : {self._baixados}")
        log.info(f"   Erros          : {self._erros}")
        log.info(f"   Total baixado  : {tam_legivel(self._bytes)}")
        log.info(f"   Tempo          : {dur:.1f}s")
        log.info(f"   Pasta          : {self.pasta.resolve()}")
        cont, tsz = {}, {}
        for arq in self.pasta.rglob("*"):
            if not arq.is_file(): continue
            pts = arq.relative_to(self.pasta).parts
            chave = f"assets/{pts[1]}" if len(pts) >= 2 and pts[0] == "assets" else "paginas"
            cont[chave] = cont.get(chave, 0) + 1
            tsz[chave]  = tsz.get(chave, 0) + arq.stat().st_size
        log.info("   Por categoria:")
        for cat, qtd in sorted(cont.items()):
            log.info(f"      {cat:<22} {qtd:>4} arq.  {tam_legivel(tsz[cat]):>10}")
        log.info("=" * 65)
        log.info(f"Abrir: {(self.pasta / 'index.html').resolve()}")
        log.info(f"Indice: {(self.pasta / '_indice_offline.html').resolve()}")

# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Baixa um site inteiro para uso offline.")
    parser.add_argument("url", nargs="?")
    parser.add_argument("--workers",      "-w", type=int,   default=WORKERS_PADRAO)
    parser.add_argument("--profundidade", "-p", type=int,   default=0)
    parser.add_argument("--delay",        "-d", type=float, default=DELAY)
    parser.add_argument("--subdominios",  "-s", action="store_true")
    parser.add_argument("--cloud",   action="store_true", help="Bypass Cloudflare automatico")
    parser.add_argument("--captcha", action="store_true", help="Abrir navegador para resolver CAPTCHA manualmente")
    parser.add_argument("--leve",    action="store_true",
                        help="Modo leve: menos CPU/RAM, ideal para rodar em segundo plano sem travar o PC")
    args = parser.parse_args()

    url = args.url
    if not url:
        print("=" * 65)
        print("  BAIXADOR DE SITE -- MODO OFFLINE TOTAL")
        print("=" * 65)
        url = input("  Cole a URL do site: ").strip()

    if not url:
        print("URL nao informada.")
        sys.exit(1)

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # ── Modo leve: ajusta workers/delay e reduz prioridade do processo ────────
    workers = args.workers
    delay   = args.delay

    if args.leve:
        workers = min(args.workers, 2)   # no maximo 2 downloads simultaneos
        delay   = max(args.delay, 1.5)   # minimo 1.5s entre requests
        # Reduz prioridade do processo no Linux (nice +15 = baixa prioridade)
        try:
            os.nice(15)
        except Exception:
            pass
        print()
        print("=" * 65)
        print("  MODO LEVE ATIVADO")
        print("=" * 65)
        print(f"  Workers : {workers} (limitado para nao sobrecarregar)")
        print(f"  Delay   : {delay}s entre requests")
        print(f"  CPU     : prioridade reduzida (nice +15)")
        print()
        print("  O download vai mais devagar, mas o PC nao vai travar.")
        print()
        print("  Para rodar em segundo plano e fechar o terminal:")
        print(f"  nohup python3 baixar_site_offline.py {url} --leve > log.txt 2>&1 &")
        print("=" * 65)
        print()

    print()
    b = BaixadorOffline(url, workers=workers, prof_max=args.profundidade,
                        delay=delay, subdominios=args.subdominios,
                        modo_cloud=args.cloud, modo_captcha=args.captcha)
    b.crawl()

if __name__ == "__main__":
    main()
