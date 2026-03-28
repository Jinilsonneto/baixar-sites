# 📥 Baixador de Site Offline

Salva um site inteiro no seu computador para leitura offline — HTML, CSS, imagens, vídeos, fontes e tudo mais. Funciona com um único arquivo Python, sem precisar instalar nada manualmente.

---

## ✨ Funcionalidades

- **Download completo** de sites: HTML, CSS, JS, imagens, vídeos, áudio, fontes, documentos
- **Reescrita automática de links** — todos os links internos são convertidos para caminhos locais, o site abre no navegador sem conexão
- **Índice offline navegável** — gera uma página `_indice_offline.html` com busca e filtros por profundidade
- **Sitemap automático** — descobre e baixa URLs via `sitemap.xml` e `robots.txt`
- **Anti-detecção nativo** — pool de 8 perfis de navegador reais, headers completos de Chrome/Firefox/Safari/Edge, Referer contextual
- **Modo furtivo** — delays com variação humana, pausa longa aleatória, fila de URLs embaralhada
- **Bypass Cloudflare** — via `cloudscraper`
- **Resolução de CAPTCHA manual** — abre Chrome real, você resolve, ele continua
- **Renderização JavaScript** — Chrome headless via `undetected-chromedriver`
- **Atualização inteligente** — baixa só o que mudou, usando `ETag` e `Last-Modified`
- **Múltiplos workers** — download paralelo configurável
- **Backoff automático em 429** — respeita `Retry-After` ou espera exponencial com jitter
- **Troca de perfil após bloqueio** — muda User-Agent e headers automaticamente ao ser detectado

---

## ⚙️ Requisitos

- Python 3.8 ou superior
- Linux (testado no Linux Mint / Ubuntu)

As dependências são instaladas automaticamente na primeira execução:

| Dependência | Para que serve |
|---|---|
| `requests` | Download HTTP básico |
| `beautifulsoup4` + `lxml` | Parsing de HTML |
| `cloudscraper` | Bypass Cloudflare (`--cloud`) |
| `undetected-chromedriver` + `selenium` | Modo JS e CAPTCHA (`--js`, `--captcha`) |

> Para os modos `--js` e `--captcha` é necessário ter o **Google Chrome** instalado.

---

## 🚀 Como usar

### Forma mais simples

```bash
python3 baixar_site_offline.py
```

O script vai pedir a URL interativamente.

### Passando a URL direto

```bash
python3 baixar_site_offline.py https://exemplo.com
```

O site é salvo em uma pasta com o nome do domínio no diretório atual.

---

## 🔧 Opções

| Opção | Atalho | Padrão | Descrição |
|---|---|---|---|
| `--workers N` | `-w` | `5` | Número de downloads paralelos |
| `--profundidade N` | `-p` | `0` (ilimitado) | Profundidade máxima de links a seguir |
| `--delay N` | `-d` | `0.3` | Delay base entre requisições (em segundos) |
| `--subdominios` | `-s` | desativado | Incluir subdomínios do site |
| `--atualizar` | `-a` | — | Só baixa o que mudou desde o último download |
| `--furtivo` | `-f` | — | Modo anti-detecção intensificado |
| `--cloud` | — | — | Bypass automático de Cloudflare |
| `--captcha` | — | — | Abre navegador para resolver CAPTCHA manualmente |
| `--js` | — | — | Renderiza JavaScript com Chrome headless |
| `--verbose` | `-v` | — | Mostra logs de debug detalhados |

---

## 📖 Exemplos de uso

**Download básico:**
```bash
python3 baixar_site_offline.py https://exemplo.com
```

**Site que bloqueia bots (modo furtivo):**
```bash
python3 baixar_site_offline.py https://exemplo.com --furtivo
```

**Site com Cloudflare:**
```bash
python3 baixar_site_offline.py https://exemplo.com --cloud
```

**Site com Cloudflare + modo furtivo:**
```bash
python3 baixar_site_offline.py https://exemplo.com --cloud --furtivo
```

**Site que exige JavaScript para renderizar o conteúdo:**
```bash
python3 baixar_site_offline.py https://exemplo.com --js
```

