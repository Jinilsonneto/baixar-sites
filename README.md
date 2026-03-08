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
    5. O programa continua o download com o seu captcha manual


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
 --atualizar            -a       Atualizar site já baixado (veja seção abaixo)

Exemplos de uso combinado:

    python3 baixar_site_offline.py https://exemplo.com -w 10
    python3 baixar_site_offline.py https://exemplo.com --cloud -w 8
    python3 baixar_site_offline.py https://exemplo.com --captcha -p 3
    python3 baixar_site_offline.py https://exemplo.com --cloud --captcha -w 5 -s
    python3 baixar_site_offline.py https://exemplo.com --atualizar


══════════════════════════════════════════════════════════════════

 MODO --atualizar — COMO FUNCIONA

══════════════════════════════════════════════════════════════════

O --atualizar serve para baixar novamente apenas o que mudou no site,
sem precisar baixar tudo do zero.

Como ele faz isso:

  No primeiro download normal, o programa salva automaticamente um
  arquivo chamado _meta.json dentro da pasta do site. Esse arquivo
  guarda um "carimbo" (ETag ou data de modificação) de cada arquivo
  baixado, que é fornecido pelo próprio servidor.

  Na próxima vez que você usar --atualizar, o programa pergunta ao
  servidor para cada arquivo: "isso aqui mudou desde o carimbo X?"

  - Se o servidor responder NÃO (código 304): o arquivo é pulado
    completamente, sem baixar nada.
  - Se o servidor responder SIM (código 200): o arquivo novo é
    baixado e substitui o antigo.

O progresso durante o --atualizar mostra:

    Atualizados: 12  |  Sem mudanca: 847  |  Fila: 200  |  Ativos: 5

Observação: sites que não enviam ETag nem Last-Modified (servidores
mal configurados) terão todos os arquivos baixados normalmente,
sem ganho de velocidade. Isso é raro mas pode acontecer.

Pausar e retomar o --atualizar:

  Você pode pausar com Ctrl+Z e retomar com fg a qualquer momento,
  inclusive trocando de rede Wi-Fi entre pausar e retomar.
  Cada arquivo é independente — nada se perde.


══════════════════════════════════════════════════════════════════

 ARQUIVOS GERADOS PELO PROGRAMA

══════════════════════════════════════════════════════════════════

 Dentro da pasta do site baixado você vai encontrar:

 index.html            Página inicial do site para abrir offline
 _indice_offline.html  Índice com todas as páginas, busca e filtros
 _meta.json            Carimbos de versão usados pelo --atualizar
                       (não apague se quiser usar o --atualizar depois)

 assets/
   imagens/            Fotos, ícones, banners
   css/                Folhas de estilo
   js/                 Scripts JavaScript
   fontes/             Arquivos de fonte (woff, ttf, etc.)
   videos/             Vídeos do site
   audio/              Áudios do site
   docs/               PDFs e documentos
   dados/              JSON, XML, YAML
   outros/             Demais arquivos


══════════════════════════════════════════════════════════════════

 DICAS IMPORTANTES

══════════════════════════════════════════════════════════════════

- Use cd ~/ para ir à pasta onde está o arquivo .py.
  O download do site será feito nessa mesma pasta.

- Se o site bloquear por excesso de requests, aumente o delay:
      python3 baixar_site_offline.py https://exemplo.com -d 1.5

- Se pausar com Ctrl+Z, retome com fg no mesmo terminal.
  Nunca use Ctrl+C para pausar — use apenas para cancelar de vez.
  Arquivos já baixados são pulados automaticamente.

- Para baixar 4 sites ao mesmo tempo, abra 4 terminais separados
  e rode um comando em cada.

- Formulários do site (comentários, login, busca) são desativados
  automaticamente no modo offline para não gerar downloads
  indesejados ao clicar.

- Após o download, abra no navegador:
      Página inicial:  pasta_do_site/index.html
      Índice completo: pasta_do_site/_indice_offline.html

══════════════════════════════════════════════════════════════════
