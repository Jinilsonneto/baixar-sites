#!/usr/bin/env python3
# BAIXADOR DE SITE — MODO OFFLINE TOTAL
# Uso basico:   python3 baixar_site_offline.py https://exemplo.com
# Atualizar:    python3 baixar_site_offline.py https://exemplo.com --atualizar
# Cloudflare:   python3 baixar_site_offline.py https://exemplo.com --cloud
# CAPTCHA:      python3 baixar_site_offline.py https://exemplo.com --captcha

import os, re, sys, time, hashlib, logging, argparse, threading, json
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

        def detectar_versao_chrome():
            import subprocess
            for cmd in ["google-chrome --version", "google-chrome-stable --version",
                        "chromium-browser --version", "chromium --version"]:
                try:
                    out = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL)
                    versao = out.decode().strip().split()[-1]
                    return int(versao.split(".")[0])
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
                version_main=versao,
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
                 subdominios=False, modo_cloud=False, modo_captcha=False, modo_atualizar=False):

        self.url_inicial   = url_inicial.rstrip("/")
        p = urlparse(self.url_inicial)
        self.dominio       = p.netloc
        self.esquema       = p.scheme
        self.workers       = workers
        self.prof_max      = prof_max
        self.delay         = delay
        self.subdominios   = subdominios
        self.modo_cloud    = modo_cloud
        self.modo_captcha  = modo_captcha
        self.modo_atualizar = modo_atualizar   # NOVO: força reescrita de arquivos existentes

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

        tamanho_pool = max(self.workers + 5, 20)
        adapter = requests_lib.adapters.HTTPAdapter(
            pool_connections=tamanho_pool,
            pool_maxsize=tamanho_pool,
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        if modo_captcha:
            sessao_cap = SessaoCaptcha(self.url_inicial)
            sessao_cap.aplicar_na_session(self.session)

        self._lock      = threading.Lock()
        self._visitados = set()
        self._mapa      = {}
        self._fila      = deque()
        self._paginas   = []
        self._baixados  = 0
        self._atualizados = 0
        self._pulados   = 0
        self._erros     = 0
        self._bytes     = 0

        # Metadados HTTP (ETag / Last-Modified) persistidos entre sessoes
        self._arquivo_meta = self.pasta / "_meta.json"
        self._meta = self._carregar_meta()

        modos = []
        if modo_cloud:     modos.append("Cloudflare bypass")
        if modo_captcha:   modos.append("CAPTCHA manual")
        if modo_atualizar: modos.append("ATUALIZAR (inteligente por ETag/Last-Modified)")
        if not modos:      modos.append("padrao")

        log.info(f"Site:    {self.url_inicial}")
        log.info(f"Pasta:   {self.pasta.resolve()}")
        log.info(f"Modo:    {' + '.join(modos)}")
        log.info(f"Workers: {self.workers}  |  Profundidade: {'ilimitada' if not self.prof_max else self.prof_max}")

    # ── Metadados ──────────────────────────────────────────────────────────────

    def _carregar_meta(self):
        try:
            if self._arquivo_meta.exists():
                return json.loads(self._arquivo_meta.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _salvar_meta(self):
        try:
            with self._lock:
                dados = dict(self._meta)
            self._arquivo_meta.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            log.debug(f"Erro ao salvar meta: {e}")

    def _registrar_meta(self, url, headers):
        """Salva ETag e Last-Modified de uma resposta bem-sucedida."""
        etag  = headers.get("ETag", "")
        lm    = headers.get("Last-Modified", "")
        if etag or lm:
            with self._lock:
                self._meta[url] = {"etag": etag, "last_modified": lm}

    # ── HTTP ───────────────────────────────────────────────────────────────────

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

    def _get_condicional(self, url, stream=False):
        """
        No modo --atualizar: envia ETag/Last-Modified se existirem.
        Retorna (resposta, mudou):
          - mudou=False  -> servidor retornou 304 (nao mudou, pular)
          - mudou=True   -> conteudo novo disponivel em resposta
          - resposta=None -> erro de rede
        """
        meta = {}
        with self._lock:
            meta = self._meta.get(url, {})

        hdrs = {}
        if meta.get("etag"):
            hdrs["If-None-Match"] = meta["etag"]
        if meta.get("last_modified"):
            hdrs["If-Modified-Since"] = meta["last_modified"]

        for t in range(1, MAX_RETRIES + 1):
            try:
                r = self.session.get(url, timeout=TIMEOUT, stream=stream,
                                     allow_redirects=True, headers=hdrs)
                if r.status_code == 304:
                    return None, False   # nao mudou
                r.raise_for_status()
                if self._detectar_captcha(r):
                    log.warning(f"CAPTCHA/bloqueio detectado em: {url}")
                    return None, True
                return r, True
            except Exception as e:
                if t == MAX_RETRIES:
                    log.debug(f"Falha: {url} -> {e}")
                    return None, True
                time.sleep(t * 1.5)
        return None, True

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
        # Substitui @import url(...) primeiro para evitar duplo processamento
        def sub_import_url(m):
            href = m.group(1).strip("'\" ")
            abs_url = normalizar(href, url_base)
            if not abs_url: return m.group(0)
            local = self._baixar_asset(abs_url, url_base, prof)
            if local: return f'@import "{rel_path(url_base, local, self.pasta, False)}"'
            return m.group(0)

        def sub_import_str(m):
            href = m.group(1).strip("'\" ")
            abs_url = normalizar(href, url_base)
            if not abs_url: return m.group(0)
            local = self._baixar_asset(abs_url, url_base, prof)
            if local: return f'@import "{rel_path(url_base, local, self.pasta, False)}"'
            return m.group(0)

        def sub_url(m):
            href = m.group(1).strip("'\" ")
            if href.startswith(("data:", "#", "about:")): return m.group(0)
            abs_url = normalizar(href, url_base)
            if not abs_url: return m.group(0)
            local = self._baixar_asset(abs_url, url_base, prof)
            if local: return f"url('{rel_path(url_base, local, self.pasta, False)}')"
            return m.group(0)

        # Ordem importa: @import url() antes do url() generico
        css = re.sub(r'@import\s+url\(\s*([^)]+?)\s*\)', sub_import_url, css)
        css = re.sub(r'@import\s+["\']([^"\']+)["\']', sub_import_str, css)
        css = re.sub(r'url\(\s*([^)]+?)\s*\)', sub_url, css)
        return css

    def _baixar_asset(self, url, url_base, prof):
        local = self._local(url)
        if local and not self.modo_atualizar:
            return local

        caminho = url2path(url, self.pasta, pagina=False)
        self._registrar(url, str(caminho))

        ja_existe = caminho.exists()

        # Modo normal: pula se já existe
        if ja_existe and not self.modo_atualizar:
            return str(caminho)

        caminho.parent.mkdir(parents=True, exist_ok=True)
        ext = caminho.suffix.lower()
        eh_midia = ext in {".mp4",".webm",".avi",".mov",".mkv",".mp3",".flac",".wav",".ogg"}

        # Modo atualizar: usa requisição condicional se já existe
        if self.modo_atualizar and ja_existe:
            r, mudou = self._get_condicional(url, stream=eh_midia)
            if not mudou:
                with self._lock: self._pulados += 1
                return str(caminho)
            if r is None:
                with self._lock: self._erros += 1
                return None
        else:
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

            self._registrar_meta(url, r.headers)
            with self._lock:
                self._baixados += 1
                self._bytes    += caminho.stat().st_size
                if ja_existe and self.modo_atualizar:
                    self._atualizados += 1
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

        # Neutraliza formularios: remove action/method para nao baixar .php ao clicar
        for form in soup.find_all("form"):
            form["action"] = "#"
            form["onsubmit"] = "return false;"
            form.pop("method", None)

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

        ja_existe_local = url2path(url, self.pasta, pagina=True).exists()

        # Modo atualizar com arquivo existente: verifica se mudou antes de baixar
        if self.modo_atualizar and ja_existe_local:
            r, mudou = self._get_condicional(url)
            if not mudou:
                with self._lock: self._pulados += 1
                log.debug(f"Sem mudancas: {url}")
                return
            if r is None:
                with self._lock: self._erros += 1
                return
        else:
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
        era_existente = caminho.exists()

        if not era_existente or self.modo_atualizar:
            caminho.write_bytes(conteudo)

        self._registrar_meta(url_final, r.headers)
        self._registrar(url, str(caminho))
        self._registrar(url_final, str(caminho))

        with self._lock:
            self._baixados += 1
            self._bytes    += len(conteudo)
            if era_existente and self.modo_atualizar:
                self._atualizados += 1
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
        paginas_json = []
        for pg in sorted(self._paginas, key=lambda p: (p["prof"], p["url"])):
            try:
                rel = os.path.relpath(pg["caminho"], self.pasta).replace("\\", "/")
            except Exception:
                rel = pg["caminho"]
            titulo_esc = pg["titulo"].replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
            url_esc    = pg["url"].replace('"', '&quot;')
            paginas_json.append({
                "titulo": titulo_esc,
                "url":    url_esc,
                "rel":    rel,
                "prof":   pg["prof"],
            })

        dados_js = json.dumps(paginas_json, ensure_ascii=False)
        data_arquivo = datetime.now().strftime("%d/%m/%Y %H:%M")

        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Indice Offline — {self.dominio}</title>
<style>
  :root {{
    --bg:      #0d1117;
    --surface: #161b22;
    --border:  #21262d;
    --accent:  #58a6ff;
    --accent2: #3fb950;
    --muted:   #8b949e;
    --text:    #e6edf3;
    --p0:      #f78166;
    --p1:      #d2a8ff;
    --radius:  10px;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }}

  /* ── HEADER ── */
  header {{
    background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
    border-bottom: 1px solid var(--border);
    padding: 2rem 2rem 1.5rem;
    position: sticky;
    top: 0;
    z-index: 10;
    backdrop-filter: blur(8px);
  }}
  .header-top {{
    display: flex;
    align-items: center;
    gap: .75rem;
    margin-bottom: 1.25rem;
    flex-wrap: wrap;
  }}
  .logo {{
    width: 36px; height: 36px;
    background: linear-gradient(135deg, var(--accent), #388bfd);
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.2rem; flex-shrink: 0;
  }}
  h1 {{
    font-size: 1.3rem;
    font-weight: 600;
    color: var(--text);
    flex: 1;
  }}
  h1 small {{
    display: block;
    font-size: .8rem;
    font-weight: 400;
    color: var(--muted);
    margin-top: 1px;
  }}

  /* ── STATS ── */
  .stats {{
    display: flex;
    gap: .75rem;
    flex-wrap: wrap;
    margin-bottom: 1.25rem;
  }}
  .stat {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: .6rem 1rem;
    display: flex;
    align-items: center;
    gap: .6rem;
    min-width: 110px;
  }}
  .stat-icon {{
    font-size: 1.2rem;
    flex-shrink: 0;
  }}
  .stat-val {{
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--text);
    line-height: 1.1;
  }}
  .stat-lbl {{
    font-size: .72rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: .03em;
  }}

  /* ── BUSCA & FILTROS ── */
  .controles {{
    display: flex;
    gap: .75rem;
    flex-wrap: wrap;
    align-items: center;
  }}
  #busca {{
    flex: 1;
    min-width: 200px;
    padding: .6rem 1rem .6rem 2.6rem;
    font-size: .95rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--text);
    outline: none;
    transition: border-color .15s;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='%238b949e' viewBox='0 0 16 16'%3E%3Cpath d='M11.742 10.344a6.5 6.5 0 1 0-1.397 1.398l3.85 3.85a1 1 0 0 0 1.415-1.415l-3.868-3.833zm-5.24 1.347a5.5 5.5 0 1 1 0-11 5.5 5.5 0 0 1 0 11z'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: .75rem center;
  }}
  #busca:focus {{ border-color: var(--accent); box-shadow: 0 0 0 3px rgba(88,166,255,.15); }}
  #busca::placeholder {{ color: var(--muted); }}

  .filtros {{
    display: flex;
    gap: .5rem;
    flex-wrap: wrap;
  }}
  .filtro {{
    padding: .4rem .9rem;
    font-size: .82rem;
    border-radius: 20px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--muted);
    cursor: pointer;
    transition: all .15s;
    user-select: none;
  }}
  .filtro:hover  {{ border-color: var(--accent); color: var(--accent); }}
  .filtro.ativo  {{ background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 600; }}
  #contador {{
    font-size: .82rem;
    color: var(--muted);
    white-space: nowrap;
    align-self: center;
  }}

  /* ── LISTA ── */
  main {{ padding: 1.5rem 2rem; }}
  #lista {{ list-style: none; }}

  .item {{
    display: flex;
    align-items: flex-start;
    gap: .75rem;
    padding: .75rem .9rem;
    border: 1px solid transparent;
    border-radius: var(--radius);
    transition: all .12s;
    text-decoration: none;
    color: inherit;
    margin-bottom: .35rem;
  }}
  .item:hover {{
    background: var(--surface);
    border-color: var(--border);
    transform: translateX(2px);
  }}
  .item-badge {{
    flex-shrink: 0;
    width: 24px; height: 24px;
    border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    font-size: .72rem;
    font-weight: 700;
    margin-top: 1px;
  }}
  .item-badge.p0 {{ background: rgba(247,129,102,.15); color: var(--p0); }}
  .item-badge.p1 {{ background: rgba(210,168,255,.15); color: var(--p1); }}
  .item-badge.pn {{ background: rgba(88,166,255,.1);   color: var(--accent); }}
  .item-body {{ flex: 1; min-width: 0; }}
  .item-titulo {{
    font-size: .9rem;
    font-weight: 500;
    color: var(--text);
    word-break: break-word;
    line-height: 1.4;
    margin-bottom: .2rem;
  }}
  .item-url {{
    font-size: .75rem;
    color: var(--muted);
    word-break: break-all;
  }}
  .item-open {{
    flex-shrink: 0;
    opacity: 0;
    transition: opacity .12s;
    color: var(--accent);
    font-size: .8rem;
    padding: .25rem .5rem;
    border-radius: 6px;
    background: rgba(88,166,255,.1);
    border: 1px solid rgba(88,166,255,.2);
    white-space: nowrap;
    align-self: center;
    text-decoration: none;
  }}
  .item:hover .item-open {{ opacity: 1; }}

  .oculto {{ display: none !important; }}

  /* ── VAZIO ── */
  #vazio {{
    display: none;
    text-align: center;
    padding: 4rem 1rem;
    color: var(--muted);
  }}
  #vazio .vazio-icon {{ font-size: 3rem; margin-bottom: 1rem; }}
  #vazio p {{ font-size: .95rem; }}

  /* ── FOOTER ── */
  footer {{
    margin: 2rem 2rem 3rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--border);
    color: var(--muted);
    font-size: .8rem;
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: .5rem;
  }}
  footer a {{ color: var(--accent); text-decoration: none; }}
  footer a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>

