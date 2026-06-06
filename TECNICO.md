# RuntimeCrypto v2.0 — Documentação Técnica

## 1. Visão Geral

O **RuntimeCrypto** é um gerenciador de cofres criptografados na nuvem para Windows, que funciona
como um aplicativo residente na bandeja do sistema (System Tray). Utiliza **RClone Crypt** como camada
de criptografia ponta-a-ponta e **WinFsp** para montar unidades virtuais nativas do Windows.

Qualquer aplicativo (Explorer, VLC, editores de texto) pode ler e escrever nos cofres como se fossem
pastas comuns — a criptografia e descriptografia são totalmente transparentes.

---

## 2. Arquitetura do Sistema

```
RuntimeCrypto/
├── runtime_crypto.py          # System Tray app (entry point)
├── core/
│   ├── __init__.py
│   └── rclone_manager.py      # RClone + cofres + montagem/desmontagem
├── vaults.json                 # Metadados dos cofres (não comitado)
├── rclone.exe                  # Binário RClone (não comitado)
├── requirements.txt            # pystray + Pillow
├── CHANGELOG.md
├── TECNICO.md
├── LICENSE
└── .gitignore
```

### 2.1. System Tray (`runtime_crypto.py`)

- **Tecnologia:** tkinter (diálogos nativos) + pystray (ícone na bandeja) + Pillow (geração de ícone).
- **Tema visual:** Escuro (#0d1b2a) com acentos verde (#10b981), estilo terminal/segurança.
- **Fila de ações:** Sistema de fila (`queue.Queue`) para comunicação entre threads de montagem e a thread principal do tkinter.
- **Menu dinâmico:** Lista cofres trancados e destrancados, com reconstrução automática após cada operação.

### 2.2. Gerenciador RClone (`core/rclone_manager.py`)

- **Montagem:** `rclone mount` com WinFsp expõe o crypt remote como unidade Windows (ex: `V:\`).
- **Configurações VFS:** 9 parâmetros ajustáveis (cache, chunking, polling) persistidos em memória.
- **OAuth:** Fluxo completo para Google Drive, OneDrive e Dropbox via `rclone authorize`.
- **Cache de senhas:** Dicionário em memória protegido por `threading.Lock`, limpo ao trancar ou sair.
- **Cofres (`vaults.json`):** CRUD de cofres com persistência em JSON. Não armazena senhas.

### 2.3. Pipeline de Criptografia

```
Arquivo → RClone Crypt (criptografia ponta-a-ponta) → WinFsp Mount → Unidade Windows (V:\)
```

- **Criptografia delegada ao rclone crypt:**
  - `filename_encryption: standard` (nomes de arquivos criptografados)
  - `directory_name_encryption: true` (estrutura de diretórios oculta)
- **Descriptografia transparente:** WinFsp expõe os dados como sistema de arquivos nativo.

---

## 3. Modelo de Segurança

### 3.1. Senhas

- Senhas dos cofres existem **apenas na RAM** durante a sessão.
- Ao trancar um cofre ou encerrar a aplicação, a senha é removida do cache.
- A ofuscação de senhas para o rclone crypt é feita via `rclone obscure` com entrada por `stdin` (não exposta na CLI).

### 3.2. Criptografia

- **Algoritmo:** XSalsa20-Poly1305 (rclone crypt — NaCl SecretBox para conteúdo, EME para nomes).
- **Chave derivada:** O rclone crypt deriva chaves do par senha/senha2 usando scrypt.
- **Transparência:** O Windows não sabe que os dados são criptografados; tudo é mediado pelo WinFsp.

### 3.3. Variáveis de Ambiente

- `RCLONE_CONFIG_PASS` é injetada no ambiente do subprocesso de montagem e limpa imediatamente após o `Popen`.

### 3.4. Proteções Adicionais

- Cache VFS é local e temporário (`--vfs-cache-mode full`).
- Montagens usam `--network-mode` para isolar o sistema de arquivos virtual.
- Desmontagem automática de todas as unidades ao encerrar a aplicação.

---

## 4. Provedores Suportados

| Provedor | ID | Autenticação |
|----------|-----|-------------|
| Google Drive | `drive` | OAuth 2.0 |
| Microsoft OneDrive | `onedrive` | OAuth 2.0 |
| Dropbox | `dropbox` | OAuth 2.0 |
| Amazon S3 / MinIO | `s3` | Access Key + Secret |
| Pasta Local | `local_path` | Nenhuma |

---

## 5. Requisitos do Sistema

### 5.1. Software
- **Windows 10/11** (obrigatório — montagem de unidades via WinFsp).
- **Python 3.10+** com `pystray` e `Pillow`.
- **WinFsp** — driver de sistema de arquivos virtual ([winfsp.dev](https://winfsp.dev/)).
- **RClone** — binário incluído ou no PATH do sistema.

### 5.2. Hardware
- **Processador:** Dual-core (mínimo).
- **Memória RAM:** 2 GB livres (o cache VFS consome memória proporcional ao uso).
- **Disco:** Espaço para cache VFS (padrão: até 5 GB).

---

## 6. Fluxo de Uso

1. **Inicialização:** O programa roda como ícone na bandeja do sistema.
2. **Criação de cofre:** Wizard de 2 passos (selecionar provedor → definir senha e nome).
3. **Destrancamento:** Clique no cofre → diálogo de senha → monta unidade virtual → abre Explorer.
4. **Uso:** Ler e escrever arquivos normalmente na unidade montada.
5. **Trancamento:** Clique no cofre montado → desmonta imediatamente → limpa senha da RAM.
6. **Encerramento:** Desmonta tudo, limpa cache de senhas, encerra processos rclone.

---

*Documento atualizado para a versão 2.0 — Junho de 2026.*
