#!/usr/bin/env python3
# BAIXADOR DE SITE — MODO OFFLINE TOTAL
# Uso basico:   python3 baixar_site_offline.py https://exemplo.com
# Atualizar:    python3 baixar_site_offline.py https://exemplo.com --atualizar
# Cloudflare:   python3 baixar_site_offline.py https://exemplo.com --cloud
# TLS bypass:   python3 baixar_site_offline.py https://exemplo.com --tls
# CAPTCHA:      python3 baixar_site_offline.py https://exemplo.com --captcha
# Anti-bot:     python3 baixar_site_offline.py https://exemplo.com --furtivo
# Debug:        python3 baixar_site_offline.py https://exemplo.com --verbose
#
# NOVIDADES:
#   --tls   Usa curl_cffi para imitar o fingerprint TLS do Chrome real.
#           Resolve bloqueios que --cloud nao resolve (PerimeterX, DataDome,
#           Cloudflare avancado). Nao precisa instalar o Chrome.
#           Instala automaticamente: pip install curl_cffi

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

def importar_curl_cffi():
    try:
        from curl_cffi.requests import Session as CurlSession
        return CurlSession
    except ImportError:
        print("Instalando curl_cffi (fingerprint TLS do Chrome real)...")
        instalar("curl_cffi")
        from curl_cffi.requests import Session as CurlSession
        return CurlSession

def importar_selenium():
    try:
        import undetected_chromedriver as uc
        return uc
    except ImportError:
        print("Instalando undetected-chromedriver...")
        instalar("undetected-chromedriver selenium")
        import undetected_chromedriver as uc
        return uc

import random

requests_lib, BeautifulSoup = importar_requests()

TIMEOUT        = 30
MAX_RETRIES    = 3
DELAY          = 0.3
WORKERS_PADRAO = 5

# ── Pool de perfis de navegador reais ─────────────────────────────────────────
# Cada perfil tem: User-Agent + Sec-CH-UA + plataforma + versao do Chrome/Firefox
# Misturar Chrome, Edge e Firefox dificulta fingerprinting por UA.
PERFIS_NAVEGADOR = [
    # Chrome 134 / Windows
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "Sec-CH-UA": '"Chromium";v="134", "Google Chrome";v="134", "Not-A.Brand";v="24"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
    },
    # Chrome 133 / Windows
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Sec-CH-UA": '"Google Chrome";v="133", "Not:A-Brand";v="24", "Chromium";v="133"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
    },
    # Chrome 134 / macOS
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "Sec-CH-UA": '"Chromium";v="134", "Google Chrome";v="134", "Not-A.Brand";v="24"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"macOS"',
    },
    # Chrome 132 / Linux
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
        "Sec-CH-UA": '"Chromium";v="132", "Google Chrome";v="132", "Not-A.Brand";v="24"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Linux"',
    },
    # Edge 134 / Windows
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 Edg/134.0.0.0",
        "Sec-CH-UA": '"Chromium";v="134", "Microsoft Edge";v="134", "Not-A.Brand";v="24"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
    },
    # Firefox 136 / Windows
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0",
        "Sec-CH-UA": None,  # Firefox nao envia Sec-CH-UA
        "Sec-CH-UA-Mobile": None,
        "Sec-CH-UA-Platform": None,
    },
    # Firefox 135 / Linux
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0",
        "Sec-CH-UA": None,
        "Sec-CH-UA-Mobile": None,
        "Sec-CH-UA-Platform": None,
    },
    # Safari 18 / macOS
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 15_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3.1 Safari/605.1.15",
        "Sec-CH-UA": None,
        "Sec-CH-UA-Mobile": None,
        "Sec-CH-UA-Platform": None,
    },
]

def sortear_perfil():
    """Retorna um perfil de navegador aleatorio do pool."""
    return random.choice(PERFIS_NAVEGADOR)

