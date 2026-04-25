# Quantum Runtime Player - Documentação Técnica

## 1. Visão Geral
O **Quantum Runtime Player** é um sistema de Video On Demand (VOD) privado de alto desempenho, focado em segurança extrema e privacidade. Ele permite a reprodução de arquivos de vídeo protegidos por criptografia simétrica em tempo real, sem a necessidade de descriptografar o arquivo completo no disco rígido, evitando rastros digitais.

---

## 2. Arquitetura do Sistema

O projeto é dividido em três camadas principais:

### 2.1. Motor de Criptografia (Core)
*   **Algoritmo:** ChaCha20 (Cifra de fluxo simétrica).
*   **Modo de Operação:** Baseado em blocos de 1MB (`TAMANHO_BLOCO`).
*   **Nonce Dinâmico:** O Nonce de cada bloco é derivado matematicamente do seu ID, permitindo o acesso randômico (*seeking*) imediato a qualquer ponto do vídeo sem processar os blocos anteriores.
*   **Paralelismo:** Utiliza `ProcessPoolExecutor` para distribuir a carga de descriptografia entre os núcleos da CPU, garantindo que o streaming mantenha 60fps em resoluções 4K.

### 2.2. Servidor de API e Streaming (Backend)
*   **Tecnologia:** FastAPI + Uvicorn (Python).
*   **Protocolo de Streaming:** HTTP Range Requests (Status Code 206) permitindo seeking.
*   **API REST:** Fornece endpoints (`/api/cofre/*`, `/api/nuvem/*`, `/api/browser`) que substituem completamente as chamadas nativas de OS, tornando o sistema Multiplataforma.
*   **Segurança de Memória:** A chave mestra reside apenas na RAM do servidor em background.
*   **Hospedagem:** Pode rodar tanto como serviço em background no Desktop quanto hospedado em uma Cloud/VM, isolando os dados brutos da máquina cliente.

### 2.3. Interface do Usuário (Frontend - Web-First)
*   **Paradigma:** Single Page Application puramente em HTML5, CSS3 e JavaScript (API Fetch).
*   **Explorador Customizado:** Renderiza toda a estrutura de diretórios do "host" (local ou nuvem) virtualmente no DOM (Via API de Navegação), dispensando pop-ups nativas do Windows/SO.
*   **Wrapper Local:** Para o executável Desktop, usa-se o PyWebView estritamente como um "Navegador Embutido" que visita `localhost:8080`, sem injetar dependências de API. O app tornou-se verdadeiramente cliente<->servidor.

---

## 3. Modelo de Segurança

### 3.1. Cofre Blindado (`cofre.bin`)
Em vez de armazenar chaves em texto puro, o sistema utiliza um cofre:
1.  **Derivação de Chave (KDF):** Utiliza **PBKDF2-HMAC-SHA256** com 100.000 iterações e um *salt* aleatório de 16 bytes.
2.  **Proteção:** A chave mestra real (256-bits) é armazenada criptografada dentro do cofre. Ela só é liberada para a RAM após a validação da senha do usuário.

### 3.2. Formato de Arquivo `.qnt`
O arquivo protegido possui a seguinte estrutura:
*   **Header (0 - 1024 bytes):** JSON cifrado contendo metadados (nome original do arquivo).
*   **Corpo (1024+ bytes):** Dados brutos do vídeo cifrados em blocos de 1MB.

### 3.3. Histórico Privado (`historico.bin`)
Lista de vídeos recentes armazenada em formato JSON, criptografada com a chave mestra do usuário, garantindo que ninguém saiba o que foi assistido sem a senha.

---

## 4. Integração com Nuvem (RClone)

O sistema integra-se ao **RClone** para permitir o streaming de provedores de nuvem (Google Drive, OneDrive, etc.):
*   **Ponte HTTP:** O player inicia um processo `rclone serve http` em background.
*   **RClone Crypt:** Compatibilidade nativa com drives já criptografados via RClone.
*   **Streaming Direto:** O motor consome os bytes via rede, descriptografa na RAM e entrega ao player.

---

## 5. Requisitos do Sistema

### 5.1. Requisitos de Software
*   **Python:** 3.10 ou superior.
*   **Dependências:** 
    *   `cryptography`: Processamento de alta segurança.
    *   `fastapi`, `uvicorn`: Motor de streaming.
    *   `pywebview`: Interface desktop.
*   **RClone (Opcional):** Necessário para a aba de Nuvem. Deve estar no PATH do sistema.

### 5.2. Requisitos de Hardware
*   **Processador:** Quad-core (recomendado para 1080p+ devido ao processamento paralelo).
*   **Memória RAM:** Mínimo de 4GB (o sistema consome cerca de 100-200MB).
*   **Espaço em Disco:** Apenas o necessário para os arquivos `.qnt`.

---

## 6. Fluxo de Uso

1.  **Primeiro Acesso:** Definição da senha mestre e criação do `cofre.bin`.
2.  **Proteção:** Uso da `encrypt_tool.py` ou do próprio Player para gerar o `.qnt`.
3.  **Reprodução:** Desbloqueio do cofre -> Seleção do vídeo -> Streaming em tempo real.
4.  **Encerramento:** Limpeza automática de chaves da memória RAM e fechamento de túneis RClone.

---
*Documento gerado em 15 de Abril de 2026.*
