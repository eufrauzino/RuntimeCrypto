import os
import json
import base64
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.crypto_worker import GerenciadorCriptografia, TAMANHO_BLOCO, proteger_chave, desproteger_chave
from encrypt_tool import criptografar_arquivo, gerar_chave_quantica
from core.rclone_manager import GerenciadorRClone

TAMANHO_CABECALHO = 1024
CHAVE_MESTRA = b""

gerenciador = GerenciadorCriptografia()
nuvem = GerenciadorRClone()

@asynccontextmanager
async def ciclo_vida(app: FastAPI):
    yield
    gerenciador.encerrar()
    nuvem.parar_servidor()

app = FastAPI(title="Quantum Runtime API", lifespan=ciclo_vida)

# --- MODELS ---
class SenhaModel(BaseModel):
    senha: str

class RemotoModel(BaseModel):
    remoto: str

class CaminhoModel(BaseModel):
    caminho: str

# --- HISTORICO ---
def _carregar_historico():
    global CHAVE_MESTRA
    if not os.path.exists("historico.bin") or not CHAVE_MESTRA:
        return []
    try:
        with open("historico.bin", "rb") as f:
            dados_cripto = f.read()
        dados_brutos = gerenciador.processar_bloco_sincrono(CHAVE_MESTRA, -2, dados_cripto)
        return json.loads(dados_brutos.decode('utf-8').strip('\0'))
    except:
        return []

def _salvar_historico(lista_historico):
    global CHAVE_MESTRA
    if not CHAVE_MESTRA: return
    try:
        dados_json = json.dumps(lista_historico[:10]).encode('utf-8')
        dados_padding = dados_json.ljust(4096, b'\0')
        dados_cripto = gerenciador.processar_bloco_sincrono(CHAVE_MESTRA, -2, dados_padding)
        with open("historico.bin", "wb") as f:
            f.write(dados_cripto)
    except:
        pass

# --- AUTH & COFRE ---
@app.get("/api/cofre/status")
def status_cofre():
    existe = os.path.exists("cofre.bin")
    aberto = len(CHAVE_MESTRA) == 32
    return {"existe": existe, "aberto": aberto}

@app.post("/api/cofre/inicializar")
def inicializar_cofre(dados: SenhaModel):
    global CHAVE_MESTRA
    try:
        chave_bruta = gerar_chave_quantica()
        dados_protegidos = proteger_chave(chave_bruta, dados.senha)
        with open("cofre.bin", "wb") as f:
            f.write(dados_protegidos)
        CHAVE_MESTRA = chave_bruta
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/cofre/abrir")
def abrir_cofre(dados: SenhaModel):
    global CHAVE_MESTRA
    try:
        with open("cofre.bin", "rb") as f:
            dados_cofre = f.read()
        CHAVE_MESTRA = desproteger_chave(dados_cofre, dados.senha)
        if len(CHAVE_MESTRA) != 32:
            raise ValueError("Senha incorreta.")
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": "Senha inválida."}

# --- BROWSER / ARQUIVOS ---
def get_drives_windows():
    if os.name == 'nt':
        import string
        drives = []
        for letter in string.ascii_uppercase:
            if os.path.exists(f"{letter}:\\"):
                drives.append(f"{letter}:\\")
        return drives
    return ["/"]

@app.get("/api/browser")
def listar_pasta(path: str = ""):
    global CHAVE_MESTRA
    if len(CHAVE_MESTRA) != 32:
        raise HTTPException(status_code=401, detail="Cofre trancado.")
    
    if not path:
        drives = get_drives_windows()
        return {"caminho_atual": "", "itens": [{"nome": d, "caminho": d, "is_dir": True} for d in drives]}
        
    if not os.path.exists(path) or not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="Pasta não encontrada.")
        
    itens = []
    try:
        for f in os.listdir(path):
            full_path = os.path.join(path, f)
            is_dir = os.path.isdir(full_path)
            if is_dir or f.lower().endswith(('.mp4', '.mkv', '.avi', '.qnt')):
                itens.append({"nome": f, "caminho": full_path, "is_dir": is_dir})
    except PermissionError:
        pass
        
    itens.sort(key=lambda x: (not x['is_dir'], x['nome'].lower()))
    parent = os.path.dirname(path) if path.strip("/\\") and path != "/" and not path.endswith(":\\") else ""
    return {"caminho_atual": path, "parent": parent, "itens": itens}

