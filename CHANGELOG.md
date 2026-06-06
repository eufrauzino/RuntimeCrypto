# Changelog - RuntimeCrypto

Todas as modificações notáveis neste projeto serão documentadas neste arquivo.

## [2.1.0] - 2026-06-06

### GUI Cryptomator-Style com CustomTkinter

Migração completa da interface de **System Tray puro (tkinter)** para uma aplicação com **janela principal
moderna** estilo Cryptomator, usando CustomTkinter. O core (`rclone_manager.py`) permaneceu intocado.

### Adicionado — Interface Principal (`gui/`)
- **`gui/janela_principal.py`:** Janela principal com header, área central scrollable de cards e footer.
  - Layout responsivo com `grid` — header, centro e footer se ajustam ao redimensionar.
  - Atualização inteligente: compara estado anterior dos cofres e só reconstroi cards se houve mudança (elimina flicker).
  - Botão (X) esconde para o tray, duplo clique no tray reabre.
- **`gui/card_cofre.py`:** Widget `CardCofre` com indicador colorido do provedor, nome, status e botão de ação.
  - Altura fixa de 76px por card para consistência visual.
  - Hover effect no card inteiro.
  - `BotaoNovoCofre` estilizado com borda tracejada.
- **`gui/dialogos.py`:** Diálogos modais modernos substituindo todos os `tkinter.simpledialog`:
  - `DialogoSenha` — entrada de senha com ícone de cadeado.
  - `DialogoMensagem` — info/erro/aviso com ícones e cores semânticas.
  - `DialogoNovoCofre` — wizard de criação em 2 abas (Provedor → Senha).
  - `DialogoImportarCofre` — wizard de importação em 2 abas (Provedor → Senhas).
  - `DialogoSeletorPastaRemota` — navegador visual de pastas remotas com `rclone lsd`.
  - `DialogoConfigVfs` — painel de 9 parâmetros VFS com restauração de padrões.
- **`tema_runtime.json`:** Tema CustomTkinter com paleta visual do projeto (`#0d1b2a` + `#10b981`).

### Adicionado — Importação de Cofre Existente
- **Fluxo completo para importar cofre já existente na nuvem:**
  1. Seleciona provedor (Google Drive, OneDrive, Dropbox, S3, Local).
  2. Informa senhas (password + password2/salt) e nome local.
  3. Para cloud: executa OAuth → abre navegador visual de pastas remotas.
  4. Para local: abre seletor nativo de pastas do Windows (`askdirectory`).
  5. Cria remoto crypt apontando para a pasta selecionada.
- **`DialogoSeletorPastaRemota`:** Navegação hierárquica com duplo clique para entrar em pastas, botão ⬆ para voltar, barra de caminho estilo console.
- **Carregamento assíncrono:** Listagem de pastas em thread separada com indicador "🔄 Carregando...".

### Adicionado — Métodos em `GerenciadorRClone`
- **`listar_diretorios_remoto(nome_remoto, caminho="")`:** Lista subdiretórios via `rclone lsd` com timeout de 30s.
- **`remover_remoto(nome)`:** Remove remoto da configuração via `rclone config delete` (usado ao cancelar importação após auth).

### Corrigido
- **Timeout de montagem:** Aumentado de **10 segundos → 60 segundos** (`montar_unidade`). Montar crypt remoto no Google Drive com VFS cache full pode levar mais de 10s na primeira vez.
- **Diagnóstico de timeout:** Captura `stderr` do rclone e inclui na mensagem de erro (até 500 chars).

### Melhorado — Responsividade
- **Janela principal:** Layout com `grid` em vez de `pack` — se ajusta ao redimensionar.
- **Todos os diálogos:** Agora são redimensionáveis (`resizable(True, True)`) com `minsize` automático.
- **Cards:** Altura fixa de 76px, `pack_propagate(False)`, indicadores e botões mais compactos.
- **Centralização robusta:** `_centralizar_janela` com `try/except` e `minsize` calculado.
- **Refresh inteligente:** Intervalo 3s, só reconstroi se estado mudou (elimina flicker e CPU desnecessário).

### Dependências
- **Adicionado:** `customtkinter>=5.2.0` ao `requirements.txt`.

### Arquitetura
```
RuntimeCrypto/
├── runtime_crypto.py          # Entry point: tray + janela CustomTkinter
├── gui/
│   ├── __init__.py
│   ├── janela_principal.py    # Janela principal (CTk)
│   ├── card_cofre.py          # Widget de card do cofre
│   └── dialogos.py            # Diálogos modais (senha, mensagem, wizard, etc.)
├── core/
│   └── rclone_manager.py      # RClone + vaults + mount (INTOCADO)
├── tema_runtime.json           # Tema CustomTkinter
├── vaults.json                 # Metadados dos cofres
├── requirements.txt            # pystray + Pillow + customtkinter
└── CHANGELOG.md
```

