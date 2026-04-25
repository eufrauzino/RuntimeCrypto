import os
import subprocess
import threading
import time
import signal

class GerenciadorRClone:
    def __init__(self):
        self.processo_servico = None
        self.porta_servico = 8081
        self.executavel = self._localizar_rclone()

    def _localizar_rclone(self):
        # Procura no PATH do sistema ou na pasta raiz
        caminhos = ["rclone.exe", "rclone", "./rclone.exe"]
        for caminho in caminhos:
            try:
                subprocess.run([caminho, "--version"], capture_output=True)
                return caminho
            except:
                continue
        return None

    def esta_disponivel(self):
        return self.executavel is not None

    def listar_remotos(self):
        if not self.esta_disponivel():
            return []
        try:
            resultado = subprocess.run([self.executavel, "listremotes"], capture_output=True, text=True)
            remotos = [r.strip() for r in resultado.stdout.split('\n') if r.strip()]
            return remotos
        except:
            return []

    def iniciar_servidor_http(self, remoto):
        """Inicia o rclone serve http para disponibilizar os arquivos da nuvem localmente."""
        if self.processo_servico:
            self.parar_servidor()

        # Comando para servir o remoto via HTTP localmente
        comando = [
            self.executavel, "serve", "http", remoto,
            "--addr", f"127.0.0.1:{self.porta_servico}",
            "--read-only",
            "--vfs-cache-mode", "full",
            "--vfs-read-ahead", "128M",
            "--vfs-cache-max-size", "5G"
        ]
        
        self.processo_servico = subprocess.Popen(
            comando, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        # Aguarda um momento para o serviço subir
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
