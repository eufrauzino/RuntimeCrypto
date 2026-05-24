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
    nuvem.desmontar_todas()
    nuvem.parar_servidor()

app = FastAPI(title="Quantum Runtime API", lifespan=ciclo_vida)

# --- MODELS ---
class SenhaModel(BaseModel):
    senha: str

class RemotoModel(BaseModel):
    remoto: str

class CaminhoModel(BaseModel):
    caminho: str

class CriarRemotoModel(BaseModel):
    nome: str
    tipo: str
    params: dict = {}

class CriarCryptModel(BaseModel):
    nome: str
    remoto_base: str
    senha: str
    senha2: str = ""
    filename_encryption: str = "standard"
    directory_name_encryption: str = "true"
    no_data_encryption: str = "false"

class MontarModel(BaseModel):
    remoto: str
    letra: str = ""

class DesmontarModel(BaseModel):
    letra: str

class ImportarCryptModel(BaseModel):
    nome: str
    remoto_base: str
    senha: str
    senha2: str = ""
    filename_encryption: str = "standard"
    directory_name_encryption: str = "true"

class RemoverRemotoModel(BaseModel):
    nome: str

class ConfigVfsModel(BaseModel):
    vfs_cache_mode: str = "full"
    vfs_cache_max_size: str = "5G"
    vfs_cache_max_age: str = "1h"
    vfs_read_chunk_size: str = "64M"
    vfs_read_chunk_size_limit: str = "2G"
    vfs_read_ahead: str = "128M"
    buffer_size: str = "32M"
    dir_cache_time: str = "5m"
    poll_interval: str = "15s"

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

# --- MONTAGEM DE UNIDADE VIRTUAL (CORE) ---
@app.get("/api/nuvem/winfsp-status")
def winfsp_status():
    return nuvem.verificar_winfsp()

@app.get("/api/nuvem/letras-disponiveis")
def letras_disponiveis():
    return {"letras": nuvem.obter_letras_disponiveis()}

@app.get("/api/nuvem/montagem/status")
def montagem_status():
    return {"montagens": nuvem.status_montagem()}

@app.post("/api/nuvem/montagem/montar")
async def montar_unidade(dados: MontarModel):
    from fastapi.concurrency import run_in_threadpool
    sucesso, msg, letra = await run_in_threadpool(
        nuvem.montar_unidade, dados.remoto, dados.letra or None
    )
    return {"success": sucesso, "message": msg, "letra": letra}

@app.post("/api/nuvem/montagem/desmontar")
async def desmontar_unidade(dados: DesmontarModel):
    from fastapi.concurrency import run_in_threadpool
    sucesso, msg = await run_in_threadpool(nuvem.desmontar_unidade, dados.letra)
    return {"success": sucesso, "message": msg}

@app.get("/api/nuvem/remotos-detalhado")
def remotos_detalhado():
    return {"remotos": nuvem.listar_remotos_detalhado()}

@app.post("/api/nuvem/importar-crypt")
async def importar_crypt(dados: ImportarCryptModel):
    from fastapi.concurrency import run_in_threadpool
    config_crypt = {
        "filename_encryption": dados.filename_encryption,
        "directory_name_encryption": dados.directory_name_encryption,
    }
    sucesso, msg = await run_in_threadpool(
        nuvem.importar_crypt, dados.nome, dados.remoto_base, dados.senha, dados.senha2, config_crypt
    )
    return {"success": sucesso, "message": msg}

@app.post("/api/nuvem/remover-remoto")
def remover_remoto(dados: RemoverRemotoModel):
    # Primeiro desmonta se estiver montado
    montagens = nuvem.status_montagem()
    nome_limpo = dados.nome.rstrip(":")
    for m in montagens:
        if m["remoto"].rstrip(":") == nome_limpo:
            nuvem.desmontar_unidade(m["letra"])
    sucesso, msg = nuvem.remover_remoto(dados.nome)
    return {"success": sucesso, "message": msg}

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

