import os
import re
import subprocess
import threading
import time
import json as _json
import string

CONFIGURACOES_VFS_PADRAO = {
    "vfs_cache_mode": "full",
    "vfs_cache_max_size": "10G",
    "vfs_cache_max_age": "1h",
    "vfs_read_chunk_size": "8M",
    "vfs_read_chunk_size_limit": "512M",
    "vfs_read_ahead": "16M",
    "buffer_size": "16M",
    "dir_cache_time": "30m",
    "poll_interval": "30s",
    "attr_timeout": "1m",
    "vfs_write_back": "5s",
    "vfs_disk_space_total_size": "1T",
    "cache_dir": "",
}

CONFIGURACOES_CRYPT_PADRAO = {
    "filename_encryption": "standard",
    "directory_name_encryption": "true",
    "no_data_encryption": "false",
}

PROVEDORES = [
    {
        "id": "drive", "nome": "Google Drive", "icone": "G",
        "cor": "#34A853", "oauth": True, "campos": []
    },
    {
        "id": "onedrive", "nome": "Microsoft OneDrive", "icone": "O",
        "cor": "#0078D4", "oauth": True, "campos": []
    },
    {
        "id": "dropbox", "nome": "Dropbox", "icone": "D",
        "cor": "#0061FF", "oauth": True, "campos": []
    },
    {
        "id": "s3", "nome": "Amazon S3 / MinIO", "icone": "S",
        "cor": "#FF9900", "oauth": False,
        "campos": [
            {"id": "access_key_id", "label": "Access Key ID", "tipo": "text", "required": True},
            {"id": "secret_access_key", "label": "Secret Access Key", "tipo": "password", "required": True},
            {"id": "region", "label": "Regiao (ex: us-east-1)", "tipo": "text", "required": False},
            {"id": "endpoint", "label": "Endpoint customizado (MinIO, etc)", "tipo": "text", "required": False},
        ]
    },
    {
        "id": "local_path", "nome": "Pasta Local", "icone": "L",
        "cor": "#10b981", "oauth": False, "local_only": True,
        "campos": [
            {"id": "_local_path", "label": "Caminho da pasta base criptografada", "tipo": "text", "required": True},
        ]
    },
]

_LETRAS_PREFERIDAS = list("VWXYZRQPONMLKJIHGFEDCBA")

_DIRETORIO_APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQUIVO_COFRES = os.path.join(_DIRETORIO_APP, "vaults.json")