---

## [2.0.0] - 2026-06-05

### Refatoração Total — RuntimeCrypto v2 (System Tray + RClone Crypt Nativo)

Reescrita completa do programa, abandonando o modelo web-based (FastAPI + PyWebView) e o motor de criptografia
customizado (ChaCha20 + `.qnt`) em favor de uma arquitetura nativa Windows com **RClone Crypt como única
camada de criptografia ponta-a-ponta**.

### Removido
- **Motor ChaCha20 customizado:** `core/crypto_worker.py` — engine de criptografia por blocos com `ProcessPoolExecutor`.
- **Ferramenta CLI:** `encrypt_tool.py` — criptografia standalone para formato `.qnt`.
- **Servidor web:** `runtime_server.py` — FastAPI + Uvicorn com endpoints REST.
- **Desktop wrapper:** `desktop_player.py` — PyWebView + servidor embutido em thread.
- **Frontend web:** `ui/index.html` — SPA com 2183 linhas de HTML/CSS/JS.
- **Formato proprietário `.qnt`:** cabeçalho criptografado de 1024 bytes + blocos ChaCha20 de 1MB.
- **Cofre local (`cofre.bin`):** chave mestra protegida por PBKDF2 + ChaCha20 (64 bytes).
- **Histórico criptografado (`historico.bin`):** JSON com padding 4096 bytes.
- Dependências removidas: `cryptography`, `fastapi`, `uvicorn`, `aiofiles`, `pywebview`.