@app.post("/api/nuvem/instalar")
async def instalar_nuvem():
    from fastapi.concurrency import run_in_threadpool
    sucesso, msg = await run_in_threadpool(nuvem.instalar_rclone_local)
    return {"success": sucesso, "message": msg}

@app.post("/api/nuvem/conectar")
async def conectar_nuvem(dados: RemotoModel):
    from fastapi.concurrency import run_in_threadpool
    try:
        url_local = await run_in_threadpool(nuvem.iniciar_servidor_http, dados.remoto)
        return {"success": True, "url": url_local}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/nuvem/desconectar")
def desconectar_nuvem():
    nuvem.parar_servidor()
    return {"success": True}

@app.get("/api/nuvem/provedores")
def listar_provedores():
    from core.rclone_manager import PROVEDORES
    return PROVEDORES

@app.get("/api/nuvem/auth-url")
async def iniciar_auth(tipo: str):
    import asyncio
    from fastapi.concurrency import run_in_threadpool
    await run_in_threadpool(nuvem.iniciar_oauth, tipo)
    # Aguarda até 10s pela URL sem bloquear o event loop
    for _ in range(20):
        status = nuvem.obter_status_oauth()
        if status["url"]:
            return {"success": True, "url": status["url"]}
        await asyncio.sleep(0.5)
    return {"success": True, "url": None}

@app.get("/api/nuvem/auth-status")
def status_auth():
    return nuvem.obter_status_oauth()

@app.post("/api/nuvem/auth-abort")
def abortar_auth():
    nuvem.abortar_oauth()
    return {"success": True}

@app.post("/api/nuvem/criar-remoto")
def criar_remoto_api(dados: CriarRemotoModel):
    sucesso, msg = nuvem.criar_remoto(dados.nome, dados.tipo, dados.params)
    return {"success": sucesso, "message": msg}

@app.post("/api/nuvem/criar-crypt")
def criar_crypt_api(dados: CriarCryptModel):
    config_crypt = {
        "filename_encryption": dados.filename_encryption,
        "directory_name_encryption": dados.directory_name_encryption,
        "no_data_encryption": dados.no_data_encryption,
    }
    sucesso, msg = nuvem.criar_crypt(dados.nome, dados.remoto_base, dados.senha, dados.senha2, config_crypt)
    return {"success": sucesso, "message": msg}

@app.get("/api/nuvem/configuracoes-vfs")
def obter_config_vfs():
    return nuvem.obter_configuracoes_vfs()

@app.post("/api/nuvem/configuracoes-vfs")
def atualizar_config_vfs(dados: ConfigVfsModel):
    config = dados.model_dump()
    resultado = nuvem.atualizar_configuracoes_vfs(config)
    return {"success": True, "config": resultado}

@app.post("/api/nuvem/configuracoes-vfs/restaurar")
def restaurar_config_vfs():
    resultado = nuvem.restaurar_configuracoes_vfs()
    return {"success": True, "config": resultado}

@app.get("/api/nuvem/browser")
def listar_pasta_nuvem(remoto: str, path: str = ""):
    global CHAVE_MESTRA
    if len(CHAVE_MESTRA) != 32:
        raise HTTPException(status_code=401, detail="Cofre trancado.")
    
    if not nuvem.esta_disponivel():
        raise HTTPException(status_code=500, detail="RClone não está disponível.")

    itens = nuvem.listar_arquivos_json(remoto, path)
    resultado = []
    
    for item in itens:
        is_dir = item.get("IsDir", False)
        nome = item.get("Name", "")
        if is_dir or nome.lower().endswith(('.mp4', '.mkv', '.avi', '.qnt')):
            caminho_item = f"{path}/{nome}".strip("/")
            resultado.append({
                "nome": nome,
                "is_dir": is_dir,
                "caminho_relativo": caminho_item
            })
            
    resultado.sort(key=lambda x: (not x['is_dir'], x['nome'].lower()))
    
    parent = ""
    if path:
        partes = [p for p in path.split("/") if p]
        if len(partes) > 1:
            parent = "/".join(partes[:-1])
            
    return {"caminho_atual": path, "parent": parent, "itens": resultado}

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