<header>
  <div class="header-top">
    <div class="logo">🗂</div>
    <h1>
      {self.dominio}
      <small>Indice Offline &mdash; arquivado em {data_arquivo}</small>
    </h1>
  </div>

  <div class="stats">
    <div class="stat">
      <span class="stat-icon">📄</span>
      <div>
        <div class="stat-val">{len(self._paginas)}</div>
        <div class="stat-lbl">Paginas</div>
      </div>
    </div>
    <div class="stat">
      <span class="stat-icon">📦</span>
      <div>
        <div class="stat-val">{self._baixados}</div>
        <div class="stat-lbl">Arquivos</div>
      </div>
    </div>
    <div class="stat">
      <span class="stat-icon">💾</span>
      <div>
        <div class="stat-val">{tam_legivel(self._bytes)}</div>
        <div class="stat-lbl">Baixados</div>
      </div>
    </div>
    <div class="stat">
      <span class="stat-icon">⚠️</span>
      <div>
        <div class="stat-val">{self._erros}</div>
        <div class="stat-lbl">Erros</div>
      </div>
    </div>
  </div>

  <div class="controles">
    <input id="busca" type="search" placeholder="Buscar pagina ou URL..." autocomplete="off" autofocus>
    <div class="filtros">
      <span class="filtro ativo" data-prof="-1">Todas</span>
      <span class="filtro" data-prof="0">Raiz</span>
      <span class="filtro" data-prof="1">Nivel 1</span>
      <span class="filtro" data-prof="2+">Nivel 2+</span>
    </div>
    <span id="contador"></span>
  </div>