### Adicionado — System Tray App (`runtime_crypto.py`)
- **Ícone na bandeja do Windows:** Aplicativo residente com menu de contexto, sem janela principal.
- **Diálogos nativos (tkinter):** Janelas modais com tema escuro (#0d1b2a + #10b981) para senha, mensagens e configurações.
- **Menu de cofres dinâmico:** Lista cofres trancados e destrancados com estado em tempo real.
- **Ícone do tray gerado programaticamente (Pillow):** Cadeado verde sobre fundo transparente.
- **Wizard de criação de cofre (3 passos):**
  1. Seleção de provedor (Google Drive, OneDrive, Dropbox)
  2. Definição de senha e nome do cofre
  3. Criação automática: OAuth → remoto base → rclone crypt
- **Fluxo Cryptomator-style:**
  - Cofre trancado → clique → diálogo de senha → monta unidade virtual → abre Explorer.
  - Cofre destrancado → clique → desmonta (tranca) imediatamente.
- **Auto-iniciar com Windows:** Registro em `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.
- **Painel de configurações VFS:** 9 parâmetros editáveis com restauração de padrões.
- **Verificação de WinFsp:** Diagnóstico com 3 métodos (System32 DLL, Registro, Program Files).

### Adicionado — Gerenciamento de Cofres (`core/rclone_manager.py`)
- **`vaults.json`:** Arquivo de metadados persistente (nome, provedor, remoto base, data de criação, flag auto-montar).
- **Cache de senhas em RAM:** Armazenamento volátil por cofre, limpo ao trancar ou sair.
- **`_carregar_cofres()` / `_salvar_cofres()`:** Persistência automática do estado dos cofres.
- **`adicionar_cofre()`, `remover_cofre()`, `atualizar_cofre()`, `obter_cofre()`:** CRUD completo de cofres.
- **`armazenar_senha()`, `obter_senha()`, `limpar_senha()`, `limpar_todas_senhas()`:** Gestão de senhas com lock thread-safe.
- **`obter_letra_por_remoto()`:** Mapeamento remoto → letra de unidade.
- **Suporte a `RCLONE_CONFIG_PASS`:** Senha injetada via variável de ambiente no processo de mount.

### Modificado — Pipeline de Criptografia
```
Antes:  Arquivo → ChaCha20 (.qnt) → Streaming HTTP → Player Web
Depois: Arquivo → RClone Crypt → WinFsp Mount → Unidade Windows (X:\)
```
- **Criptografia delegada ao rclone crypt:** `filename_encryption: standard`, `directory_name_encryption: true`.
- **Descriptografia transparente via kernel:** WinFsp expõe o crypt remote como unidade nativa do Windows.
- **Qualquer aplicativo pode ler/escrever:** Explorer, VLC, editores de texto — sem limitação a streaming HTTP.

### Arquitetura Final
```
RuntimeCrypto/
├── runtime_crypto.py          # System tray app (entry point)
├── core/
│   └── rclone_manager.py      # RClone + vaults + mount/lock
├── vaults.json                 # Metadados dos cofres
├── rclone.exe                  # Binário RClone (72 MB)
├── requirements.txt            # pystray + Pillow
├── CHANGELOG.md
├── LICENSE
└── .gitignore
```

---

## [Não Lançado] - 2026-05-24

### Adicionado — Configurações Avançadas de VFS (Cache/Chunking/Performance)
- **Painel de Configurações VFS na UI:** Novo painel acessível pelo botão "⚙ Configurações" no Dashboard de Drives. Grid organizado em 3 seções: Cache, Chunking e Leitura, Sincronização.
- **9 parâmetros configuráveis:** `vfs_cache_mode` (off/minimal/writes/full), `vfs_cache_max_size`, `vfs_cache_max_age`, `vfs_read_chunk_size`, `vfs_read_chunk_size_limit`, `vfs_read_ahead`, `buffer_size`, `dir_cache_time`, `poll_interval`.
- **Tooltips explicativos:** Cada campo possui ícone `?` com tooltip detalhado sobre o que o parâmetro controla.
- **Restauração de padrões:** Botão para resetar todas as configurações VFS aos valores padrão otimizados para streaming de vídeo.
- **Feedback visual:** Botão "Salvar" exibe confirmação `✓ Salvo!` com transição suave.
- **Valores dinâmicos no backend:** Os valores hardcoded de `montar_unidade()` e `iniciar_servidor_http()` foram substituídos pelo método `_construir_args_vfs()` que monta a CLI do rclone a partir do dicionário de configurações ativo.

### Adicionado — Configurações Avançadas do Crypt (Criptografia de Nomes/Dados)
- **Seção colapsável "Configurações Avançadas do Crypt"** no Wizard (Passo 3) e na tela de Importação. Animação suave de expand/collapse via CSS `max-height`.
- **`filename_encryption`:** Select com 3 opções — Standard (criptografia forte), Obfuscate (ofuscação simples), Off (sem criptografia de nomes).
- **`directory_name_encryption`:** Checkbox para ocultar a estrutura de diretórios no provedor remoto.
- **`no_data_encryption`:** Checkbox para desabilitar criptografia do conteúdo dos arquivos (apenas no wizard de criação). Exibe aviso vermelho condicional ao ativar.
- **Checkboxes customizados:** Estilizados com tema verde e marca de seleção `✓` compatível com o design do sistema.

### Adicionado — Novos Endpoints REST
- `GET /api/nuvem/configuracoes-vfs` — Retorna as configurações VFS ativas da sessão.
- `POST /api/nuvem/configuracoes-vfs` — Atualiza as configurações VFS (aplicadas nas próximas montagens).
- `POST /api/nuvem/configuracoes-vfs/restaurar` — Restaura configurações VFS para os valores padrão.

### Adicionado — Novos Métodos em `GerenciadorRClone`
- `obter_configuracoes_vfs()`, `atualizar_configuracoes_vfs()`, `restaurar_configuracoes_vfs()`, `_construir_args_vfs()`.

### Modificado — Models de API
- `CriarCryptModel` — Adicionados campos `filename_encryption`, `directory_name_encryption`, `no_data_encryption`.
- `ImportarCryptModel` — Adicionados campos `filename_encryption`, `directory_name_encryption`.
- Novo model `ConfigVfsModel` com 9 campos e defaults.

### Modificado — Backend (`rclone_manager.py`)
- `criar_crypt()` e `importar_crypt()` agora aceitam parâmetro `config_crypt` para configurar criptografia de nomes e dados.
- `montar_unidade()` e `iniciar_servidor_http()` agora aceitam `config_vfs` e usam `_construir_args_vfs()` em vez de flags hardcoded.
- Novas constantes `CONFIGURACOES_VFS_PADRAO` e `CONFIGURACOES_CRYPT_PADRAO` com defaults documentados.

---

### Adicionado — Montagem Nativa de Unidade Virtual (Estilo Cryptomator)
- **`rclone mount` nativo para Windows:** O programa agora monta drives crypt como unidades virtuais do Windows (ex: `V:\`, `W:\`), acessíveis diretamente pelo Windows Explorer, sem necessidade de streaming HTTP.
- **Detecção automática de WinFsp:** Verifica se o driver WinFsp está instalado (DLL no System32, registro do Windows, ou Program Files). Exibe alerta com link de download caso ausente.
- **Gestão inteligente de letras de unidade:** Seleciona automaticamente a primeira letra livre (V→Z, depois R→Q). Permite seleção manual via dropdown na UI.
- **Montagem automática:** Ao criar um crypt pelo wizard, opção de "Montar como Unidade e Finalizar" monta imediatamente.
- **Desmontagem automática no shutdown:** `ciclo_vida` do FastAPI desmonta todas as unidades ao encerrar.
- **Badge de montagem ativa:** Indicador visual animado (pulse glow) na barra de título mostrando unidades montadas (ex: `V: Montado`).
- **Polling de status:** Verificação periódica (10s) do estado das montagens ativas.

### Adicionado — Importação de Crypt Existente
- **Tela "Importar Crypt Existente":** Formulário dedicado para conectar a um drive crypt já configurado em outro provedor, informando nome, remoto base e senha.
- **Novo endpoint `POST /api/nuvem/importar-crypt`:** Cria configuração crypt local a partir de dados de um crypt existente.

### Adicionado — Novos Endpoints REST
- `GET /api/nuvem/winfsp-status` — Verifica se WinFsp está instalado no sistema.
- `GET /api/nuvem/montagem/status` — Retorna todas as montagens ativas com letra, remoto e ponto de montagem.
- `POST /api/nuvem/montagem/montar` — Monta um remoto crypt como unidade virtual. Aceita `{remoto, letra?}`.
- `POST /api/nuvem/montagem/desmontar` — Desmonta uma unidade ativa. Aceita `{letra}`.
- `GET /api/nuvem/letras-disponiveis` — Lista letras de unidade disponíveis no Windows.
- `GET /api/nuvem/remotos-detalhado` — Lista todos os remotos com tipo, config, status de montagem e letra.
- `POST /api/nuvem/remover-remoto` — Remove um remoto da configuração do RClone (desmonta automaticamente se montado).

### Adicionado — Novos Métodos em `GerenciadorRClone`
- `verificar_winfsp()`, `obter_letras_disponiveis()`, `montar_unidade()`, `desmontar_unidade()`, `desmontar_todas()`, `status_montagem()`, `listar_remotos_detalhado()`, `obter_config_remoto()`, `importar_crypt()`, `remover_remoto()`.

### Modificado — Redesign da Interface (Foco em Gerenciamento de Drives)
- **Aba DRIVES como tela principal:** Dashboard com cards de todos os drives configurados (crypts e bases), botões de montar/desmontar, seletor de letra, badge de tipo e status.
- **Tabs reordenadas:** `DRIVES | LOCAL | STREAMING` — o streaming de vídeo agora é um recurso secundário.
- **Cards de drive interativos:** Mostra tipo (crypt/base), remoto base, status de montagem, com ações contextuais.
- **Alerta visual de WinFsp ausente:** Card amarelo com link direto para download.
- **Estado vazio refinado:** Ícone de cadeado e texto guia quando não há drives.
- **Wizard atualizado:** Passo 4 (sucesso) agora oferece "Montar como Unidade e Finalizar" com montagem imediata.
- **CSS unificado:** Classes reutilizáveis (`.btn`, `.panel`, `.input-field`, `.label`, `.badge`) substituem estilos inline repetidos.
- **Scrollbar estilizada:** Barra de rolagem dark com cor accent.

### Segurança e Padrões (Mantidos)
- Chave mestra apenas na RAM. Zero rastros descriptografados em disco.
- Montagens usam `--vfs-cache-mode full` com cache local temporário e `--network-mode`.

---

## [Não Lançado] - 2026-04-26

### Adicionado
- **Wizard de Configuração RClone (sem CLI):** Fluxo guiado em 4 etapas para instalar, autenticar e configurar drives criptografados diretamente pela interface web.
  - **Etapa 1:** Grid de cards com provedores suportados (Google Drive, OneDrive, Dropbox, Amazon S3/MinIO, Pasta Local).
  - **Etapa 2a — OAuth:** Autorização via browser nativo com link de fallback manual e polling automático do token.
  - **Etapa 2b — Campos:** Formulário dinâmico para provedores com credenciais (S3) ou caminho local.
  - **Etapa 3:** Criação do cofre `rclone crypt` com nome, senha e confirmação com validações.
  - **Etapa 4:** Tela de sucesso com navegação imediata para o drive.
- **Novos endpoints REST:**
  - `GET /api/nuvem/provedores` — lista provedores disponíveis.
  - `GET /api/nuvem/auth-url` — inicia OAuth e retorna URL de autorização.
  - `GET /api/nuvem/auth-status` — polling do status de autorização OAuth.
  - `POST /api/nuvem/auth-abort` — cancela processo OAuth em andamento.
  - `POST /api/nuvem/criar-remoto` — cria remoto base via `rclone config create`.
  - `POST /api/nuvem/criar-crypt` — cria remoto crypt com senha ofuscada via `rclone obscure`.
- **Novos métodos em `GerenciadorRClone`:** `criar_remoto`, `criar_crypt`, `obscurecer_senha`, `iniciar_oauth`, `abortar_oauth`, `obter_status_oauth`, `listar_todos_remotos`.

### Corrigido
- **Bug crítico de DOM:** `carregarNuvem` referenciava `#cloud-status` que era destruído pelo `innerHTML`, causando silêncio em caso de erro.
- **Endpoints bloqueantes:** `instalar_nuvem`, `conectar_nuvem` e `iniciar_auth` agora rodam em `run_in_threadpool`, sem travar o event loop do FastAPI.
- **Detecção de token OAuth:** Parser mais robusto captura o JSON mesmo quando fragmentado em múltiplas linhas ou com prefixos de log do rclone.
- **Inicialização do desktop player:** `time.sleep(1.0)` fixo substituído por retry com verificação HTTP real ao servidor, eliminando falhas em máquinas lentas.

### Melhorado
- **Lista de drives remotos:** Visual aprimorado com badge "crypt", hover animado e botão "Adicionar novo drive".
- **Instalação do RClone:** Substituído o spinner no botão (que era destruído pelo DOM) por uma tela de progresso dedicada; erro exibe mensagem técnica.
- **Spinner de carregamento** na aba Nuvem ao verificar o status do RClone.

---

## [Não Lançado] - 2026-04-25


### Adicionado
- **Navegador de Arquivos Integrado:** Adicionada uma nova camada de interface antes do player para navegar por arquivos locais e remotos (RClone).
- **Suporte a Pré-visualização (Preview):** 
  - Área dedicada de pré-visualização ao lado da lista de arquivos.
  - Ao passar o mouse sobre um arquivo de vídeo (hover) por 600ms, uma pré-visualização silenciosa é reproduzida automaticamente.
  - Preparação segura do vídeo via backend (`/api/preparar`) antes da pré-visualização.
- **Listagem Nativa do RClone:**
  - Novo método `listar_arquivos_json` em `GerenciadorRClone` (`core/rclone_manager.py`) para utilizar o comando `rclone lsjson`.
  - Novo endpoint `/api/nuvem/browser` no `runtime_server.py` para fornecer navegação de múltiplos níveis estruturada e nativa para arquivos na nuvem.
- **Interface Avançada de Arquivos (estilo Cloud Drive):**
  - **Navegação por Breadcrumbs:** Substituição do texto de caminho estático por links interativos (migalhas de pão) para retorno rápido a diretórios pais.
  - **Ícones Vetoriais:** Substituição de emojis por ícones SVG limpos e escaláveis para pastas e vídeos.
  - **Visões Dinâmicas (Lista e Grade):** Botões na barra de ferramentas para alternar entre formato de tabela detalhada (com cabeçalhos "Nome" e "Tipo") e formato de cartões (cards/thumbnails).
  - **Estados Vazios (Empty States):** Exibição elegante de "Pasta Vazia" quando não há conteúdo compatível no diretório.
- **Botão "Voltar ao Navegador":** Adicionado no player principal para retornar diretamente à aba e diretório anteriores.

### Modificado
- **Tema e Design UI/UX (Foco em Segurança):**
  - Paleta de cores atualizada: remoção de gradientes lúdicos (azul/roxo) em favor de um tema escuro (charcoal/dark slate) com detalhes em verde esmeralda/neon (`#10b981`).
  - Textura de fundo alterada para um padrão de grade sutil, remetendo a interfaces técnicas/terminais.
  - Elementos de interface (botões, painéis) com cantos mais retos (border-radius menores) e efeitos de brilho (glow) interativos.
  - Atualização da tipografia para maior clareza tática, utilizando uppercase e letter-spacing em botões e cabeçalhos.
- **Fluxo Inicial de Destravamento:** Após inserir a senha mestre com sucesso, a aplicação redireciona automaticamente para o navegador de Arquivos Locais, eliminando a tela seletora estática anterior.

### Segurança e Padrões (Mantidos)
- Todo o código, comentários e nomenclaturas da interface e novos métodos adicionados continuam estritamente em **Português (Brasil)**.
- O manuseio de chaves e a política de zero rastros descriptografados em disco foram mantidos durante as pré-visualizações.