import os
import sys
import json
import time
import queue
import threading
import webbrowser
import subprocess

from core.rclone_manager import GerenciadorRClone, PROVEDORES

# ---------------------------------------------------------------------------
# Globais
# ---------------------------------------------------------------------------

gerenciador = GerenciadorRClone()
_dialog_queue = queue.Queue()
_icon = None
_janela = None

# ---------------------------------------------------------------------------
# Geracao de icones com Pillow
# ---------------------------------------------------------------------------

def _gerar_icone_tray(tamanho=64):
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (tamanho, tamanho), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    m = tamanho // 8
    corpo = (m * 2, m * 3, m * 6, m * 6)
    draw.rounded_rectangle(corpo, radius=m // 2, fill="#10b981")

    alca_x0 = m * 6 - m
    alca_y0 = m * 2
    alca_x1 = m * 6 + m
    alca_y1 = m * 3 + m // 2
    draw.arc(
        [alca_x0, alca_y0 - m, alca_x1, alca_y1],
        start=180, end=0,
        fill="#10b981", width=m
    )

    buraco_cx = m * 4
    buraco_cy = m * 4 + m // 2
    buraco_r = m // 2 + 1
    draw.ellipse(
        [buraco_cx - buraco_r, buraco_cy - buraco_r, buraco_cx + buraco_r, buraco_cy + buraco_r],
        fill="#0d1b2a"
    )

    return img


# ---------------------------------------------------------------------------
# Menu do tray (reconstrução dinâmica)
# ---------------------------------------------------------------------------

def _atualizar_menu_tray():
    """Reconstroi o menu do tray com o estado atual dos cofres."""
    import pystray
    global _icon

    if not _icon:
        return

    cofres = gerenciador.listar_cofres()
    montados = [c for c in cofres if c.get("montado")]
    trancados = [c for c in cofres if not c.get("montado")]

    menu_items = []

    menu_items.append(pystray.MenuItem(
        "Abrir RuntimeCrypto",
        _callback_mostrar_janela,
        default=True,
    ))
    menu_items.append(pystray.Menu.SEPARATOR)

    for c in trancados:
        nome = c["nome"]
        provedor = c.get("provedor_nome", "")
        menu_items.append(pystray.MenuItem(
            f"🔴 {nome}  [{provedor}]",
            _criar_callback_cofre(nome),
        ))

    for c in montados:
        nome = c["nome"]
        letra = c.get("letra", "?")
        menu_items.append(pystray.MenuItem(
            f"🟢 {nome}  ({letra}:)",
            _criar_callback_cofre(nome),
        ))

    if cofres:
        menu_items.append(pystray.Menu.SEPARATOR)

    menu_items.append(pystray.MenuItem("Novo Cofre...", _callback_novo_cofre_tray))
    menu_items.append(pystray.Menu.SEPARATOR)

    sub_config = pystray.Menu(
        pystray.MenuItem(
            "Auto-iniciar com Windows",
            _callback_auto_iniciar,
            checked=lambda item: _verificar_auto_iniciar(),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Configurações VFS...", _callback_config_vfs_tray),
        pystray.MenuItem("Verificar WinFsp", _callback_verificar_winfsp_tray),
    )

    menu_items.append(pystray.MenuItem("Configurações", sub_config))
    menu_items.append(pystray.Menu.SEPARATOR)
    menu_items.append(pystray.MenuItem("Sobre", _callback_sobre_tray))
    menu_items.append(pystray.MenuItem("Sair", _callback_sair_tray))

    _icon.menu = pystray.Menu(*menu_items)


def _criar_callback_cofre(nome):
    def callback(icon, item):
        _dialog_queue.put(("cofre", nome))
    return callback


# ---------------------------------------------------------------------------
# Callbacks do tray
# ---------------------------------------------------------------------------

def _callback_mostrar_janela(icon=None, item=None):
    _dialog_queue.put(("mostrar_janela", None))


def _callback_novo_cofre_tray(icon, item):
    _dialog_queue.put(("novo_cofre", None))


def _callback_config_vfs_tray(icon, item):
    _dialog_queue.put(("config_vfs", None))


def _callback_verificar_winfsp_tray(icon, item):
    _dialog_queue.put(("verificar_winfsp", None))


def _callback_sobre_tray(icon, item):
    _dialog_queue.put(("sobre", None))


def _callback_sair_tray(icon, item):
    _dialog_queue.put(("sair", None))


def _callback_auto_iniciar(icon, item):
    atual = _verificar_auto_iniciar()
    if atual:
        _remover_auto_iniciar()
    else:
        _adicionar_auto_iniciar()
    _atualizar_menu_tray()


# ---------------------------------------------------------------------------
# Auto-iniciar (registro Windows)
# ---------------------------------------------------------------------------

def _verificar_auto_iniciar():
    if os.name != 'nt':
        return False
    try:
        import winreg
        chave = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_READ
        )
        try:
            valor, _ = winreg.QueryValueEx(chave, "RuntimeCrypto")
            winreg.CloseKey(chave)
            return True
        except FileNotFoundError:
            winreg.CloseKey(chave)
            return False
    except Exception:
        return False


def _adicionar_auto_iniciar():
    if os.name != 'nt':
        return
    try:
        import winreg
        chave = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        exe_path = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
        winreg.SetValueEx(chave, "RuntimeCrypto", 0, winreg.REG_SZ, exe_path)
        winreg.CloseKey(chave)
    except Exception as e:
        _dialog_queue.put(("msg", ("Erro", f"Erro ao configurar auto-início: {e}", "erro")))


def _remover_auto_iniciar():
    if os.name != 'nt':
        return
    try:
        import winreg
        chave = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        try:
            winreg.DeleteValue(chave, "RuntimeCrypto")
        except FileNotFoundError:
            pass
        winreg.CloseKey(chave)
    except Exception as e:
        _dialog_queue.put(("msg", ("Erro", f"Erro ao remover auto-início: {e}", "erro")))


# ---------------------------------------------------------------------------
# Fluxo OAuth
# ---------------------------------------------------------------------------

def _fluxo_oauth(tipo, nome_base):
    """Executa fluxo OAuth, abrindo o navegador, e cria o remoto base com o token."""
    gerenciador.iniciar_oauth(tipo)
    time.sleep(1)

    status = gerenciador.obter_status_oauth()
    if status["url"]:
        webbrowser.open(status["url"])
        _dialog_queue.put(("msg", (
            "Autorização",
            "O navegador foi aberto para autorização.\n"
            "Após concluir, volte para esta janela.",
            "info"
        )))

    for _ in range(120):
        time.sleep(1)
        status = gerenciador.obter_status_oauth()
        if status["concluido"]:
            token = status["token"]
            if token:
                try:
                    token_data = json.loads(token)
                    sucesso, msg = gerenciador.criar_remoto(
                        nome_base, tipo,
                        {"token": token}
                    )
                    return sucesso, msg
                except json.JSONDecodeError:
                    return False, "Token OAuth inválido (JSON malformado)."
                except Exception as e:
                    return False, str(e)
            return False, "Token não encontrado na saída do rclone."

    gerenciador.abortar_oauth()
    return False, "Timeout: Autorização não concluída em 2 minutos."


# ---------------------------------------------------------------------------
# Ações dos cofres (desbloquear / trancar)
# ---------------------------------------------------------------------------

def _acao_cofre(cofre):
    """Callback quando o usuário clica em um cofre (card ou tray)."""
    nome = cofre if isinstance(cofre, str) else cofre.get("nome")
    dados_cofre = gerenciador.obter_cofre(nome)
    if not dados_cofre:
        return

    # Verificar se está montado
    montagens = {m["remoto"].rstrip(":"): m for m in gerenciador.status_montagem()}
    montado = nome in montagens

    if montado:
        _travar_cofre(nome)
    else:
        _destravar_cofre(nome)


def _destravar_cofre(nome):
    """Destranca (monta) um cofre."""
    from gui.dialogos import DialogoSenha

    senha = gerenciador.obter_senha(nome)
    if not senha:
        dialogo = DialogoSenha(_janela, nome, "desbloquear")
        senha = dialogo.obter_resultado()
    if not senha:
        return

    def _executar():
        gerenciador.armazenar_senha(nome, senha)
        sucesso, msg, letra = gerenciador.montar_unidade(
            nome, letra=None, senha=senha
        )
        _dialog_queue.put(("resultado_montagem", (nome, sucesso, msg, letra, senha)))

    threading.Thread(target=_executar, daemon=True).start()


def _travar_cofre(nome):
    """Tranca (desmonta) um cofre."""
    from gui.dialogos import DialogoMensagem

    letra = gerenciador.obter_letra_por_remoto(nome)
    if letra:
        sucesso, msg = gerenciador.desmontar_unidade(letra)
    else:
        sucesso, msg = gerenciador.desmontar_unidade(nome)

    gerenciador.limpar_senha(nome)
    _atualizar_menu_tray()
    if _janela:
        _janela.forcar_atualizacao()

    tipo = "info" if sucesso else "erro"
    DialogoMensagem(
        _janela, "Cofre Trancado" if sucesso else "Erro", msg, tipo
    ).aguardar()


def _resultado_montagem(nome, sucesso, msg, letra, senha):
    """Callback após tentativa de montagem."""
    from gui.dialogos import DialogoMensagem

    if sucesso and letra:
        subprocess.Popen(["explorer", f"{letra}:\\"],
                         creationflags=subprocess.CREATE_NO_WINDOW)
        DialogoMensagem(
            _janela,
            "Cofre Destrancado",
            f"'{nome}' montado em {letra}:\\\n\nO Explorador de Arquivos foi aberto.",
            "info",
        ).aguardar()
        _atualizar_menu_tray()
        if _janela:
            _janela.forcar_atualizacao()
    else:
        gerenciador.limpar_senha(nome)
        DialogoMensagem(
            _janela,
            "Erro ao Destrancar",
            f"Falha ao montar '{nome}':\n{msg}",
            "erro",
        ).aguardar()


# ---------------------------------------------------------------------------
# Ação: Novo cofre
# ---------------------------------------------------------------------------

def _acao_novo_cofre():
    """Abre o wizard de criação de novo cofre."""
    from gui.dialogos import DialogoNovoCofre, DialogoMensagem

    if _janela:
        _janela.mostrar()

    dialogo = DialogoNovoCofre(_janela)
    resultado = dialogo.obter_resultado()

    if not resultado.get("sucesso"):
        return

    prov = resultado["provedor"]
    nome = resultado["nome"]
    senha = resultado["senha"]

    def _executar():
        prov_id = prov["id"]
        prov_nome = prov["nome"]
        nome_base = nome + "_base"

        if prov.get("oauth"):
            sucesso, msg = _fluxo_oauth(prov_id, nome_base)
            if not sucesso:
                _dialog_queue.put(("msg", ("Erro OAuth", msg, "erro")))
                return
        elif prov_id == "local_path":
            sucesso, msg = gerenciador.criar_remoto(
                nome_base, "local",
                {"remote": ""}
            )
            if not sucesso:
                _dialog_queue.put(("msg", ("Erro", msg, "erro")))
                return
        else:
            _dialog_queue.put(("msg", (
                "Erro",
                f"Provedor '{prov_nome}' requer configuração manual.\n"
                f"Use 'rclone config' no terminal para configurá-lo primeiro.",
                "erro"
            )))
            return

        remoto_base = nome_base + ":"
        sucesso, msg = gerenciador.criar_crypt(nome, remoto_base, senha, senha)
        if not sucesso:
            _dialog_queue.put(("msg", ("Erro", msg, "erro")))
            return

        sucesso, msg = gerenciador.adicionar_cofre(
            nome, prov_id, prov_nome, remoto_base
        )
        if sucesso:
            gerenciador.armazenar_senha(nome, senha)
            _dialog_queue.put(("msg", (
                "Sucesso",
                f"Cofre '{nome}' criado com sucesso!\n\n"
                f"Provedor: {prov_nome}\n"
                f"Remoto base: {remoto_base}\n\n"
                f"Use o botão 'Destrancar' para montar.",
                "info"
            )))
            _dialog_queue.put(("atualizar", None))
        else:
            _dialog_queue.put(("msg", ("Erro", msg, "erro")))

    threading.Thread(target=_executar, daemon=True).start()


# ---------------------------------------------------------------------------
# Ação: Importar cofre existente
# ---------------------------------------------------------------------------

def _acao_importar_cofre():
    """Abre o wizard de importação de cofre existente."""
    from gui.dialogos import DialogoImportarCofre, DialogoMensagem

    if _janela:
        _janela.mostrar()

    dialogo = DialogoImportarCofre(_janela)
    resultado = dialogo.obter_resultado()

    if not resultado.get("sucesso"):
        return

    prov = resultado["provedor"]
    nome = resultado["nome"]
    senha = resultado["senha"]
    senha2 = resultado["senha2"]

    def _executar_auth():
        """Thread: autentica no provedor e depois abre seletor de pasta."""
        prov_id = prov["id"]
        prov_nome = prov["nome"]
        nome_base = nome + "_base"

        # Para local: usa seletor nativo de pasta do Windows
        if prov_id == "local_path":
            _dialog_queue.put(("selecionar_pasta_local", (
                nome, nome_base, prov_id, prov_nome, senha, senha2
            )))
            return

        # Para cloud: criar o remoto base via OAuth
        if prov.get("oauth"):
            sucesso, msg = _fluxo_oauth(prov_id, nome_base)
            if not sucesso:
                _dialog_queue.put(("msg", ("Erro OAuth", msg, "erro")))
                return
        else:
            _dialog_queue.put(("msg", (
                "Erro",
                f"Provedor '{prov_nome}' requer configuração manual.\n"
                f"Use 'rclone config' no terminal para configurá-lo primeiro.",
                "erro"
            )))
            return

        # Auth ok → mostrar seletor de pasta remota
        _dialog_queue.put(("selecionar_pasta_remota", (
            nome, nome_base, prov_id, prov_nome, senha, senha2
        )))

    threading.Thread(target=_executar_auth, daemon=True).start()


def _mostrar_seletor_pasta_remota(nome, nome_base, prov_id, prov_nome, senha, senha2):
    """Abre o navegador de pastas do remoto já autenticado."""
    from gui.dialogos import DialogoSeletorPastaRemota, DialogoMensagem

    if _janela:
        _janela.mostrar()

    dialogo = DialogoSeletorPastaRemota(
        _janela, gerenciador, nome_base, titulo_provedor=prov_nome
    )
    caminho = dialogo.obter_resultado()

    if caminho is None:
        # Cancelou — limpar o remoto base criado
        gerenciador.remover_remoto(nome_base)
        return

    # Continuar importação em background
    def _finalizar():
        if caminho:
            caminho_limpo = caminho.strip("/")
            remoto_base = f"{nome_base}:{caminho_limpo}"
        else:
            remoto_base = f"{nome_base}:"

        sucesso, msg = gerenciador.importar_crypt(
            nome, remoto_base, senha, senha2
        )
        if not sucesso:
            _dialog_queue.put(("msg", ("Erro", msg, "erro")))
            return

        sucesso, msg = gerenciador.adicionar_cofre(
            nome, prov_id, prov_nome, remoto_base
        )
        if sucesso:
            gerenciador.armazenar_senha(nome, senha)
            _dialog_queue.put(("msg", (
                "Sucesso",
                f"Cofre '{nome}' importado com sucesso!\n\n"
                f"Provedor: {prov_nome}\n"
                f"Remoto: {remoto_base}\n\n"
                f"Use o botão 'Destrancar' para montar.",
                "info"
            )))
            _dialog_queue.put(("atualizar", None))
        else:
            _dialog_queue.put(("msg", ("Erro", msg, "erro")))

    threading.Thread(target=_finalizar, daemon=True).start()


def _mostrar_seletor_pasta_local(nome, nome_base, prov_id, prov_nome, senha, senha2):
    """Abre o seletor nativo de pasta do Windows para provedor local."""
    from gui.dialogos import DialogoMensagem
    from tkinter import filedialog

    if _janela:
        _janela.mostrar()

    pasta = filedialog.askdirectory(
        title="Selecionar pasta onde está o cofre criptografado",
        parent=_janela,
    )

    if not pasta:
        return

    def _finalizar():
        # Criar remoto local apontando para a pasta
        sucesso, msg = gerenciador.criar_remoto(
            nome_base, "local",
            {"remote": pasta}
        )
        if not sucesso:
            _dialog_queue.put(("msg", ("Erro", msg, "erro")))
            return

        remoto_base = f"{nome_base}:"

        sucesso, msg = gerenciador.importar_crypt(
            nome, remoto_base, senha, senha2
        )
        if not sucesso:
            _dialog_queue.put(("msg", ("Erro", msg, "erro")))
            return

        sucesso, msg = gerenciador.adicionar_cofre(
            nome, prov_id, prov_nome, remoto_base
        )
        if sucesso:
            gerenciador.armazenar_senha(nome, senha)
            _dialog_queue.put(("msg", (
                "Sucesso",
                f"Cofre '{nome}' importado com sucesso!\n\n"
                f"Provedor: {prov_nome}\n"
                f"Pasta: {pasta}\n\n"
                f"Use o botão 'Destrancar' para montar.",
                "info"
            )))
            _dialog_queue.put(("atualizar", None))
        else:
            _dialog_queue.put(("msg", ("Erro", msg, "erro")))

    threading.Thread(target=_finalizar, daemon=True).start()


# ---------------------------------------------------------------------------
# Ações: Config VFS, WinFsp, Sobre
# ---------------------------------------------------------------------------

def _acao_config_vfs():
    from gui.dialogos import DialogoConfigVfs
    if _janela:
        _janela.mostrar()
    DialogoConfigVfs(_janela, gerenciador)


def _acao_verificar_winfsp():
    from gui.dialogos import DialogoMensagem

    def _executar():
        info = gerenciador.verificar_winfsp()
        if info.get("instalado"):
            _dialog_queue.put(("msg", ("WinFsp", "WinFsp está instalado e funcionando.", "info")))
        else:
            _dialog_queue.put(("msg", (
                "WinFsp Ausente",
                f"WinFsp não encontrado.\n\n{info.get('motivo', '')}\n\n"
                f"Baixe em: {info.get('url_download', 'https://winfsp.dev/')}",
                "aviso"
            )))
    threading.Thread(target=_executar, daemon=True).start()


def _acao_sobre():
    from gui.dialogos import DialogoMensagem
    if _janela:
        _janela.mostrar()
    DialogoMensagem(
        _janela,
        "RuntimeCrypto",
        "RuntimeCrypto — Cofre Criptografado na Nuvem\n\n"
        "Versão 2.0\n"
        "Cryptomator-style cloud vault manager\n\n"
        "Usa RClone + Crypt para criptografia ponta-a-ponta.\n"
        "Seus arquivos são criptografados antes de enviados à nuvem\n"
        "e descriptografados instantaneamente no seu PC.\n\n"
        "Apache 2.0 — Douglas Eufrauzino de Souza",
        "info",
    ).aguardar()


# ---------------------------------------------------------------------------
# Auto-montagem
# ---------------------------------------------------------------------------

def _auto_montar_cofres():
    """Monta automaticamente cofres configurados para auto-montagem."""
    for cofre in gerenciador.listar_cofres():
        if cofre.get("auto_montar") and cofre.get("tem_senha"):
            nome = cofre["nome"]
            if not cofre.get("montado"):
                senha = gerenciador.obter_senha(nome)
                if senha:
                    gerenciador.montar_unidade(nome, letra=None, senha=senha)


# ---------------------------------------------------------------------------
# Encerramento
# ---------------------------------------------------------------------------

def _sair_aplicacao():
    """Encerra a aplicação limpamente."""
    try:
        gerenciador.desmontar_todas()
    except Exception:
        pass
    try:
        gerenciador.limpar_todas_senhas()
    except Exception:
        pass
    try:
        gerenciador.abortar_oauth()
    except Exception:
        pass
    try:
        if _icon:
            _icon.stop()
    except Exception:
        pass
    try:
        if _janela:
            _janela.destroy()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Processador de ações (thread principal / mainloop)
# ---------------------------------------------------------------------------

def _processar_acoes():
    """Processa ações da fila na thread principal (CustomTkinter)."""
    from gui.dialogos import DialogoMensagem

    try:
        while True:
            acao, dados = _dialog_queue.get_nowait()

            try:
                if acao == "cofre":
                    _acao_cofre(dados)

                elif acao == "novo_cofre":
                    _acao_novo_cofre()

                elif acao == "importar_cofre":
                    _acao_importar_cofre()

                elif acao == "selecionar_pasta_remota":
                    nome, nome_base, prov_id, prov_nome, senha, senha2 = dados
                    _mostrar_seletor_pasta_remota(
                        nome, nome_base, prov_id, prov_nome, senha, senha2
                    )

                elif acao == "selecionar_pasta_local":
                    nome, nome_base, prov_id, prov_nome, senha, senha2 = dados
                    _mostrar_seletor_pasta_local(
                        nome, nome_base, prov_id, prov_nome, senha, senha2
                    )

                elif acao == "config_vfs":
                    _acao_config_vfs()

                elif acao == "verificar_winfsp":
                    _acao_verificar_winfsp()

                elif acao == "sobre":
                    _acao_sobre()

                elif acao == "msg":
                    titulo, mensagem, tipo = dados
                    if _janela:
                        _janela.mostrar()
                    DialogoMensagem(_janela, titulo, mensagem, tipo).aguardar()

                elif acao == "atualizar":
                    _atualizar_menu_tray()
                    if _janela:
                        _janela.forcar_atualizacao()

                elif acao == "mostrar_janela":
                    if _janela:
                        _janela.mostrar()

                elif acao == "resultado_montagem":
                    nome, sucesso, msg, letra, senha = dados
                    _resultado_montagem(nome, sucesso, msg, letra, senha)

                elif acao == "auto_montar":
                    _auto_montar_cofres()

                elif acao == "sair":
                    _sair_aplicacao()

            except Exception as e:
                print(f"Erro ao processar ação '{acao}': {e}")

    except queue.Empty:
        pass

    if _janela:
        _janela.after(200, _processar_acoes)


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------

def main():
    global _icon, _janela

    from gui.janela_principal import JanelaPrincipal

    # Criar janela principal
    _janela = JanelaPrincipal(
        gerenciador,
        callback_cofre=_acao_cofre,
        callback_novo_cofre=_acao_novo_cofre,
        callback_importar_cofre=_acao_importar_cofre,
        callback_config_vfs=_acao_config_vfs,
        callback_verificar_winfsp=_acao_verificar_winfsp,
        callback_sobre=_acao_sobre,
        callback_sair=_sair_aplicacao,
    )

    # Criar tray icon
    import pystray
    imagem_tray = _gerar_icone_tray(64)

    menu_tray = pystray.Menu(
        pystray.MenuItem("Abrir RuntimeCrypto", _callback_mostrar_janela, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Sair", _callback_sair_tray),
    )

    _icon = pystray.Icon(
        "RuntimeCrypto",
        imagem_tray,
        "RuntimeCrypto",
        menu_tray,
    )

    # Agendar processamento de ações
    _janela.after(500, _processar_acoes)

    # Agendar atualização do menu tray
    _janela.after(1000, _atualizar_menu_tray)

    # Agendar auto-montagem
    _janela.after(1500, lambda: _dialog_queue.put(("auto_montar", None)))

    # Iniciar tray em thread separada
    try:
        threading.Thread(target=_icon.run, daemon=True).start()
    except Exception:
        _icon.run_detached()

    # Mainloop
    _janela.mainloop()


if __name__ == "__main__":
    main()
