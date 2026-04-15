import os
import sys
import secrets
import json
from core.crypto_worker import GerenciadorCriptografia, TAMANHO_BLOCO

def gerar_chave_quantica():
    return secrets.token_bytes(32)

def criptografar_arquivo(caminho_arquivo: str, chave: bytes, gerenciador: GerenciadorCriptografia):
    print(f"[*] Processando ativo: {caminho_arquivo}")
    caminho_saida = caminho_arquivo + ".qnt"
    
    # Criar metadados (Header de 1024 bytes)
    nome_original = os.path.basename(caminho_arquivo)
    metadados = json.dumps({"nome": nome_original}).encode('utf-8')
    header = metadados.ljust(1024, b'\0') # Padding para 1KB
    
    # Criptografar o header (usamos o ID de bloco -1 para o header)
    header_cripto = gerenciador.processar_bloco_sincrono(chave, -1, header)
    
    tamanho_total = os.path.getsize(caminho_arquivo)
    processado = 0
    
    with open(caminho_arquivo, 'rb') as entrada, open(caminho_saida, 'wb') as saida:
        # Escreve o cabeçalho de 1KB primeiro
        saida.write(header_cripto)
        
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
    # Mantendo compatibilidade com execução direta via terminal
    if len(sys.argv) < 2:
        print("Uso: python encrypt_tool.py arquivo.mp4")
        sys.exit(1)
        
    arquivo_alvo = sys.argv[1]
    
    # Se não houver cofre, tentamos ler master.key (fallback para compatibilidade)
    chave = None
    if os.path.exists("master.key"):
        with open("master.key", "rb") as kf:
            chave = kf.read()
    else:
        print("[!] Erro: Execute o player primeiro para criar o cofre ou forneça uma master.key")
        sys.exit(1)
            
    gerenciador = GerenciadorCriptografia()
    try:
        criptografar_arquivo(arquivo_alvo, chave, gerenciador)
    except Exception as e:
        print(f"\n[X] Falha: {e}")
    finally:
        gerenciador.encerrar()