@app.post("/api/preparar")
def preparar_video(dados: CaminhoModel):
    global CHAVE_MESTRA
    if len(CHAVE_MESTRA) != 32:
        return {"success": False, "error": "Cofre não desbloqueado."}
        
    arquivo_alvo = dados.caminho
    is_http = arquivo_alvo.startswith("http://") or arquivo_alvo.startswith("https://")
    
    try:
        if not is_http and not arquivo_alvo.endswith(".qnt"):
            nome_arquivo_qnt = arquivo_alvo + ".qnt"
            if not os.path.exists(nome_arquivo_qnt):
                criptografar_arquivo(arquivo_alvo, CHAVE_MESTRA, gerenciador)
            arquivo_alvo = nome_arquivo_qnt
            
        nome_real = os.path.basename(arquivo_alvo)
        if not is_http:
            with open(arquivo_alvo, 'rb') as f:
                header_cripto = f.read(1024)
        else:
            import urllib.request
            req = urllib.request.Request(arquivo_alvo)
            req.add_header('Range', 'bytes=0-1023')
            with urllib.request.urlopen(req) as resp:
                header_cripto = resp.read()
                
        # Garante que ele recarregue e remova paddings
        header_cripto = header_cripto.ljust(1024, b'\0')
        header_bruto = gerenciador.processar_bloco_sincrono(CHAVE_MESTRA, -1, header_cripto)
        
        try:
            metadados = json.loads(header_bruto.decode('utf-8').strip('\0'))
            nome_real = metadados.get("nome", nome_real)
        except:
            pass # Continua com o nome original se nao conseguir decodar o JSON
            
        if not is_http:
            # Atualiza Histórico apenas para locais, para evitar URLs que podem expirar
            historico = _carregar_historico()
            historico = [h for h in historico if h['caminho'] != arquivo_alvo]
            historico.insert(0, {"nome": nome_real, "caminho": arquivo_alvo})
            _salvar_historico(historico)
            caminho_abs = os.path.abspath(arquivo_alvo)
        else:
            caminho_abs = arquivo_alvo

        caminho_final = base64.b64encode(caminho_abs.encode('utf-8')).decode('utf-8')
        url_stream = f"/play/{caminho_final}"

        return {"success": True, "url": url_stream, "nome": nome_real}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/historico")
def obter_historico():
    historico = _carregar_historico()
    validados = [item for item in historico if os.path.exists(item['caminho'])]
    if len(validados) != len(historico):
        _salvar_historico(validados)
    return validados

# --- NUVEM (RClone) ---
@app.get("/api/nuvem/status")
def status_nuvem():
    return {
        "disponivel": nuvem.esta_disponivel(),
        "remotos": nuvem.listar_remotos() if nuvem.esta_disponivel() else []
    }

@app.post("/api/nuvem/conectar")
def conectar_nuvem(dados: RemotoModel):
    try:
        url_local = nuvem.iniciar_servidor_http(dados.remoto)
        return {"success": True, "url": url_local}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/nuvem/desconectar")
def desconectar_nuvem():
    nuvem.parar_servidor()
    return {"success": True}

# --- MOTOR DE STREAMING QUÂNTICO ---
@app.get("/play/{caminho_base64}")
async def transmitir_video(caminho_base64: str, requisicao: Request):
    global CHAVE_MESTRA
    if len(CHAVE_MESTRA) != 32:
        raise HTTPException(status_code=401, detail="Cofre trancado.")
    
    try:
        caminho_arquivo = base64.b64decode(caminho_base64).decode('utf-8')
    except:
        raise HTTPException(status_code=400, detail="Caminho inválido.")

    is_http = caminho_arquivo.startswith("http://") or caminho_arquivo.startswith("https://")

    if not is_http and not os.path.exists(caminho_arquivo):
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
        
    tamanho_total_arquivo = 0
    
    if is_http:
        try:
            import urllib.request
            from fastapi.concurrency import run_in_threadpool
            
            def _fetch_head():
                req = urllib.request.Request(caminho_arquivo, method="HEAD")
                with urllib.request.urlopen(req) as resp:
                    return int(resp.headers.get("Content-Length", 0))
            tamanho_total_arquivo = await run_in_threadpool(_fetch_head)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Erro ao acessar nuvem: {e}")
    else:
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
        from fastapi.concurrency import run_in_threadpool
        import urllib.request
        
        idx_bloco_inicio = inicio // TAMANHO_BLOCO
        idx_bloco_fim = fim // TAMANHO_BLOCO
        offset_bytes_inicio = inicio % TAMANHO_BLOCO
        
        def _fetch_chunk(url, byte_start, byte_end):
            req = urllib.request.Request(url)
            req.add_header('Range', f'bytes={byte_start}-{byte_end}')
            with urllib.request.urlopen(req) as resp:
                return resp.read()

        if is_http:
            for id_bloco in range(idx_bloco_inicio, idx_bloco_fim + 1):
                f_inicio = TAMANHO_CABECALHO + (id_bloco * TAMANHO_BLOCO)
                f_fim = f_inicio + TAMANHO_BLOCO - 1
                
                try:
                    dados_criptografados = await run_in_threadpool(_fetch_chunk, caminho_arquivo, f_inicio, f_fim)
                except Exception:
                    break
                    
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
        else:
            with open(caminho_arquivo, 'rb') as f:
                for id_bloco in range(idx_bloco_inicio, idx_bloco_fim + 1):
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

# --- FRONTEND ESTATICO ---
caminho_ui = os.path.join(os.path.dirname(__file__), "ui")
@app.get("/")
def index():
    return FileResponse(os.path.join(caminho_ui, "index.html"))

app.mount("/", StaticFiles(directory=caminho_ui), name="ui")

if __name__ == "__main__":
    uvicorn.run("runtime_server:app", host="0.0.0.0", port=8080, workers=1)