</header>

<main>
  <ul id="lista"></ul>
  <div id="vazio">
    <div class="vazio-icon">🔍</div>
    <p>Nenhuma pagina encontrada para "<span id="busca-termo"></span>"</p>
  </div>
</main>

<footer>
  <span>Gerado por BaixadorOffline</span>
  <a href="{self.url_inicial}" target="_blank">{self.url_inicial}</a>
</footer>

<script>
const PAGINAS = {dados_js};

const lista   = document.getElementById('lista');
const vazio   = document.getElementById('vazio');
const busca   = document.getElementById('busca');
const contador= document.getElementById('contador');
const filtros = document.querySelectorAll('.filtro');

// Renderiza todos os itens
function criarItem(pg) {{
  const li = document.createElement('li');
  li.className = 'item';

  const badgeCls = pg.prof === 0 ? 'p0' : pg.prof === 1 ? 'p1' : 'pn';
  const badgeTxt = pg.prof === 0 ? 'R' : String(pg.prof);

  li.innerHTML = `
    <span class="item-badge ${{badgeCls}}">${{badgeTxt}}</span>
    <div class="item-body">
      <div class="item-titulo">${{pg.titulo}}</div>
      <div class="item-url">${{pg.url}}</div>
    </div>
    <a class="item-open" href="${{pg.rel}}" title="Abrir pagina offline">Abrir ↗</a>
  `;
  li.querySelector('.item-open').addEventListener('click', e => e.stopPropagation());
  li.addEventListener('click', () => window.open(pg.rel, '_blank'));
  li.style.cursor = 'pointer';
  return li;
}}

