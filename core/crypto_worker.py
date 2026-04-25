import os
import asyncio
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import concurrent.futures
import secrets

TAMANHO_BLOCO = 1024 * 1024

def derivar_chave_mestra(senha: str, sal: bytes) -> bytes:
    """Deriva uma chave de 256 bits a partir de uma senha usando PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=sal,
        iterations=100000,
    )
    return kdf.derive(senha.encode())

def proteger_chave(chave_bruta: bytes, senha: str) -> bytes:
    """Criptografa a chave mestra com uma chave derivada da senha."""
    sal = secrets.token_bytes(16)
    chave_derivada = derivar_chave_mestra(senha, sal)
    
    # Usamos ChaCha20 para proteger a própria chave mestra dentro do cofre
    nonce = secrets.token_bytes(16)
    cifra = Cipher(algorithms.ChaCha20(chave_derivada, nonce), mode=None)
    encriptador = cifra.encryptor()
    chave_protegida = encriptador.update(chave_bruta)
    
    # Retorno: SAL (16) + NONCE (16) + CHAVE_PROTEGIDA (32)
    return sal + nonce + chave_protegida

def desproteger_chave(dados_cofre: bytes, senha: str) -> bytes:
    """Recupera a chave mestra original usando a senha."""
    sal = dados_cofre[:16]
    nonce = dados_cofre[16:32]
    chave_protegida = dados_cofre[32:]
    
    chave_derivada = derivar_chave_mestra(senha, sal)
    cifra = Cipher(algorithms.ChaCha20(chave_derivada, nonce), mode=None)
    decriptador = cifra.decryptor()
    return decriptador.update(chave_protegida)

def _tarefa_processar_bloco(chave: bytes, id_bloco: int, dados_entrada: bytes) -> bytes:
    if len(chave) != 32:
        raise ValueError("A chave deve ter exatos 256-bits.")
    
    nonce = id_bloco.to_bytes(16, byteorder="little", signed=True)
    cifra = Cipher(algorithms.ChaCha20(chave, nonce), mode=None)
    processador = cifra.decryptor()
    return processador.update(dados_entrada)

class GerenciadorCriptografia:
    def __init__(self, contagem_trabalhadores=None):
        if contagem_trabalhadores is None:
            contagem_trabalhadores = os.cpu_count() or 4
        self.executor = concurrent.futures.ProcessPoolExecutor(max_workers=max(1, contagem_trabalhadores - 1))
        
    def processar_bloco_sincrono(self, chave: bytes, id_bloco: int, dados_entrada: bytes):
        futuro = self.executor.submit(_tarefa_processar_bloco, chave, id_bloco, dados_entrada)
        return futuro.result()

    async def processar_bloco_assincrono(self, chave: bytes, id_bloco: int, dados_entrada: bytes):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, _tarefa_processar_bloco, chave, id_bloco, dados_entrada)

    def encerrar(self):
        self.executor.shutdown(wait=True)