class GerenciadorRClone:
    def __init__(self):
        self.process_servico = None
        self.porta_servico = 8081
        self.executavel = self._localizar_rclone()
        self._oauth_processo = None
        self._oauth_token = None
        self._oauth_url = None
        self._oauth_lock = threading.Lock()
        self._montagens = {}
        self._montagem_lock = threading.Lock()
        self._config_vfs = dict(CONFIGURACOES_VFS_PADRAO)
        self._senhas_cache = {}
        self._cache_lock = threading.Lock()
        self._chamada_status = None
        self._carregar_cofres()

    # ==================== LOCALIZACAO / INSTALACAO ====================

    def _localizar_rclone(self):
        caminho_local = os.path.join(_DIRETORIO_APP, "rclone.exe")
        for caminho in [caminho_local, "rclone.exe", "rclone"]:
            try:
                subprocess.run([caminho, "--version"], capture_output=True, timeout=5)
                return caminho
            except Exception:
                continue
        return None

    def esta_disponivel(self):
        return self.executavel is not None

    def instalar_rclone_local(self):
        import urllib.request
        import zipfile
        import io
        if os.name != 'nt':
            return False, "Instalacao automatica disponivel apenas para Windows."
        url = "https://downloads.rclone.org/rclone-current-windows-amd64.zip"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=120) as response:
                with zipfile.ZipFile(io.BytesIO(response.read())) as z:
                    for info in z.infolist():
                        if info.filename.endswith("rclone.exe"):
                            with open("rclone.exe", "wb") as f:
                                f.write(z.read(info.filename))
                            self.executavel = "./rclone.exe"
                            return True, "RClone instalado com sucesso."
            return False, "Executavel nao encontrado no arquivo baixado."
        except Exception as e:
            return False, str(e)

    # ==================== WINFSP ====================

    def verificar_winfsp(self):
        if os.name != 'nt':
            return {"instalado": False, "motivo": "Apenas Windows e suportado."}

        system32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
        dll_caminho = os.path.join(system32, "winfsp-x64.dll")
        if os.path.exists(dll_caminho):
            return {"instalado": True}

        try:
            import winreg
            chave = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\WOW6432Node\WinFsp"
            )
            caminho_instalacao, _ = winreg.QueryValueEx(chave, "InstallDir")
            winreg.CloseKey(chave)
            if caminho_instalacao and os.path.exists(caminho_instalacao):
                return {"instalado": True}
        except (FileNotFoundError, OSError):
            pass

        for base in [os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")]:
            if base:
                winfsp_dir = os.path.join(base, "WinFsp")
                if os.path.isdir(winfsp_dir):
                    return {"instalado": True}

        return {
            "instalado": False,
            "url_download": "https://winfsp.dev/rel/",
            "motivo": "WinFsp nao encontrado. Necessario para montar unidades virtuais."
        }

    # ==================== LETRAS DE UNIDADE ====================

    def obter_letras_disponiveis(self):
        if os.name != 'nt':
            return []
        ocupadas = set()
        for letra in string.ascii_uppercase:
            if os.path.exists(f"{letra}:\\"):
                ocupadas.add(letra)
        with self._montagem_lock:
            for letra_montada in self._montagens:
                ocupadas.add(letra_montada)
        disponiveis = [l for l in _LETRAS_PREFERIDAS if l not in ocupadas]
        return disponiveis

    # ==================== CONFIGURACOES VFS ====================

    def obter_configuracoes_vfs(self):
        return dict(self._config_vfs)

    def atualizar_configuracoes_vfs(self, config):
        chaves_validas = set(CONFIGURACOES_VFS_PADRAO.keys())
        for chave, valor in config.items():
            if chave in chaves_validas and valor:
                self._config_vfs[chave] = str(valor)
        return self._config_vfs

    def restaurar_configuracoes_vfs(self):
        self._config_vfs = dict(CONFIGURACOES_VFS_PADRAO)
        return self._config_vfs

    def _construir_args_vfs(self, config_override=None):
        cfg = dict(self._config_vfs)
        if config_override:
            cfg.update({k: v for k, v in config_override.items() if v})

        mapa_args = {
            "vfs_cache_mode": "--vfs-cache-mode",
            "vfs_cache_max_size": "--vfs-cache-max-size",
            "vfs_cache_max_age": "--vfs-cache-max-age",
            "vfs_read_chunk_size": "--vfs-read-chunk-size",
            "vfs_read_chunk_size_limit": "--vfs-read-chunk-size-limit",
            "vfs_read_ahead": "--vfs-read-ahead",
            "buffer_size": "--buffer-size",
            "dir_cache_time": "--dir-cache-time",
            "poll_interval": "--poll-interval",
            "attr_timeout": "--attr-timeout",
            "vfs_write_back": "--vfs-write-back",
            "vfs_disk_space_total_size": "--vfs-disk-space-total-size",
            "cache_dir": "--cache-dir",
        }
        args = []
        for chave, flag in mapa_args.items():
            valor = cfg.get(chave)
            if valor:
                args.extend([flag, valor])
        return args

    # ==================== MONTAGEM / DESMONTAGEM ====================

    def montar_unidade(self, remoto, letra=None, senha=None, config_vfs=None):
        if not self.esta_disponivel():
            return False, "RClone nao disponivel.", None

        winfsp = self.verificar_winfsp()
        if not winfsp.get("instalado"):
            return False, winfsp.get("motivo", "WinFsp ausente."), None

        if not letra:
            disponiveis = self.obter_letras_disponiveis()
            if not disponiveis:
                return False, "Nenhuma letra de unidade disponivel.", None
            letra = disponiveis[0]

        letra = letra.upper().strip().rstrip(":\\")

        with self._montagem_lock:
            if letra in self._montagens:
                return False, f"A letra {letra}: ja esta em uso.", None

        if not remoto.endswith(":"):
            remoto = remoto + ":"

        ponto_montagem = f"{letra}:"
        comando = [
            self.executavel, "mount", remoto, ponto_montagem,
        ] + self._construir_args_vfs(config_vfs) + [
            "--volname", f"RuntimeCrypto ({remoto.rstrip(':')})",
            "--network-mode",
            "--no-checksum",
            "--no-modtime",
            "--no-console",
        ]

        env = os.environ.copy()
        if senha:
            env["RCLONE_CONFIG_PASS"] = senha

        try:
            processo = subprocess.Popen(
                comando,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )

            if senha and "RCLONE_CONFIG_PASS" in env:
                env["RCLONE_CONFIG_PASS"] = "x" * len(senha)
                del env["RCLONE_CONFIG_PASS"]
            del env

            montou = False
            inicio = time.time()
            intervalo = 0.2

            while time.time() - inicio < 45:
                time.sleep(intervalo)
                if os.path.exists(f"{letra}:\\"):
                    montou = True
                    break
                if processo.poll() is not None:
                    erro = processo.stderr.read().decode('utf-8', errors='replace').strip()
                    return False, f"Falha ao montar: {erro or 'Processo encerrou inesperadamente.'}", None
                if intervalo < 1.0:
                    intervalo = min(intervalo * 1.5, 1.0)

            if not montou:
                erro_stderr = ""
                try:
                    processo.terminate()
                    _, stderr_bytes = processo.communicate(timeout=5)
                    if stderr_bytes:
                        erro_stderr = stderr_bytes.decode('utf-8', errors='replace').strip()
                except Exception:
                    processo.kill()
                msg_erro = "Timeout: A unidade nao ficou pronta em 45 segundos."
                if erro_stderr:
                    msg_erro += f"\n\nDetalhes: {erro_stderr[:500]}"
                return False, msg_erro, None

            with self._montagem_lock:
                self._montagens[letra] = {
                    "processo": processo,
                    "remoto": remoto,
                    "letra": letra,
                }

            return True, f"Unidade {letra}: montada com sucesso.", letra

        except Exception as e:
            return False, str(e), None

    def desmontar_unidade(self, letra):
        letra = letra.upper().strip().rstrip(":\\")

        with self._montagem_lock:
            info = self._montagens.get(letra)
            if not info:
                return False, f"Nenhuma montagem ativa na letra {letra}:"

        processo = info["processo"]

        for tentativa in range(3):
            try:
                if tentativa == 0:
                    processo.terminate()
                else:
                    processo.kill()
                processo.wait(timeout=5)
                break
            except subprocess.TimeoutExpired:
                continue
            except Exception:
                break

        with self._montagem_lock:
            self._montagens.pop(letra, None)

        return True, f"Unidade {letra}: desmontada com sucesso."

    def desmontar_todas(self):
        with self._montagem_lock:
            letras = list(self._montagens.keys())
        for letra in letras:
            self.desmontar_unidade(letra)

    def status_montagem(self):
        with self._montagem_lock:
            resultado = []
            letras_remover = []
            for letra, info in self._montagens.items():
                processo = info["processo"]
                ativo = processo.poll() is None
                if not ativo:
                    letras_remover.append(letra)
                    continue
                resultado.append({
                    "letra": letra,
                    "remoto": info["remoto"],
                    "ativo": True,
                    "ponto_montagem": f"{letra}:\\"
                })
            for l in letras_remover:
                self._montagens.pop(l, None)
        return resultado

    def obter_letra_por_remoto(self, nome_remoto):
        nome_remoto = nome_remoto.rstrip(":")
        for m in self.status_montagem():
            if m["remoto"].rstrip(":") == nome_remoto:
                return m["letra"]
        return None
    # ==================== LISTAGEM DE DIRETORIOS ====================

    def listar_diretorios_remoto(self, nome_remoto, caminho=""):
        """Lista subdiretórios de um remoto usando 'rclone lsd'."""
        if not self.esta_disponivel():
            return []
        if not nome_remoto.endswith(":"):
            nome_remoto = nome_remoto + ":"
        alvo = nome_remoto + caminho.lstrip("/") if caminho else nome_remoto
        try:
            resultado = subprocess.run(
                [self.executavel, "lsd", alvo],
                capture_output=True, text=True, encoding='utf-8', timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            dirs = []
            for linha in resultado.stdout.splitlines():
                linha = linha.strip()
                if not linha:
                    continue
                # Formato: -1 2024-01-01 00:00:00 -1 nome_pasta
                partes = linha.split(None, 4)
                if len(partes) >= 5:
                    dirs.append(partes[4])
                elif len(partes) >= 1:
                    dirs.append(partes[-1])
            return sorted(dirs)
        except Exception:
            return []



    def listar_remotos(self):
        if not self.esta_disponivel():
            return []
        try:
            resultado = subprocess.run(
                [self.executavel, "config", "dump"],
                capture_output=True, text=True, encoding='utf-8', timeout=10
            )
            if resultado.returncode == 0:
                config = _json.loads(resultado.stdout)
                return [f"{nome}:" for nome, cfg in config.items() if cfg.get("type") == "crypt"]
            resultado = subprocess.run(
                [self.executavel, "listremotes"],
                capture_output=True, text=True, timeout=10
            )
            return [r.strip() for r in resultado.stdout.split('\n') if r.strip()]
        except Exception:
            return []

    def listar_todos_remotos(self):
        if not self.esta_disponivel():
            return []
        try:
            resultado = subprocess.run(
                [self.executavel, "listremotes"],
                capture_output=True, text=True, encoding='utf-8', timeout=10
            )
            return [r.strip() for r in resultado.stdout.split('\n') if r.strip()]
        except Exception:
            return []

    def listar_remotos_detalhado(self):
        if not self.esta_disponivel():
            return []
        try:
            resultado = subprocess.run(
                [self.executavel, "config", "dump"],
                capture_output=True, text=True, encoding='utf-8', timeout=10
            )
            if resultado.returncode != 0:
                return []
            config = _json.loads(resultado.stdout)
            lista = []
            montagens_ativas = {m["remoto"].rstrip(":"): m for m in self.status_montagem()}

            for nome, cfg in config.items():
                tipo = cfg.get("type", "desconhecido")
                remoto_base = cfg.get("remote", "")
                montagem = montagens_ativas.get(nome, None)
                lista.append({
                    "nome": nome,
                    "tipo": tipo,
                    "is_crypt": tipo == "crypt",
                    "remoto_base": remoto_base,
                    "montado": montagem is not None,
                    "letra_montada": montagem["letra"] if montagem else None,
                })
            return lista
        except Exception:
            return []

    def obter_config_remoto(self, nome):
        if not self.esta_disponivel():
            return None
        try:
            resultado = subprocess.run(
                [self.executavel, "config", "dump"],
                capture_output=True, text=True, encoding='utf-8', timeout=10
            )
            if resultado.returncode == 0:
                config = _json.loads(resultado.stdout)
                return config.get(nome.rstrip(":"))
            return None
        except Exception:
            return None

    # ==================== CRYPT / REMOTO ====================

    def obscurecer_senha(self, senha):
        resultado = subprocess.run(
            [self.executavel, "obscure", "-"],
            input=senha,
            capture_output=True, text=True, encoding='utf-8', timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        return resultado.stdout.strip()

    def remover_remoto(self, nome):
        """Remove um remoto da configuração do rclone."""
        if not self.esta_disponivel():
            return False, "RClone nao disponivel."
        try:
            resultado = subprocess.run(
                [self.executavel, "config", "delete", nome],
                capture_output=True, text=True, encoding='utf-8', timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            if resultado.returncode == 0:
                return True, f"Remoto '{nome}' removido."
            return False, resultado.stderr.strip() or "Erro desconhecido."
        except Exception as e:
            return False, str(e)

    def criar_remoto(self, nome, tipo, params: dict):
        if not self.esta_disponivel():
            return False, "RClone nao disponivel."
        comando = [self.executavel, "config", "create", nome, tipo]
        for chave, valor in params.items():
            if valor:
                comando.extend([chave, str(valor)])
        try:
            resultado = subprocess.run(
                comando, capture_output=True, text=True, encoding='utf-8', timeout=30
            )
            if resultado.returncode == 0:
                return True, f"Remoto '{nome}' criado com sucesso."
            return False, resultado.stderr.strip() or "Erro desconhecido."
        except Exception as e:
            return False, str(e)

    def criar_crypt(self, nome_crypt, remoto_base, senha, senha2="", config_crypt=None):
        if not self.esta_disponivel():
            return False, "RClone nao disponivel."
        try:
            cfg = dict(CONFIGURACOES_CRYPT_PADRAO)
            if config_crypt:
                cfg.update({k: v for k, v in config_crypt.items() if v})

            senha_obs = self.obscurecer_senha(senha)
            senha2_obs = self.obscurecer_senha(senha2) if senha2 else senha_obs
            params = {
                "remote": remoto_base,
                "password": senha_obs,
                "password2": senha2_obs,
                "filename_encryption": cfg["filename_encryption"],
                "directory_name_encryption": cfg["directory_name_encryption"],
            }
            if cfg.get("no_data_encryption") == "true":
                params["no_data_encryption"] = "true"
            return self.criar_remoto(nome_crypt, "crypt", params)
        except Exception as e:
            return False, str(e)

    def importar_crypt(self, nome, remoto_base, senha, senha2="", config_crypt=None):
        if not self.esta_disponivel():
            return False, "RClone nao disponivel."
        try:
            cfg = dict(CONFIGURACOES_CRYPT_PADRAO)
            if config_crypt:
                cfg.update({k: v for k, v in config_crypt.items() if v})

            senha_obs = self.obscurecer_senha(senha)
            senha2_obs = self.obscurecer_senha(senha2) if senha2 else senha_obs
            params = {
                "remote": remoto_base,
                "password": senha_obs,
                "password2": senha2_obs,
                "filename_encryption": cfg["filename_encryption"],
                "directory_name_encryption": cfg["directory_name_encryption"],
            }
            if cfg.get("no_data_encryption") == "true":
                params["no_data_encryption"] = "true"
            return self.criar_remoto(nome, "crypt", params)
        except Exception as e:
            return False, str(e)

    def remover_remoto(self, nome):
        if not self.esta_disponivel():
            return False, "RClone nao disponivel."
        nome_limpo = nome.rstrip(":")
        try:
            resultado = subprocess.run(
                [self.executavel, "config", "delete", nome_limpo],
                capture_output=True, text=True, encoding='utf-8', timeout=10
            )
            if resultado.returncode == 0:
                return True, f"Remoto '{nome_limpo}' removido."
            return False, resultado.stderr.strip() or "Erro ao remover."
        except Exception as e:
            return False, str(e)

    # ==================== OAUTH ====================

    def iniciar_oauth(self, tipo):
        self.abortar_oauth()
        with self._oauth_lock:
            self._oauth_token = None
            self._oauth_url = None
        self._oauth_processo = subprocess.Popen(
            [self.executavel, "authorize", tipo],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        threading.Thread(target=self._ler_oauth_output, daemon=True).start()
        return True

    def _ler_oauth_output(self):
        buffer_token = []
        capturando_token = False

        for linha in self._oauth_processo.stdout:
            linha_strip = linha.strip()

            if "127.0.0.1" in linha_strip or "localhost" in linha_strip:
                match = re.search(r'https?://\S+', linha_strip)
                if match:
                    with self._oauth_lock:
                        self._oauth_url = match.group(0).rstrip('.')

            if "Paste the following" in linha_strip:
                capturando_token = True
                buffer_token = []
                continue

            if capturando_token:
                if linha_strip == "<---End paste" or "End paste" in linha_strip:
                    token_str = "".join(buffer_token).strip()
                    match_json = re.search(r'(\{.*\})', token_str, re.DOTALL)
                    if match_json:
                        with self._oauth_lock:
                            self._oauth_token = match_json.group(1)
                    break
                if linha_strip.startswith("{") or buffer_token:
                    buffer_token.append(linha_strip)

        self._oauth_processo.wait()

    def obter_status_oauth(self):
        with self._oauth_lock:
            return {
                "url": self._oauth_url,
                "token": self._oauth_token,
                "concluido": self._oauth_token is not None,
            }

    def abortar_oauth(self):
        if self._oauth_processo:
            try:
                self._oauth_processo.terminate()
                self._oauth_processo.wait(timeout=3)
            except Exception:
                try:
                    self._oauth_processo.kill()
                except Exception:
                    pass
            self._oauth_processo = None

    # ==================== GERENCIAMENTO DE SENHAS (CACHE EM MEMORIA) ====================

    def armazenar_senha(self, nome_cofre, senha):
        with self._cache_lock:
            self._senhas_cache[nome_cofre] = senha

    def obter_senha(self, nome_cofre):
        with self._cache_lock:
            return self._senhas_cache.get(nome_cofre)

    def limpar_senha(self, nome_cofre):
        with self._cache_lock:
            self._senhas_cache.pop(nome_cofre, None)

    def limpar_todas_senhas(self):
        with self._cache_lock:
            self._senhas_cache.clear()

    # ==================== GERENCIAMENTO DE COFRES (VAULTS) ====================

    def _carregar_cofres(self):
        if os.path.exists(ARQUIVO_COFRES):
            try:
                with open(ARQUIVO_COFRES, 'r', encoding='utf-8') as f:
                    self._cofres = _json.load(f)
            except Exception:
                self._cofres = []
        else:
            self._cofres = []

    def _salvar_cofres(self):
        with open(ARQUIVO_COFRES, 'w', encoding='utf-8') as f:
            _json.dump(self._cofres, f, indent=2, ensure_ascii=False)

    def listar_cofres(self):
        montagens = {m["remoto"].rstrip(":"): m for m in self.status_montagem()}
        resultado = []
        for cofre in self._cofres:
            nome = cofre.get("nome", "")
            m = montagens.get(nome, None)
            item = dict(cofre)
            item["montado"] = m is not None
            item["letra"] = m["letra"] if m else None
            item["tem_senha"] = self.obter_senha(nome) is not None
            resultado.append(item)
        return resultado

    def adicionar_cofre(self, nome, provedor_id, nome_provedor, remoto_base, caminho_cripto=None):
        for c in self._cofres:
            if c["nome"] == nome:
                return False, f"Ja existe um cofre com o nome '{nome}'."
        cofre = {
            "nome": nome,
            "provedor_id": provedor_id,
            "provedor_nome": nome_provedor,
            "remoto_base": remoto_base,
            "caminho_cripto": caminho_cripto or "",
            "criado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
            "auto_montar": False,
        }
        self._cofres.append(cofre)
        self._salvar_cofres()
        return True, f"Cofre '{nome}' adicionado."

    def remover_cofre(self, nome):
        montagens = {m["remoto"].rstrip(":"): m for m in self.status_montagem()}
        for c in self._cofres:
            if c["nome"] == nome:
                if nome in montagens:
                    self.desmontar_unidade(montagens[nome]["letra"])
                self.limpar_senha(nome)
                self._cofres.remove(c)
                self._salvar_cofres()
                return True, f"Cofre '{nome}' removido."
        return False, f"Cofre '{nome}' nao encontrado."

    def atualizar_cofre(self, nome, **kwargs):
        for c in self._cofres:
            if c["nome"] == nome:
                for k, v in kwargs.items():
                    if k in c:
                        c[k] = v
                self._salvar_cofres()
                return True
        return False

    def obter_cofre(self, nome):
        for c in self._cofres:
            if c["nome"] == nome:
                return dict(c)
        return None