let filtroAtual = -1;  // -1 = todos

function renderizar() {{
  const q    = busca.value.toLowerCase().trim();
  const elems = lista.querySelectorAll('li');
  let visiveis = 0;

  PAGINAS.forEach((pg, i) => {{
    const el = elems[i];
    if (!el) return;
    const textoMatch = !q || pg.titulo.toLowerCase().includes(q) || pg.url.toLowerCase().includes(q);
    const profMatch  = filtroAtual === -1
      || (filtroAtual === '2+' ? pg.prof >= 2 : pg.prof === filtroAtual);
    if (textoMatch && profMatch) {{
      el.classList.remove('oculto');
      visiveis++;
    }} else {{
      el.classList.add('oculto');
    }}
  }});

  const total = PAGINAS.length;
  contador.textContent = visiveis === total ? `${{total}} paginas` : `${{visiveis}} de ${{total}}`;
  document.getElementById('busca-termo').textContent = q;
  vazio.style.display = visiveis === 0 ? 'block' : 'none';
}}

// Popula a lista uma vez
PAGINAS.forEach(pg => lista.appendChild(criarItem(pg)));
contador.textContent = `${{PAGINAS.length}} paginas`;

busca.addEventListener('input', renderizar);

filtros.forEach(f => {{
  f.addEventListener('click', () => {{
    filtros.forEach(x => x.classList.remove('ativo'));
    f.classList.add('ativo');
    const val = f.dataset.prof;
    filtroAtual = val === '-1' ? -1 : val === '2+' ? '2+' : Number(val);
    renderizar();
  }});
}});
</script>
</body>
</html>"""

        idx = self.pasta / "_indice_offline.html"
        idx.write_text(html, encoding="utf-8")
        log.info(f"Indice: {idx.resolve()}")

    def crawl(self):
        inicio = time.time()
        if self.modo_atualizar:
            log.info("MODO ATUALIZAR INTELIGENTE: verificando o que mudou no servidor...")
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

                novos = submeter()
                with self._lock:
                    b, pend, ativos, pul = self._baixados, len(self._fila), len(futuros), self._pulados
                if self.modo_atualizar:
                    print(f"\r  Atualizados: {b}  |  Sem mudanca: {pul}  |  Fila: {pend}  |  Ativos: {ativos}    ", end="", flush=True)
                else:
                    print(f"\r  Baixados: {b}  |  Na fila: {pend}  |  Ativos: {ativos}    ", end="", flush=True)
                if not done and not novos and not futuros: break

        print()
        self._salvar_meta()
        self._gerar_indice()
        self._relatorio(time.time() - inicio)

    def _relatorio(self, dur):
        log.info("=" * 65)
        if self.modo_atualizar:
            log.info(f"Atualizacao inteligente concluida!")
            log.info(f"   Arquivos atualizados : {self._atualizados}")
            log.info(f"   Sem mudanca (pulados): {self._pulados}")
        else:
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
    parser.add_argument("--cloud",        action="store_true", help="Bypass Cloudflare automatico")
    parser.add_argument("--captcha",      action="store_true", help="Abrir navegador para resolver CAPTCHA manualmente")
    parser.add_argument("--atualizar",    "-a", action="store_true",
                        help="Atualizar site ja baixado (so baixa o que mudou, via ETag/Last-Modified)")
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

    print()
    try:
        b = BaixadorOffline(url,
                            workers=args.workers,
                            prof_max=args.profundidade,
                            delay=args.delay,
                            subdominios=args.subdominios,
                            modo_cloud=args.cloud,
                            modo_captcha=args.captcha,
                            modo_atualizar=args.atualizar)
        b.crawl()
    except KeyboardInterrupt:
        print("\n\nInterrompido. O conteudo baixado ate agora esta salvo.")

if __name__ == "__main__":
    main()