def headers_navegador(perfil, url_pagina_atual=None, eh_asset=False):
    """
    Monta o conjunto completo de headers HTTP que um navegador real envia.
    - perfil: dicionario do PERFIS_NAVEGADOR
    - url_pagina_atual: URL da pagina que gerou este pedido (para Referer e Sec-Fetch-Site)
    - eh_asset: True se for CSS/JS/imagem (muda Sec-Fetch-Dest e Sec-Fetch-Mode)
    """
    eh_firefox = "Firefox" in perfil["User-Agent"]
    eh_safari  = "Safari" in perfil["User-Agent"] and "Chrome" not in perfil["User-Agent"]

    hdrs = {
        "User-Agent": perfil["User-Agent"],
        "Accept-Language": random.choice([
            "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "pt-BR,pt;q=0.9,en;q=0.8",
            "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7",
            "en-GB,en;q=0.9,pt;q=0.8",
        ]),
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "DNT": random.choice(["1", None]),   # alguns usuarios ativam, outros nao
    }

    # Accept varia conforme tipo do recurso
    if eh_asset:
        hdrs["Accept"] = "*/*"
        hdrs["Sec-Fetch-Dest"] = "script" if not eh_asset == "css" else "style"
        hdrs["Sec-Fetch-Mode"] = "no-cors"
        hdrs["Sec-Fetch-Site"] = "same-origin"
    else:
        hdrs["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
        hdrs["Sec-Fetch-Dest"] = "document"
        hdrs["Sec-Fetch-Mode"] = "navigate"
        hdrs["Sec-Fetch-Site"] = "same-origin" if url_pagina_atual else "none"
        hdrs["Sec-Fetch-User"] = "?1"
        hdrs["Upgrade-Insecure-Requests"] = "1"

    # Referer: simula navegacao natural dentro do site
    if url_pagina_atual:
        hdrs["Referer"] = url_pagina_atual

    # Headers exclusivos do Chromium (Chrome/Edge) — Firefox e Safari nao enviam
    if not eh_firefox and not eh_safari:
        if perfil.get("Sec-CH-UA"):
            hdrs["Sec-CH-UA"]          = perfil["Sec-CH-UA"]
            hdrs["Sec-CH-UA-Mobile"]   = perfil["Sec-CH-UA-Mobile"]
            hdrs["Sec-CH-UA-Platform"] = perfil["Sec-CH-UA-Platform"]

    # Remove entradas None (headers opcionais que nao foram sorteados)
    return {k: v for k, v in hdrs.items() if v is not None}

def delay_humano(base=DELAY, modo_furtivo=False):
    """
    Gera um delay com variacao aleatoria que imita comportamento humano.
    - modo_furtivo: delays maiores, pausa longa ocasional (simula leitura)
    """
    if modo_furtivo:
        d = base + random.uniform(1.5, 4.5)
        # ~10% de chance de uma pausa mais longa (usuario "lendo" a pagina)
        if random.random() < 0.10:
            d += random.uniform(3.0, 8.0)
    else:
        # Variacao de ±60% no delay normal
        d = base * random.uniform(0.4, 1.6)
        # ~5% de chance de pausa curta extra
        if random.random() < 0.05:
            d += random.uniform(0.5, 2.0)
    time.sleep(max(d, 0.1))

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
    # Normaliza prefixo "www": trata example.com e www.example.com como o mesmo dominio.
    # Isso corrige o caso em que o usuario digita https://example.com e o servidor
    # redireciona para https://www.example.com (redirect muito comum).
    h_bare = h[4:] if h.startswith("www.") else h
    d_bare = dominio[4:] if dominio.startswith("www.") else dominio
    if h_bare and h_bare == d_bare: return True
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
        self.user_agent = sortear_perfil()["User-Agent"]
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
                 subdominios=False, modo_cloud=False, modo_captcha=False, modo_atualizar=False,
                 modo_js=False, modo_furtivo=False, modo_tls=False):

        # Remove fragmento (#ancora) da URL inicial — servidor nunca o recebe
        _p0 = urlparse(url_inicial.rstrip("/"))
        self.url_inicial   = urlunparse(_p0._replace(fragment=""))
        p = urlparse(self.url_inicial)
        self.dominio       = p.netloc
        self.esquema       = p.scheme
        self.workers       = workers
        self.prof_max      = prof_max
        self.delay         = delay
        self.subdominios   = subdominios
        self.modo_cloud    = modo_cloud
        self.modo_captcha  = modo_captcha
        self.modo_atualizar = modo_atualizar
        self.modo_js       = modo_js
        self.modo_furtivo  = modo_furtivo
        self.modo_tls      = modo_tls

        # Perfil de navegador fixo para esta sessao (mas trocado a cada retry)
        self._perfil_atual = sortear_perfil()
        # Rastreia a ultima URL visitada por thread para construir o Referer
        self._ultimo_referer: dict = {}  # thread_id -> url

        self.pasta = Path(sanitizar(self.dominio))
        self.pasta.mkdir(parents=True, exist_ok=True)
        for sub in ("assets/imagens","assets/css","assets/js","assets/fontes",
                    "assets/midia","assets/audio","assets/videos","assets/docs",
                    "assets/dados","assets/outros"):
            (self.pasta / sub).mkdir(parents=True, exist_ok=True)

        if modo_tls:
            log.info("Modo TLS ativo -- usando curl_cffi (fingerprint Chrome real)")
            CurlSession = importar_curl_cffi()
            # impersonate="chrome132" faz o curl_cffi usar o mesmo TLS handshake
            # que o Chrome 132 usaria — invisivel para sistemas anti-bot modernos.
            self.session = CurlSession(impersonate="chrome132")
        elif modo_cloud:
            log.info("Modo Cloudflare ativado -- usando cloudscraper")
            cs = importar_cloudscraper()
            self.session = cs.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "mobile": False}
            )
        else:
            self.session = requests_lib.Session()

        self.session.headers.update({
            "User-Agent":        self._perfil_atual["User-Agent"],
            "Accept":            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language":   "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding":   "gzip, deflate, br",
            "Connection":        "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
        # Adiciona Client Hints do Chromium (quando o perfil suporta)
        if self._perfil_atual.get("Sec-CH-UA"):
            self.session.headers.update({
                "Sec-CH-UA":          self._perfil_atual["Sec-CH-UA"],
                "Sec-CH-UA-Mobile":   self._perfil_atual["Sec-CH-UA-Mobile"],
                "Sec-CH-UA-Platform": self._perfil_atual["Sec-CH-UA-Platform"],
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

        # Driver JS (Chrome headless) — um unico driver com lock para modo --js
        self._js_driver  = None
        self._js_lock    = threading.Lock()
        if modo_js:
            self._iniciar_driver_js()

        # Metadados HTTP (ETag / Last-Modified) persistidos entre sessoes
        self._arquivo_meta = self.pasta / "_meta.json"
        self._meta = self._carregar_meta()

        modos = []
        if modo_tls:       modos.append("TLS fingerprint (curl_cffi / Chrome real)")
        if modo_cloud:     modos.append("Cloudflare bypass")
        if modo_captcha:   modos.append("CAPTCHA manual")
        if modo_atualizar: modos.append("ATUALIZAR (inteligente por ETag/Last-Modified)")
        if modo_js:        modos.append("JS rendering (Chrome headless)")
        if modo_furtivo:   modos.append("FURTIVO (anti-deteccao intensificado)")
        if not modos:      modos.append("padrao")

        log.info(f"Site:    {self.url_inicial}")
        log.info(f"Pasta:   {self.pasta.resolve()}")
        log.info(f"Modo:    {' + '.join(modos)}")
        log.info(f"Workers: {self.workers}  |  Profundidade: {'ilimitada' if not self.prof_max else self.prof_max}")

    # ── Driver JS (Chrome headless) ────────────────────────────────────────────

    def _iniciar_driver_js(self):
        uc = importar_selenium()
        log.info("Iniciando Chrome headless para renderizacao JS...")
        options = uc.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1280,900")
        options.add_argument(f"--user-agent={self._perfil_atual['User-Agent']}")

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
        try:
            self._js_driver = uc.Chrome(options=options, headless=True, version_main=versao)
            log.info("Chrome headless pronto.")
        except Exception as e:
            log.warning(f"Nao foi possivel iniciar Chrome headless: {e}")
            log.warning("O modo --js sera ignorado. Instale o Google Chrome.")
            self._js_driver = None

    def _encerrar_driver_js(self):
        if self._js_driver:
            try: self._js_driver.quit()
            except Exception: pass
            self._js_driver = None

    def _get_html_js(self, url):
        """Renderiza a pagina com Chrome headless e retorna o HTML completo apos JS."""
        if not self._js_driver:
            return None
        with self._js_lock:
            try:
                self._js_driver.get(url)
                # Aguarda o corpo da pagina ter conteudo real (max 15s)
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                from selenium.webdriver.common.by import By
                try:
                    WebDriverWait(self._js_driver, 15).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                except Exception:
                    pass
                time.sleep(1.5)  # Aguarda scripts adicionais terminarem
                return self._js_driver.page_source.encode("utf-8")
            except Exception as e:
                log.debug(f"Erro JS rendering {url}: {e}")
                return None

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

    def _hdrs_request(self, url, referer=None, eh_asset=False):
        """Monta headers completos para uma requisicao, usando o perfil atual."""
        with self._lock:
            perfil = self._perfil_atual
        return headers_navegador(perfil, url_pagina_atual=referer, eh_asset=eh_asset)

    def _trocar_perfil(self):
        """Sorteia um novo perfil de navegador (chamado apos deteccao de bloqueio)."""
        with self._lock:
            self._perfil_atual = sortear_perfil()
        log.info(f"Perfil de navegador trocado: {self._perfil_atual['User-Agent'][:60]}...")

    def _get(self, url, stream=False, referer=None, eh_asset=False):
        for t in range(1, MAX_RETRIES + 1):
            try:
                hdrs = self._hdrs_request(url, referer=referer, eh_asset=eh_asset)
                r = self.session.get(url, timeout=TIMEOUT, stream=stream,
                                     allow_redirects=True, headers=hdrs)

                # 429 Too Many Requests: espera o Retry-After ou faz backoff exponencial
                if r.status_code == 429:
                    retry_after = int(r.headers.get("Retry-After", 0))
                    espera = retry_after if retry_after > 0 else (2 ** t) * 3 + random.uniform(1, 4)
                    log.warning(f"429 (limite de requisicoes) em {url}. Aguardando {espera:.1f}s...")
                    time.sleep(espera)
                    self._trocar_perfil()
                    continue

                r.raise_for_status()
                if self._detectar_captcha(r):
                    log.warning(f"CAPTCHA/bloqueio detectado em: {url}")
                    log.warning("Use --captcha para resolver manualmente ou --cloud para Cloudflare.")
                    self._trocar_perfil()
                    return None
                return r
            except Exception as e:
                if t == MAX_RETRIES:
                    log.warning(f"Falha ao baixar: {url} -> {e}")
                    return None
                backoff = (t * 1.5) + random.uniform(0, 1.0)
                time.sleep(backoff)
        return None

    def _get_opcional(self, url):
        """Versao sem retry para recursos opcionais (robots.txt, sitemap.xml)."""
        try:
            hdrs = self._hdrs_request(url)
            r = self.session.get(url, timeout=10, allow_redirects=True, headers=hdrs)
            r.raise_for_status()
            if self._detectar_captcha(r):
                return None
            return r
        except Exception:
            return None

    def _get_condicional(self, url, stream=False, referer=None):
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

        hdrs_cond = {}
        if meta.get("etag"):
            hdrs_cond["If-None-Match"] = meta["etag"]
        if meta.get("last_modified"):
            hdrs_cond["If-Modified-Since"] = meta["last_modified"]

        for t in range(1, MAX_RETRIES + 1):
            try:
                hdrs = self._hdrs_request(url, referer=referer)
                hdrs.update(hdrs_cond)
                r = self.session.get(url, timeout=TIMEOUT, stream=stream,
                                     allow_redirects=True, headers=hdrs)
                if r.status_code == 304:
                    return None, False
                if r.status_code == 429:
                    retry_after = int(r.headers.get("Retry-After", 0))
                    espera = retry_after if retry_after > 0 else (2 ** t) * 3 + random.uniform(1, 4)
                    log.warning(f"429 em {url}. Aguardando {espera:.1f}s...")
                    time.sleep(espera)
                    self._trocar_perfil()
                    continue
                r.raise_for_status()
                if self._detectar_captcha(r):
                    log.warning(f"CAPTCHA/bloqueio detectado em: {url}")
                    return None, True
                return r, True
            except Exception as e:
                if t == MAX_RETRIES:
                    log.debug(f"Falha: {url} -> {e}")
                    return None, True
                time.sleep((t * 1.5) + random.uniform(0, 1.0))
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
        eh_css   = ext == ".css"

        # url_base serve como Referer (asset foi requisitado pela pagina pai)
        if self.modo_atualizar and ja_existe:
            r, mudou = self._get_condicional(url, stream=eh_midia, referer=url_base)
            if not mudou:
                with self._lock: self._pulados += 1
                return str(caminho)
            if r is None:
                with self._lock: self._erros += 1
                return None
        else:
            r = self._get(url, stream=eh_midia, referer=url_base,
                          eh_asset="css" if eh_css else True)
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
            log.warning(f"Erro salvando {url}: {e}")
            with self._lock: self._erros += 1
            return None

        delay_humano(self.delay, self.modo_furtivo)
        return str(caminho)

    def _processar_html(self, url, conteudo, prof):
        # Tenta lxml primeiro (mais rapido); se falhar usa html.parser (mais compativel)
        try:
            soup = BeautifulSoup(conteudo, "lxml")
        except Exception:
            try:
                soup = BeautifulSoup(conteudo, "html.parser")
            except Exception as e:
                log.warning(f"Falha ao interpretar HTML de {url}: {e}")
                raise
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

        # Referer: paginas de nivel 0 vem "de fora" (sem referer), paginas filhas
        # usam a URL mae que as agendou — comportamento identico a um navegador real.
        referer = self.url_inicial if prof > 0 else None

        ja_existe_local = url2path(url, self.pasta, pagina=True).exists()

        if self.modo_atualizar and ja_existe_local:
            r, mudou = self._get_condicional(url, referer=referer)
            if not mudou:
                with self._lock: self._pulados += 1
                log.debug(f"Sem mudancas: {url}")
                return
            if r is None:
                with self._lock: self._erros += 1
                return
        else:
            r = self._get(url, referer=referer)
            if not r:
                with self._lock: self._erros += 1
                return

        ct = r.headers.get("Content-Type", "").lower()
        url_final = r.url or url

        # Detecta redirect para domínio diferente e avisa o usuario
        dominio_final = urlparse(url_final).netloc
        if dominio_final and not mesmo_dominio(url_final, self.dominio, self.subdominios):
            log.warning(f"Redirect para domínio diferente: {self.dominio} → {dominio_final}")
            log.warning("O conteudo sera salvo, mas links externos nao serao seguidos.")
            log.warning("Se o site principal esta em outro dominio, tente baixar diretamente por ele.")

        if "text/html" in ct:
            caminho = url2path(url_final, self.pasta, pagina=True)
            if not caminho.suffix: caminho = caminho.with_suffix(".html")

            # Modo JS: substitui o conteudo pelo HTML renderizado com JavaScript
            if self.modo_js and self._js_driver:
                conteudo_bruto = self._get_html_js(url_final)
                if conteudo_bruto:
                    conteudo = self._processar_html(url_final, conteudo_bruto, prof)
                    titulo_raw = conteudo_bruto
                else:
                    # Fallback para resposta normal se JS falhar
                    conteudo = self._processar_html(url_final, r.content, prof)
                    titulo_raw = r.content
            else:
                conteudo = self._processar_html(url_final, r.content, prof)
                titulo_raw = r.content

            titulo = url_final
            try:
                try:
                    s = BeautifulSoup(titulo_raw, "lxml")
                except Exception:
                    s = BeautifulSoup(titulo_raw, "html.parser")
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
        delay_humano(self.delay, self.modo_furtivo)

    def _ler_sitemap(self, sm_url):
        r = self._get_opcional(sm_url)
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
        r = self._get_opcional(f"{self.esquema}://{self.dominio}/robots.txt")
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
        if self.modo_furtivo:
            log.info(f"MODO FURTIVO ativo — perfil: {self._perfil_atual['User-Agent'][:72]}...")
        log.info("Verificando sitemap...")
        self._descobrir_sitemap()
        self._agendar(self.url_inicial, 0, pagina=True)

        # No modo furtivo embaralha a fila de URLs antes de começar, para que o
        # padrão de acesso nao seja sequencial/previsivel (comportamento de crawler).
        if self.modo_furtivo and len(self._fila) > 1:
            lista_fila = list(self._fila)
            random.shuffle(lista_fila)
            self._fila = deque(lista_fila)
            log.info(f"Fila embaralhada ({len(self._fila)} URLs) para acesso nao-sequencial.")

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
                    except Exception as e: log.warning(f"Worker erro: {e}")

                novos = submeter()
                with self._lock:
                    b, pend, ativos, pul = self._baixados, len(self._fila), len(futuros), self._pulados
                if self.modo_atualizar:
                    print(f"\r  Atualizados: {b}  |  Sem mudanca: {pul}  |  Fila: {pend}  |  Ativos: {ativos}    ", end="", flush=True)
                else:
                    print(f"\r  Baixados: {b}  |  Na fila: {pend}  |  Ativos: {ativos}    ", end="", flush=True)
                if not done and not novos and not futuros: break

        print()
        self._encerrar_driver_js()
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
    parser.add_argument("--tls",          action="store_true", help="Imitar fingerprint TLS do Chrome real via curl_cffi (resolve bloqueios avancados sem instalar Chrome)")
    parser.add_argument("--captcha",      action="store_true", help="Abrir navegador para resolver CAPTCHA manualmente")
    parser.add_argument("--js",           action="store_true",
                        help="Renderizar paginas com Chrome headless (para sites que usam JavaScript)")
    parser.add_argument("--atualizar",    "-a", action="store_true",
                        help="Atualizar site ja baixado (so baixa o que mudou, via ETag/Last-Modified)")
    parser.add_argument("--furtivo",      "-f", action="store_true",
                        help="Modo anti-deteccao intensificado: UA aleatorio, delays humanos, fila embaralhada")
    parser.add_argument("--verbose",      "-v", action="store_true",
                        help="Mostrar mensagens de debug detalhadas (util para diagnosticar problemas)")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger("offline").setLevel(logging.DEBUG)

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
                            modo_js=args.js,
                            modo_atualizar=args.atualizar,
                            modo_furtivo=args.furtivo,
                            modo_tls=args.tls)
        b.crawl()
    except KeyboardInterrupt:
        print("\n\nInterrompido. O conteudo baixado ate agora esta salvo.")

if __name__ == "__main__":
    main()
