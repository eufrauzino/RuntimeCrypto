import os
import sys
import threading
import time
import base64
import webview
import uvicorn
import secrets
from encrypt_tool import criptografar_arquivo, gerar_chave_quantica
from core.crypto_worker import GerenciadorCriptografia, proteger_chave, desproteger_chave

# O servidor FastAPI agora recebe a chave mestra em memória via API de configuração
CHAVE_ATUAL_MEMORIA = None

class ApiPlayer:
    def __init__(self):
        self.janela = None
        self._pool_cripto = GerenciadorCriptografia()
        self.chave_mestra = None

    def definir_janela(self, janela):
        self.janela = janela

    def verificar_cofre(self):
        """Verifica se o cofre de chaves existe."""
        return os.path.exists("cofre.bin")

    def inicializar_cofre(self, senha: str):
        """Cria o cofre pela primeira vez com uma nova chave quântica."""
        try:
            chave_bruta = gerar_chave_quantica()
            dados_protegidos = proteger_chave(chave_bruta, senha)
            with open("cofre.bin", "wb") as f:
                f.write(dados_protegidos)
            self.chave_mestra = chave_bruta
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def abrir_cofre(self, senha: str):
        """Tenta abrir o cofre usando a senha fornecida."""
        try:
            with open("cofre.bin", "rb") as f:
                dados_cofre = f.read()
            self.chave_mestra = desproteger_chave(dados_cofre, senha)
            
            # Validação rápida: a chave deve ter 32 bytes
            if len(self.chave_mestra) != 32:
                raise ValueError("Senha incorreta ou cofre corrompido.")
            
            # Configura a chave no servidor global (em memória)
            import runtime_server
            runtime_server.CHAVE_MESTRA = self.chave_mestra
            
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": "Senha inválida ou cofre inacessível."}

    def selecionar_e_processar_video(self):
        if not self.chave_mestra:
            return {"success": False, "error": "Cofre não desbloqueado."}

        tipos_arquivo = ('Arquivos de Vídeo (*.mp4;*.avi;*.mkv)', 'Todos os arquivos (*.*)')
        resultado = self.janela.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=tipos_arquivo)
        
        if not resultado:
            return {"success": False, "error": "Cancelado"}
            
        arquivo_alvo = resultado[0]
        
        try:
            nome_arquivo_qnt = arquivo_alvo + ".qnt"
            
            if not os.path.exists(nome_arquivo_qnt):
                self.janela.evaluate_js(f"atualizarProgresso('Criptografando... (Aguarde)')")
                criptografar_arquivo(arquivo_alvo, self.chave_mestra, self._pool_cripto)
            
            caminho_abs = os.path.abspath(nome_arquivo_qnt)
            caminho_b64 = base64.b64encode(caminho_abs.encode('utf-8')).decode('utf-8')
            
            return {"success": True, "url": f"http://127.0.0.1:8080/play/{caminho_b64}"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

def executar_servidor():
    import logging
    logging.getLogger("uvicorn.access").setLevel(logging.CRITICAL)
    # Importa o app aqui para garantir que a chave mestra em memória seja compartilhada
    from runtime_server import app
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="warning")

def inicio():
    # Inicia o servidor em background
    threading.Thread(target=executar_servidor, daemon=True).start()
    time.sleep(0.5)

    api = ApiPlayer()
    caminho_ui = os.path.abspath(os.path.join(os.path.dirname(__file__), "ui", "index.html"))
    
    janela = webview.create_window(
        title='Quantum Runtime Player', 
        url=f'file://{caminho_ui}',
        js_api=api,
        width=1000, 
        height=700,
        background_color='#0f172a'
    )
    api.definir_janela(janela)
    webview.start()

if __name__ == "__main__":
    # Remove arquivo de chave antiga se existir
    if os.path.exists("master.key"):
        os.remove("master.key")
    inicio()
