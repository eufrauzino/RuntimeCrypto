import os
import sys
import secrets
from core.crypto_worker import GerenciadorCriptografia, TAMANHO_BLOCO

def gerar_chave_quantica():
    return secrets.token_bytes(32)

def criptografar_arquivo(caminho_arquivo: str, chave: bytes, gerenciador: GerenciadorCriptografia):
    print(f"[*] Processando ativo: {caminho_arquivo}")
    caminho_saida = caminho_arquivo + ".qnt"
    
    tamanho_total = os.path.getsize(caminho_arquivo)
    processado = 0
    
    with open(caminho_arquivo, 'rb') as entrada, open(caminho_saida, 'wb') as saida:
        id_bloco = 0
        while True:
            dados_brutos = entrada.read(TAMANHO_BLOCO)
            if not dados_brutos:
                break
            
            dados_criptografados = gerenciador.processar_bloco_sincrono(chave, id_bloco, dados_brutos)
            saida.write(dados_criptografados)
            
            processado += len(dados_brutos)
            porcentagem = (processado / tamanho_total) * 100
            print(f"  -> Protegendo arquivo... {porcentagem:.1f}%", end="\r")
            
            id_bloco += 1
            
    print(f"\n[+] Operação concluída. Saída: {caminho_saida}")
    return caminho_saida

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python encrypt_tool.py arquivo.mp4")
        sys.exit(1)
        
    arquivo_alvo = sys.argv[1]
    
    if not os.path.exists("master.key"):
        chave = gerar_chave_quantica()
        with open("master.key", "wb") as kf:
            kf.write(chave)
        print("[!] Nova chave mestra gerada.")
    else:
        with open("master.key", "rb") as kf:
            chave = kf.read()
            
    gerenciador = GerenciadorCriptografia()
    try:
        criptografar_arquivo(arquivo_alvo, chave, gerenciador)
    except Exception as e:
        print(f"\n[X] Falha: {e}")
    finally:
        gerenciador.encerrar()