**Site com CAPTCHA ou login:**
```bash
python3 baixar_site_offline.py https://exemplo.com --captcha
```
> Um Chrome real abre. Você resolve o CAPTCHA/faz login. Pressione Enter e o download continua com seus cookies.

**Atualizar site já baixado (só baixa o que mudou):**
```bash
python3 baixar_site_offline.py https://exemplo.com --atualizar
```

**Download com mais workers e profundidade limitada:**
```bash
python3 baixar_site_offline.py https://exemplo.com -w 10 -p 3
```

**Ver todos os erros detalhadamente:**
```bash
python3 baixar_site_offline.py https://exemplo.com --verbose
```

**Combinando opções:**
```bash
python3 baixar_site_offline.py https://exemplo.com --furtivo --js -w 3 -d 2.0
```

---

## 📁 Estrutura da pasta gerada

```
exemplo.com/
├── index.html                   ← Página inicial do site
├── _indice_offline.html         ← Índice navegável com busca
├── _meta.json                   ← Metadados HTTP (ETag, Last-Modified)
├── sobre/
│   └── index.html
├── artigos/
│   └── meu-post/
│       └── index.html
└── assets/
    ├── imagens/
    ├── css/
    ├── js/
    ├── fontes/
    ├── audio/
    ├── videos/
    ├── docs/
    ├── dados/
    └── outros/
```

---

## 🛡️ Sistema anti-detecção

O script imita o comportamento de um navegador real de várias formas:

**Pool de perfis de navegador reais** — a cada execução, um perfil é sorteado aleatoriamente entre:
- Chrome 122, 123, 124 (Windows, macOS, Linux)
- Edge 124 (Windows)
- Firefox 124, 125 (Windows, Linux)
- Safari 17 (macOS)

**Headers HTTP completos** — além do `User-Agent`, envia todos os headers que um navegador real enviaria:
- `Sec-CH-UA`, `Sec-CH-UA-Platform`, `Sec-CH-UA-Mobile` (Client Hints do Chrome/Edge)
- `Sec-Fetch-Dest`, `Sec-Fetch-Mode`, `Sec-Fetch-Site`, `Sec-Fetch-User`
- `Referer` contextual (baseado na página que gerou o link)
- `Accept-Language` variado aleatoriamente

**Comportamento em caso de bloqueio:**
- Ao receber `429 Too Many Requests`, respeita o `Retry-After` do servidor ou aplica backoff exponencial com jitter
- Troca automaticamente de perfil de navegador após qualquer detecção

**Modo `--furtivo`** intensifica tudo:
- Delays de 1.5 a 4.5 segundos entre requisições
- 10% de chance de pausa longa de 3 a 8 segundos (simula leitura)
- Fila de URLs embaralhada (bots normalmente acessam em ordem sequencial)

---

## 🗺️ Índice offline

Após o download, o arquivo `_indice_offline.html` oferece:

- Listagem de todas as páginas baixadas
- Busca por título ou URL
- Filtro por profundidade (raiz, nível 1, nível 2+)
- Contador de páginas visíveis
- Botão de acesso direto a cada página

---

## ❓ Solução de problemas

**O site baixou só 1 página**
O servidor pode estar redirecionando para um domínio diferente (ex: `exemplo.com` → `www.exemplo.com`). Use `--verbose` para ver um aviso de redirect e tente a URL com `www`.

**Erro de CAPTCHA ou acesso negado**
Tente em ordem:
1. `--furtivo` — muda o perfil e delays
2. `--cloud` — para sites com Cloudflare
3. `--captcha` — você resolve manualmente no navegador

**Site não carrega sem JavaScript**
Use `--js`. Requer Google Chrome instalado.

**Download muito lento**
Aumente os workers: `-w 10`. Mas cuidado — mais workers aumentam a chance de detecção como bot.

**Ver o que está dando errado**
```bash
python3 baixar_site_offline.py https://exemplo.com --verbose
```

---

## 📝 Licença

Uso livre para fins pessoais e educacionais.
