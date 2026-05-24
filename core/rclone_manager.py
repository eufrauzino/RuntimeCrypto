import os
import re
import subprocess
import threading
import time
import json as _json
import string

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
            {"id": "region", "label": "Região (ex: us-east-1)", "tipo": "text", "required": False},
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

# Ordem preferida de letras de unidade para montagem
_LETRAS_PREFERIDAS = list("VWXYZRQPONMLKJIHGFEDCBA")


class GerenciadorRClone:
    def __init__(self):
        self.processo_servico = None
        self.porta_servico = 8081
        self.executavel = self._localizar_rclone()
        self._oauth_processo = None
        self._oauth_token = None
        self._oauth_url = None
        self._oauth_lock = threading.Lock()
        # Montagem de unidade virtual
        self._montagens = {}  # {letra: {"processo": Popen, "remoto": str}}
        self._montagem_lock = threading.Lock()

    def _localizar_rclone(self):
        for caminho in ["rclone.exe", "rclone", "./rclone.exe"]:
            try:
                subprocess.run([caminho, "--version"], capture_output=True, timeout=5)
                return caminho
            except:
                continue
        return None

    def esta_disponivel(self):
        return self.executavel is not None

    def instalar_rclone_local(self):
        import urllib.request
        import zipfile
        import io
        if os.name != 'nt':
            return False, "Instalação automática disponível apenas para Windows."
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
            return False, "Executável não encontrado no arquivo baixado."
        except Exception as e:
            return False, str(e)

    # ==================== VERIFICAÇÃO WINFSP ====================

    def verificar_winfsp(self):
        """Verifica se o WinFsp está instalado no sistema (necessário para rclone mount)."""
        if os.name != 'nt':
            return {"instalado": False, "motivo": "Apenas Windows é suportado."}

        # Método 1: Verificar DLL no System32
        system32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
        dll_caminho = os.path.join(system32, "winfsp-x64.dll")
        if os.path.exists(dll_caminho):
            return {"instalado": True}

        # Método 2: Verificar no registro do Windows
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

        # Método 3: Verificar no Program Files
        for base in [os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")]:
            if base:
                winfsp_dir = os.path.join(base, "WinFsp")
                if os.path.isdir(winfsp_dir):
                    return {"instalado": True}

        return {
            "instalado": False,
            "url_download": "https://winfsp.dev/rel/",
            "motivo": "WinFsp não encontrado. Necessário para montar unidades virtuais."
        }

    # ==================== GESTÃO DE LETRAS ====================

    def obter_letras_disponiveis(self):
        """Retorna lista de letras de unidade disponíveis no Windows, ordenadas por preferência."""
        if os.name != 'nt':
            return []
        ocupadas = set()
        for letra in string.ascii_uppercase:
            if os.path.exists(f"{letra}:\\"):
                ocupadas.add(letra)
        # Também exclui letras já reservadas por montagens ativas
        with self._montagem_lock:
            for letra_montada in self._montagens:
                ocupadas.add(letra_montada)
        disponiveis = [l for l in _LETRAS_PREFERIDAS if l not in ocupadas]
        return disponiveis

    # ==================== MONTAGEM DE UNIDADE ====================

    def montar_unidade(self, remoto, letra=None):
        """Monta um remoto RClone como unidade virtual no Windows."""
        if not self.esta_disponivel():
            return False, "RClone não disponível.", None

        winfsp = self.verificar_winfsp()
        if not winfsp.get("instalado"):
            return False, winfsp.get("motivo", "WinFsp ausente."), None

        # Escolhe letra automaticamente se não fornecida
        if not letra:
            disponiveis = self.obter_letras_disponiveis()
            if not disponiveis:
                return False, "Nenhuma letra de unidade disponível.", None
            letra = disponiveis[0]

        letra = letra.upper().strip().rstrip(":\\")

        # Verifica se já está montada
        with self._montagem_lock:
            if letra in self._montagens:
                return False, f"A letra {letra}: já está em uso.", None

        # Garante formato do remoto
        if not remoto.endswith(":"):
            remoto = remoto + ":"

        ponto_montagem = f"{letra}:"
        comando = [
            self.executavel, "mount", remoto, ponto_montagem,
            "--vfs-cache-mode", "full",
            "--vfs-read-ahead", "128M",
            "--vfs-cache-max-size", "5G",
            "--dir-cache-time", "5m",
            "--poll-interval", "15s",
            "--volname", f"RClone ({remoto.rstrip(':')})",
            "--network-mode",
        ]

        try:
            processo = subprocess.Popen(
                comando,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )

            # Aguarda a montagem ficar pronta (até 10 segundos)
            montou = False
            for _ in range(20):
                time.sleep(0.5)
                if os.path.exists(f"{letra}:\\"):
                    montou = True
                    break
                # Verifica se o processo morreu
                if processo.poll() is not None:
                    erro = processo.stderr.read().decode('utf-8', errors='replace').strip()
                    return False, f"Falha ao montar: {erro or 'Processo encerrou inesperadamente.'}", None

            if not montou:
                processo.terminate()
                return False, "Timeout: A unidade não ficou pronta em 10 segundos.", None

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
        """Desmonta uma unidade virtual previamente montada."""
        letra = letra.upper().strip().rstrip(":\\")

        with self._montagem_lock:
            info = self._montagens.get(letra)
            if not info:
                return False, f"Nenhuma montagem ativa na letra {letra}:"

        processo = info["processo"]

        try:
            processo.terminate()
            processo.wait(timeout=5)
        except:
            try:
                processo.kill()
            except:
                pass

        with self._montagem_lock:
            self._montagens.pop(letra, None)

        return True, f"Unidade {letra}: desmontada com sucesso."

    def desmontar_todas(self):
        """Desmonta todas as unidades montadas. Usado no shutdown."""
        with self._montagem_lock:
            letras = list(self._montagens.keys())
        for letra in letras:
            self.desmontar_unidade(letra)

    def status_montagem(self):
        """Retorna status de todas as montagens ativas."""
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
            # Limpa montagens que caíram
            for l in letras_remover:
                self._montagens.pop(l, None)
        return resultado

    # ==================== REMOTOS ====================

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
        except:
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
        except:
            return []

    def listar_remotos_detalhado(self):
        """Retorna todos os remotos com detalhes de configuração (tipo, remote base, etc)."""
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
            # Monta status de montagem para enriquecer
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
        except:
            return []

    def obter_config_remoto(self, nome):
        """Retorna a configuração completa de um remoto específico."""
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
        except:
            return None

    # ==================== IMPORTAR CRYPT EXISTENTE ====================

    def importar_crypt(self, nome, remoto_base, senha, senha2=""):
        """Importa/configura um crypt existente (quando já existe no drive, mas não no rclone local)."""
        if not self.esta_disponivel():
            return False, "RClone não disponível."
        try:
            senha_obs = self.obscurecer_senha(senha)
            senha2_obs = self.obscurecer_senha(senha2) if senha2 else senha_obs
            params = {
                "remote": remoto_base,
                "password": senha_obs,
                "password2": senha2_obs,
                "filename_encryption": "standard",
                "directory_name_encryption": "true",
            }
            return self.criar_remoto(nome, "crypt", params)
        except Exception as e:
            return False, str(e)

    # ==================== CRYPT / REMOTO ====================

    def obscurecer_senha(self, senha):
        resultado = subprocess.run(
            [self.executavel, "obscure", senha],
            capture_output=True, text=True, encoding='utf-8', timeout=10
        )
        return resultado.stdout.strip()

    def criar_remoto(self, nome, tipo, params: dict):
        if not self.esta_disponivel():
            return False, "RClone não disponível."
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

    def criar_crypt(self, nome_crypt, remoto_base_ou_caminho, senha, senha2=""):
        if not self.esta_disponivel():
            return False, "RClone não disponível."
        try:
            senha_obs = self.obscurecer_senha(senha)
            senha2_obs = self.obscurecer_senha(senha2) if senha2 else senha_obs
            params = {
                "remote": remoto_base_ou_caminho,
                "password": senha_obs,
                "password2": senha2_obs,
                "filename_encryption": "standard",
                "directory_name_encryption": "true",
            }
            return self.criar_remoto(nome_crypt, "crypt", params)
        except Exception as e:
            return False, str(e)

    def remover_remoto(self, nome):
        """Remove um remoto da configuração do RClone."""
        if not self.esta_disponivel():
            return False, "RClone não disponível."
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
        """Thread que lê a saída do processo rclone authorize."""
        buffer_token = []
        capturando_token = False

        for linha in self._oauth_processo.stdout:
            linha_strip = linha.strip()

            # Detecta a URL de autorização (pode vir com prefixo de log rclone)
            if "127.0.0.1" in linha_strip or "localhost" in linha_strip:
                match = re.search(r'https?://\S+', linha_strip)
                if match:
                    with self._oauth_lock:
                        self._oauth_url = match.group(0).rstrip('.')

            # Detecta início do bloco de token
            if "Paste the following" in linha_strip:
                capturando_token = True
                buffer_token = []
                continue

            if capturando_token:
                if linha_strip == "<---End paste" or "End paste" in linha_strip:
                    # Monta o JSON completo
                    token_str = "".join(buffer_token).strip()
                    # Remove possível prefixo de log do rclone (ex: "2024/xx NOTICE: ...")
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
            except:
                try:
                    self._oauth_processo.kill()
                except:
                    pass
            self._oauth_processo = None

    # ==================== SERVIDOR HTTP (STREAMING FALLBACK) ====================

    def iniciar_servidor_http(self, remoto):
        if self.processo_servico:
            self.parar_servidor()
        comando = [
            self.executavel, "serve", "http", remoto,
            "--addr", f"127.0.0.1:{self.porta_servico}",
            "--read-only",
            "--vfs-cache-mode", "full",
            "--vfs-read-ahead", "128M",
            "--vfs-cache-max-size", "5G",
        ]
        self.processo_servico = subprocess.Popen(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        time.sleep(2)
        return f"http://127.0.0.1:{self.porta_servico}/"

    def parar_servidor(self):
        if self.processo_servico:
            try:
                self.processo_servico.terminate()
                self.processo_servico.wait(timeout=3)
            except:
                self.processo_servico.kill()
            self.processo_servico = None

    # ==================== LSJSON ====================

    def listar_arquivos_json(self, remoto, caminho=""):
        if not self.esta_disponivel():
            return []
        alvo = f"{remoto}:{caminho}" if caminho else f"{remoto}:"
        comando = [self.executavel, "lsjson", alvo]
        try:
            resultado = subprocess.run(
                comando, capture_output=True, text=True, encoding='utf-8', timeout=30
            )
            if resultado.returncode == 0:
                return _json.loads(resultado.stdout)
            return []
        except Exception as e:
            print("Erro ao listar json:", e)
            return []
