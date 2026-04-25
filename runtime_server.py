import os
import uvicorn
import base64
import json
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from core.crypto_worker import GerenciadorCriptografia, TAMANHO_BLOCO
from contextlib import asynccontextmanager

# O cabeçalho ocupa os primeiros 1024 bytes
TAMANHO_CABECALHO = 1024

gerenciador = GerenciadorCriptografia()

@asynccontextmanager
async def ciclo_vida(app: FastAPI):
    yield
    gerenciador.encerrar()

app = FastAPI(title="Runtime Crypto Core", lifespan=ciclo_vida)

# CHAVE_MESTRA injetada em memória
CHAVE_MESTRA = b""

@app.get("/play/{caminho_base64}")
async def transmitir_video(caminho_base64: str, requisicao: Request):
    global CHAVE_MESTRA
    if len(CHAVE_MESTRA) != 32:
        raise HTTPException(status_code=401, detail="Cofre trancado.")
    
    try:
        caminho_arquivo = base64.b64decode(caminho_base64).decode('utf-8')
    except:
        raise HTTPException(status_code=400, detail="Caminho inválido.")

    if not os.path.exists(caminho_arquivo):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
        
    # Tamanho real do vídeo é o tamanho do arquivo menos o cabeçalho
    tamanho_total_arquivo = os.path.getsize(caminho_arquivo)
    tamanho_video = tamanho_total_arquivo - TAMANHO_CABECALHO
    
    cabecalho_range = requisicao.headers.get("Range")
    inicio = 0
    fim = tamanho_video - 1
    
    if cabecalho_range:
        string_range = cabecalho_range.replace("bytes=", "")
        partes = string_range.split("-")
        if partes[0]: inicio = int(partes[0])
        if partes[1]: fim = int(partes[1])
            
    tamanho_trecho = (fim - inicio) + 1
    
    async def gerador_streaming_interno():
        idx_bloco_inicio = inicio // TAMANHO_BLOCO
        idx_bloco_fim = fim // TAMANHO_BLOCO
        offset_bytes_inicio = inicio % TAMANHO_BLOCO
        
        with open(caminho_arquivo, 'rb') as f:
            for id_bloco in range(idx_bloco_inicio, idx_bloco_fim + 1):
                # Soma o offset do cabeçalho para pular a parte dos metadados
                f.seek(TAMANHO_CABECALHO + (id_bloco * TAMANHO_BLOCO))
                dados_criptografados = f.read(TAMANHO_BLOCO)
                if not dados_criptografados: break
                    
                dados_descriptografados = await gerenciador.processar_bloco_assincrono(CHAVE_MESTRA, id_bloco, dados_criptografados)
                
                if id_bloco == idx_bloco_inicio and id_bloco == idx_bloco_fim:
                    offset_bytes_fim = fim % TAMANHO_BLOCO
                    yield dados_descriptografados[offset_bytes_inicio:offset_bytes_fim+1]
                elif id_bloco == idx_bloco_inicio:
                    yield dados_descriptografados[offset_bytes_inicio:]
                elif id_bloco == idx_bloco_fim:
                    offset_bytes_fim = fim % TAMANHO_BLOCO
                    yield dados_descriptografados[:offset_bytes_fim+1]
                else:
                    yield dados_descriptografados
                
    headers = {
        "Content-Range": f"bytes {inicio}-{fim}/{tamanho_video}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(tamanho_trecho),
        "Content-Type": "video/mp4",
    }
    
    return StreamingResponse(
        gerador_streaming_interno(),
        status_code=206 if cabecalho_range else 200,
        headers=headers
    )

if __name__ == "__main__":
    uvicorn.run("runtime_server:app", host="0.0.0.0", port=8080, workers=1)
