# Changelog - RuntimeCrypto

Todas as modificações notáveis neste projeto serão documentadas neste arquivo.

## [Não Lançado] - 2026-05-24

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