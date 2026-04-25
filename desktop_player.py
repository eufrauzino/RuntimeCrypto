import os
import threading
import time
import webview
import uvicorn
import runtime_server

def executar_servidor():
    import logging
    logging.getLogger("uvicorn.access").setLevel(logging.CRITICAL)
    uvicorn.run(runtime_server.app, host="127.0.0.1", port=8080, log_level="warning")

def inicio():
    threading.Thread(target=executar_servidor, daemon=True).start()
    # Dá tempo para o servidor subir
    time.sleep(1.0)
    
    janela = webview.create_window(
        title='Quantum Runtime Player', 
        url='http://127.0.0.1:8080/',
        width=1000, 
        height=700,
        background_color='#0f172a'
    )
    webview.start()

if __name__ == "__main__":
    inicio()
