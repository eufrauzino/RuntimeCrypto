import os
import re
import subprocess
import threading
import time
import json as _json

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


class GerenciadorRClone:
    def __init__(self):
        self.processo_servico = None
        self.porta_servico = 8081
        self.executavel = self._localizar_rclone()
        self._oauth_processo = None
        self._oauth_token = None
        self._oauth_url = None
        self._oauth_lock = threading.Lock()

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
