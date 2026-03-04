══════════════════════════════════════════════════════════════════

         TUTORIAL DE INSTALAÇÃO — BAIXADOR DE SITE OFFLINE
         
══════════════════════════════════════════════════════════════════

REQUISITO INICIAL
─────────────────
Você precisa ter o Python 3 instalado.
Para verificar, abra o terminal e digite:

    python3 --version

Se aparecer "Python 3.x.x" pode continuar.
Se não tiver, instale com:

    sudo apt install python3 python3-pip


══════════════════════════════════════════════════════════════════

PASSO 1 — DEPENDÊNCIAS BÁSICAS (obrigatório para todos os modos)

══════════════════════════════════════════════════════════════════

Instale as bibliotecas principais:

    pip3 install requests beautifulsoup4 lxml --break-system-packages

Isso permite usar o programa no modo normal, sem nenhum argumento extra.

Teste básico:

    python3 baixar_site_offline.py https://exemplo.com


══════════════════════════════════════════════════════════════════

 PASSO 2 — CLOUDFLARE (opcional, só se usar --cloud)
 
══════════════════════════════════════════════════════════════════


Se o site que você quer baixar usa proteção Cloudflare
(aquela tela "Checking your browser before accessing..."),
instale o cloudscraper:

    pip3 install cloudscraper --break-system-packages

Como usar:

    python3 baixar_site_offline.py https://exemplo.com --cloud

O programa passa pela verificação automaticamente, sem você fazer nada.


══════════════════════════════════════════════════════════════════

 PASSO 3 — CAPTCHA MANUAL (opcional, só se usar --captcha)
 
══════════════════════════════════════════════════════════════════


Se o site exige CAPTCHA (reCAPTCHA, hCaptcha, login, etc.),
você vai resolver na mão dentro de um navegador que o programa abre.

3.1 — Instale as bibliotecas:

    pip3 install undetected-chromedriver selenium --break-system-packages

3.2 — Instale o Google Chrome (necessário para o modo --captcha):

    wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    sudo apt install ./google-chrome-stable_current_amd64.deb

    OBS: O Chrome e o Chromium podem ficar instalados juntos sem conflito.
    OBS: Se o wget não funcionar, baixe o .deb manualmente em:
         https://www.google.com/chrome e instale com o comando acima.

Como usar:

    python3 baixar_site_offline.py https://exemplo.com --captcha

O que vai acontecer:
    1. Um Chrome real vai abrir na sua tela
    2. Resolva o CAPTCHA ou faça login normalmente
    3. Quando a página carregar, volte ao terminal
    4. Pressione ENTER
    5. O programa continua o download com sua sessão


══════════════════════════════════════════════════════════════════

 RESUMO — O QUE INSTALAR PARA CADA SITUAÇÃO
 
══════════════════════════════════════════════════════════════════


 Situação                          O que instalar
 
 ─────────────────────────────────────────────────────────────
 
 Site normal                       Passo 1 apenas
 Site com Cloudflare               Passo 1 + Passo 2
 Site com CAPTCHA                  Passo 1 + Passo 3
 Site com Cloudflare + CAPTCHA     Passo 1 + Passo 2 + Passo 3


══════════════════════════════════════════════════════════════════

 TODOS OS ARGUMENTOS DISPONÍVEIS
 
══════════════════════════════════════════════════════════════════


 Argumento              Atalho   Descrição
 
 ─────────────────────────────────────────────────────────────
 --workers 5            -w 5     Downloads simultâneos (padrão: 5)
 --profundidade 3       -p 3     Limite de níveis de links (0 = ilimitado)
 --delay 0.3            -d 0.3   Espera entre requests em segundos
 --subdominios          -s       Incluir subdomínios automaticamente
 --cloud                         Bypass Cloudflare automático
 --captcha                       Abrir navegador para resolver CAPTCHA
 --leve                          Modo leve para baixar sem travar 
 
Exemplos de uso combinado:

    python3 baixar_site_offline.py https://exemplo.com -w 10
    python3 baixar_site_offline.py https://exemplo.com --cloud -w 8
    python3 baixar_site_offline.py https://exemplo.com --captcha -p 3
    python3 baixar_site_offline.py https://exemplo.com --cloud --captcha -w 5 -s


══════════════════════════════════════════════════════════════════

 DICAS IMPORTANTES
 
══════════════════════════════════════════════════════════════════

- Use cd ~/ para pasta onde está o arquivo py. Nela também será feito o download do site.

- Se o site bloquear por excesso de requests, aumente o delay:
      python3 baixar_site_offline.py https://exemplo.com -d 1.5

- Se pausar com Ctrl+C, pode rodar de novo com a mesma URL.
  Arquivos já baixados são pulados automaticamente.

- Para baixar 4 sites ao mesmo tempo, abra 4 terminais separados
  e rode um comando em cada.

- Após o download, abra no navegador:
      Página inicial:  pasta_do_site/index.html
      Índice completo: pasta_do_site/_indice_offline.html

══════════════════════════════════════════════════════════════════
