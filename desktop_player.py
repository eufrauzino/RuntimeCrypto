import os
import sys
import threading
import time
import base64
import json
import webview
import uvicorn
import secrets
from encrypt_tool import criptografar_arquivo, gerar_chave_quantica
from core.crypto_worker import GerenciadorCriptografia, proteger_chave, desproteger_chave
from core.rclone_manager import GerenciadorRClone

import runtime_server

class ApiPlayer:
    def __init__(self):
        self.janela = None
        self.chave_mestra = None
        self.nuvem = GerenciadorRClone()

    def definir_janela(self, janela):
        self.janela = janela

    def verificar_cofre(self):
        return os.path.exists("cofre.bin")

    def inicializar_cofre(self, senha: str):
        try:
            chave_bruta = gerar_chave_quantica()
            dados_protegidos = proteger_chave(chave_bruta, senha)
            with open("cofre.bin", "wb") as f:
                f.write(dados_protegidos)
            self.chave_mestra = chave_bruta
            runtime_server.CHAVE_MESTRA = self.chave_mestra
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def abrir_cofre(self, senha: str):
        try:
            with open("cofre.bin", "rb") as f:
                dados_cofre = f.read()
            self.chave_mestra = desproteger_chave(dados_cofre, senha)
            
            if len(self.chave_mestra) != 32:
                raise ValueError("Senha incorreta.")
            
            runtime_server.CHAVE_MESTRA = self.chave_mestra
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": "Senha inválida."}

    # --- RClone / Cloud Integration ---
    def obter_status_nuvem(self):
        return {
            "disponivel": self.nuvem.esta_disponivel(),
            "remotos": self.nuvem.listar_remotos() if self.nuvem.esta_disponivel() else []
        }

    def conectar_nuvem(self, remoto):
        try:
            url_local = self.nuvem.iniciar_servidor_http(remoto)
            return {"success": True, "url": url_local}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- Historico ---
    def _carregar_historico(self):
        if not os.path.exists("historico.bin") or not self.chave_mestra:
            return []
        try:
            with open("historico.bin", "rb") as f:
                dados_cripto = f.read()
            dados_brutos = runtime_server.gerenciador.processar_bloco_sincrono(self.chave_mestra, -2, dados_cripto)
            return json.loads(dados_brutos.decode('utf-8').strip('\0'))
        except:
            return []

    def _salvar_historico(self, lista_historico):
        if not self.chave_mestra: return
        try:
            dados_json = json.dumps(lista_historico[:10]).encode('utf-8')
            dados_padding = dados_json.ljust(4096, b'\0')
            dados_cripto = runtime_server.gerenciador.processar_bloco_sincrono(self.chave_mestra, -2, dados_padding)
            with open("historico.bin", "wb") as f:
                f.write(dados_cripto)
        except:
            pass

    def obter_historico(self):
        historico = self._carregar_historico()
        validados = [item for item in historico if os.path.exists(item['caminho'])]
        if len(validados) != len(historico):
            self._salvar_historico(validados)
        return validados

    # --- Player Logic ---
    def selecionar_e_processar_video(self):
        if not self.chave_mestra:
            return {"success": False, "error": "Cofre não desbloqueado."}

        tipos_arquivo = ('Arquivos de Vídeo (*.mp4;*.avi;*.mkv;*.qnt)', 'Todos os arquivos (*.*)')
        resultado = self.janela.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=False, file_types=tipos_arquivo)
        
        if not resultado:
            return {"success": False, "error": "Cancelado"}
            
        return self.preparar_reproducao(resultado[0])

    def preparar_reproducao(self, arquivo_alvo):
        try:
            # Caso seja arquivo local mas nao .qnt, protegemos
            if not arquivo_alvo.endswith(".qnt") and not arquivo_alvo.startswith("http"):
                nome_arquivo_qnt = arquivo_alvo + ".qnt"
                if not os.path.exists(nome_arquivo_qnt):
                    self.janela.evaluate_js(f"atualizarProgresso('Protegendo arquivo local... (Aguarde)')")
                    criptografar_arquivo(arquivo_alvo, self.chave_mestra, runtime_server.gerenciador)
                arquivo_alvo = nome_arquivo_qnt
            
            # Se for local, extrai metadados do cabeçalho
            nome_real = os.path.basename(arquivo_alvo)
            if not arquivo_alvo.startswith("http"):
                with open(arquivo_alvo, 'rb') as f:
                    header_cripto = f.read(1024)
                    header_bruto = runtime_server.gerenciador.processar_bloco_sincrono(self.chave_mestra, -1, header_cripto)
                    metadados = json.loads(header_bruto.decode('utf-8').strip('\0'))
                    nome_real = metadados.get("nome", nome_real)
                
                # Atualiza Histórico apenas para locais
                historico = self._carregar_historico()
                historico = [h for h in historico if h['caminho'] != arquivo_alvo]
                historico.insert(0, {"nome": nome_real, "caminho": arquivo_alvo})
                self._salvar_historico(historico)

                caminho_abs = os.path.abspath(arquivo_alvo)
                caminho_final = base64.b64encode(caminho_abs.encode('utf-8')).decode('utf-8')
                url_stream = f"http://127.0.0.1:8080/play/{caminho_final}"
            else:
                # Se for da nuvem, o rclone ja descriptografa se for RClone Crypt
                # Caso contrário, o stream precisaria passar pelo nosso motor (futura melhoria)
                url_stream = arquivo_alvo 

            return {"success": True, "url": url_stream, "nome": nome_real}
        except Exception as e:
            return {"success": False, "error": str(e)}

def executar_servidor():
    import logging
    logging.getLogger("uvicorn.access").setLevel(logging.CRITICAL)
    uvicorn.run(runtime_server.app, host="127.0.0.1", port=8080, log_level="warning")

def inicio():
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
    api.nuvem.parar_servidor() # Limpa o processo do rclone ao sair

if __name__ == "__main__":
    inicio()
