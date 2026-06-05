import os
import sys
import json
import time
import queue
import threading
import webbrowser
import subprocess
from pathlib import Path

from core.rclone_manager import GerenciadorRClone, PROVEDORES, CONFIGURACOES_VFS_PADRAO

# ---------------------------------------------------------------------------
# Globais
# ---------------------------------------------------------------------------

gerenciador = GerenciadorRClone()
_dialog_queue = queue.Queue()
_icon = None
_root = None

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


def _gerar_icone_cofre(tamanho=16, cor="#10b981"):
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (tamanho, tamanho), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    m = max(1, tamanho // 8)
    corpo = (m, m * 3, m * 7, m * 7)
    draw.rounded_rectangle(corpo, radius=m, fill=cor)

    return img


def _atualizar_menu():
    """Reconstroi o menu do tray com o estado atual dos cofres."""
    import pystray
    global _icon, _root

    def _reconstruir():
        cofres = gerenciador.listar_cofres()
        montados = [c for c in cofres if c.get("montado")]
        trancados = [c for c in cofres if not c.get("montado")]

        menu_items = []

        for c in trancados:
            nome = c["nome"]
            provedor = c.get("provedor_nome", "")
            menu_items.append(pystray.MenuItem(
                f"  {nome}  [{provedor}]",
                _criar_callback_cofre(nome),
                default=False
            ))

        for c in montados:
            nome = c["nome"]
            letra = c.get("letra", "?")
            menu_items.append(pystray.MenuItem(
                f"  {nome}  ({letra}:)",
                _criar_callback_cofre(nome),
                default=False
            ))

        if menu_items:
            menu_items.append(pystray.Menu.SEPARATOR)

        menu_items.append(pystray.MenuItem(
            "Novo Cofre...",
            _callback_novo_cofre,
            default=False
        ))
        menu_items.append(pystray.Menu.SEPARATOR)

        sub_config = pystray.Menu(
            pystray.MenuItem(
                "Auto-iniciar com Windows",
                _callback_auto_iniciar,
                checked=lambda item: _verificar_auto_iniciar(),
                default=False
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Configuracoes VFS...",
                _callback_config_vfs,
                default=False
            ),
            pystray.MenuItem(
                "Verificar WinFsp",
                _callback_verificar_winfsp,
                default=False
            ),
        )

        menu_items.append(pystray.MenuItem("Configuracoes", sub_config))
        menu_items.append(pystray.Menu.SEPARATOR)
        menu_items.append(pystray.MenuItem("Sobre", _callback_sobre, default=False))
        menu_items.append(pystray.MenuItem("Sair", _callback_sair, default=False))

        _icon.menu = pystray.Menu(*menu_items)

    _root.after(0, _reconstruir)


def _criar_callback_cofre(nome):
    def callback(icon, item):
        _dialog_queue.put(("cofre", nome))
    return callback


# ---------------------------------------------------------------------------
# Dialogs (tkinter)
# ---------------------------------------------------------------------------

def _dialogo_senha(nome_cofre, acao="desbloquear"):
    """Mostra dialogo nativo para entrada de senha."""
    import tkinter as tk
    from tkinter import ttk

    resultado = {"senha": None, "confirmado": False}

    janela = tk.Toplevel(_root)
    janela.title(f"RuntimeCrypto - {acao.capitalize()} Cofre")
    janela.geometry("400x200")
    janela.resizable(False, False)
    janela.configure(bg="#0d1b2a")

    try:
        janela.iconbitmap(default="cofre.ico")
    except Exception:
        pass

    janela.transient(_root)
    janela.grab_set()

    frame = tk.Frame(janela, bg="#0d1b2a", padx=20, pady=20)
    frame.pack(fill="both", expand=True)

    tk.Label(
        frame, text=f"{acao.capitalize()} cofre: {nome_cofre}",
        font=("Segoe UI", 12, "bold"),
        fg="#10b981", bg="#0d1b2a"
    ).pack(pady=(0, 10))

    tk.Label(
        frame, text="Senha do cofre:",
        font=("Segoe UI", 9),
        fg="#8899aa", bg="#0d1b2a"
    ).pack(anchor="w")

    entry_senha = tk.Entry(
        frame, show="•", font=("Segoe UI", 11),
        bg="#1b2838", fg="#e0e0e0",
        insertbackground="#10b981",
        relief="flat", bd=0, highlightthickness=1,
        highlightbackground="#1b3a2a", highlightcolor="#10b981"
    )
    entry_senha.pack(fill="x", ipady=4, pady=(0, 15))
    entry_senha.focus_set()

    def confirmar(event=None):
        senha = entry_senha.get().strip()
        if senha:
            resultado["senha"] = senha
            resultado["confirmado"] = True
            janela.destroy()

    def cancelar():
        janela.destroy()

    btn_frame = tk.Frame(frame, bg="#0d1b2a")
    btn_frame.pack(fill="x")

    btn_cancelar = tk.Button(
        btn_frame, text="Cancelar", command=cancelar,
        bg="#1b2838", fg="#8899aa",
        font=("Segoe UI", 9),
        relief="flat", bd=0, padx=16, pady=6,
        activebackground="#2a3a4a", activeforeground="#e0e0e0",
        cursor="hand2"
    )
    btn_cancelar.pack(side="left")

    btn_ok = tk.Button(
        btn_frame, text=acao.capitalize(), command=confirmar,
        bg="#10b981", fg="#0d1b2a",
        font=("Segoe UI", 9, "bold"),
        relief="flat", bd=0, padx=24, pady=6,
        activebackground="#0d9668", activeforeground="#0d1b2a",
        cursor="hand2"
    )
    btn_ok.pack(side="right")

    entry_senha.bind("<Return>", confirmar)
    entry_senha.bind("<Escape>", lambda e: cancelar())

    janela.protocol("WM_DELETE_WINDOW", cancelar)
    janela.wait_window()

    if resultado["confirmado"]:
        return resultado["senha"]
    return None


def _dialogo_mensagem(titulo, mensagem, tipo="info"):
    """Mostra dialogo de mensagem simples."""
    import tkinter as tk

    janela = tk.Toplevel(_root)
    janela.title(titulo)
    janela.configure(bg="#0d1b2a")

    cores = {"info": "#10b981", "erro": "#ef4444", "aviso": "#f59e0b"}
    cor = cores.get(tipo, "#10b981")

    try:
        janela.iconbitmap(default="cofre.ico")
    except Exception:
        pass

    janela.transient(_root)
    janela.grab_set()

    frame = tk.Frame(janela, bg="#0d1b2a", padx=24, pady=20)
    frame.pack(fill="both", expand=True)

    tk.Label(
        frame, text=mensagem,
        font=("Segoe UI", 10),
        fg="#e0e0e0", bg="#0d1b2a",
        wraplength=350, justify="center"
    ).pack(pady=(0, 15))

    tk.Button(
        frame, text="OK", command=janela.destroy,
        bg=cor, fg="#0d1b2a",
        font=("Segoe UI", 9, "bold"),
        relief="flat", bd=0, padx=32, pady=6,
        activebackground=cor, activeforeground="#0d1b2a",
        cursor="hand2"
    ).pack()

    janela.geometry("")
    janela.resizable(False, False)
    janela.update_idletasks()

    w = max(380, janela.winfo_reqwidth())
    h = janela.winfo_reqheight()
    x = _root.winfo_x() + (_root.winfo_width() - w) // 2
    y = _root.winfo_y() + (_root.winfo_height() - h) // 2
    janela.geometry(f"{w}x{h}+{x}+{y}")

    janela.bind("<Return>", lambda e: janela.destroy())
    janela.bind("<Escape>", lambda e: janela.destroy())
    janela.protocol("WM_DELETE_WINDOW", janela.destroy)
    janela.focus_set()
    janela.wait_window()


def _dialogo_novo_cofre():
    """Wizard de criacao de novo cofre (Cryptomator-style)."""
    import tkinter as tk
    from tkinter import ttk

    resultado = {"sucesso": False, "nome": None, "senha": None}

    janela = tk.Toplevel(_root)
    janela.title("RuntimeCrypto - Novo Cofre")
    janela.geometry("480x560")
    janela.configure(bg="#0d1b2a")
    janela.resizable(False, False)

    try:
        janela.iconbitmap(default="cofre.ico")
    except:
        pass

    janela.transient(_root)
    janela.grab_set()

    frame = tk.Frame(janela, bg="#0d1b2a", padx=24, pady=20)
    frame.pack(fill="both", expand=True)

    titulo = tk.Label(
        frame, text="Criar Novo Cofre",
        font=("Segoe UI", 14, "bold"),
        fg="#10b981", bg="#0d1b2a"
    )
    titulo.pack(pady=(0, 20))

    notebook = ttk.Notebook(frame)
    notebook.pack(fill="both", expand=True)

    estilo = ttk.Style()
    estilo.theme_use("clam")
    estilo.configure("TNotebook", background="#0d1b2a", borderwidth=0)
    estilo.configure("TNotebook.Tab", background="#1b2838", foreground="#8899aa",
                     padding=[16, 6], font=("Segoe UI", 9))
    estilo.map("TNotebook.Tab", background=[("selected", "#10b981")],
               foreground=[("selected", "#0d1b2a")])

    # --- Aba 1: Provedor ---
    aba1 = tk.Frame(notebook, bg="#0d1b2a", padx=12, pady=12)
    notebook.add(aba1, text=" 1. Provedor ")

    tk.Label(
        aba1, text="Escolha o provedor de nuvem:",
        font=("Segoe UI", 10),
        fg="#e0e0e0", bg="#0d1b2a"
    ).pack(anchor="w", pady=(0, 10))

    provedor_var = tk.StringVar(value="")
    provedores_filtrados = [p for p in PROVEDORES if not p.get("local_only")]

    for prov in provedores_filtrados:
        pid = prov["id"]
        nome = prov["nome"]
        cor = prov["cor"]

        btn_frame = tk.Frame(aba1, bg="#1b2838", cursor="hand2")
        btn_frame.pack(fill="x", pady=2)

        btn_frame_inner = tk.Frame(btn_frame, bg="#1b2838")
        btn_frame_inner.pack(fill="x", padx=1, pady=1)

        indicador = tk.Label(btn_frame_inner, text="  ", bg=cor, width=3)
        indicador.pack(side="left", fill="y")

        lbl = tk.Label(
            btn_frame_inner, text=f"  {nome}",
            font=("Segoe UI", 10),
            fg="#e0e0e0", bg="#1b2838", anchor="w"
        )
        lbl.pack(side="left", fill="both", expand=True)

        for widget in [btn_frame, btn_frame_inner, lbl, indicador]:
            widget.bind("<Button-1>", lambda e, p=prov: _selecionar_provedor(
                p, provedor_var, notebook, janela, resultado
            ))
            widget.bind("<Enter>", lambda e, f=btn_frame_inner, l=lbl: (
                f.configure(bg="#2a3a4a"), l.configure(bg="#2a3a4a")
            ))
            widget.bind("<Leave>", lambda e, f=btn_frame_inner, l=lbl: (
                f.configure(bg="#1b2838"), l.configure(bg="#1b2838")
            ))

    # --- Aba 2: Senha ---
    aba2 = tk.Frame(notebook, bg="#0d1b2a", padx=12, pady=12)
    notebook.add(aba2, text=" 2. Senha ")

    tk.Label(
        aba2, text="Defina a senha do cofre:",
        font=("Segoe UI", 10),
        fg="#e0e0e0", bg="#0d1b2a"
    ).pack(anchor="w", pady=(0, 15))

    tk.Label(
        aba2, text="Senha:",
        font=("Segoe UI", 9),
        fg="#8899aa", bg="#0d1b2a"
    ).pack(anchor="w")

    entry_senha = tk.Entry(
        aba2, show="•", font=("Segoe UI", 11),
        bg="#1b2838", fg="#e0e0e0",
        insertbackground="#10b981",
        relief="flat", bd=0, highlightthickness=1,
        highlightbackground="#1b3a2a", highlightcolor="#10b981"
    )
    entry_senha.pack(fill="x", ipady=4, pady=(0, 10))

    tk.Label(
        aba2, text="Confirmar senha:",
        font=("Segoe UI", 9),
        fg="#8899aa", bg="#0d1b2a"
    ).pack(anchor="w")

    entry_senha2 = tk.Entry(
        aba2, show="•", font=("Segoe UI", 11),
        bg="#1b2838", fg="#e0e0e0",
        insertbackground="#10b981",
        relief="flat", bd=0, highlightthickness=1,
        highlightbackground="#1b3a2a", highlightcolor="#10b981"
    )
    entry_senha2.pack(fill="x", ipady=4, pady=(0, 10))

    tk.Label(
        aba2, text="Nome do cofre:",
        font=("Segoe UI", 9),
        fg="#8899aa", bg="#0d1b2a"
    ).pack(anchor="w")

    entry_nome = tk.Entry(
        aba2, font=("Segoe UI", 11),
        bg="#1b2838", fg="#e0e0e0",
        insertbackground="#10b981",
        relief="flat", bd=0, highlightthickness=1,
        highlightbackground="#1b3a2a", highlightcolor="#10b981"
    )
    entry_nome.pack(fill="x", ipady=4, pady=(0, 15))

    btn_frame2 = tk.Frame(aba2, bg="#0d1b2a")
    btn_frame2.pack(fill="x")

    tk.Button(
        btn_frame2, text="Cancelar", command=janela.destroy,
        bg="#1b2838", fg="#8899aa",
        font=("Segoe UI", 9),
        relief="flat", bd=0, padx=16, pady=6,
        activebackground="#2a3a4a", activeforeground="#e0e0e0",
        cursor="hand2"
    ).pack(side="left")

    tk.Button(
        btn_frame2, text="Criar Cofre", command=lambda: _criar_cofre_final(
            resultado, provedor_var, entry_nome, entry_senha, entry_senha2, janela
        ),
        bg="#10b981", fg="#0d1b2a",
        font=("Segoe UI", 9, "bold"),
        relief="flat", bd=0, padx=24, pady=6,
        activebackground="#0d9668", activeforeground="#0d1b2a",
        cursor="hand2"
    ).pack(side="right")

    janela.protocol("WM_DELETE_WINDOW", janela.destroy)
    notebook.select(0)
    janela.focus_set()
    janela.wait_window()

    return resultado


def _selecionar_provedor(prov, provedor_var, notebook, janela, resultado):
    provedor_var.set(prov["id"])
    resultado["provedor"] = prov
    notebook.select(1)


def _criar_cofre_final(resultado, provedor_var, entry_nome, entry_senha, entry_senha2, janela):
    prov = resultado.get("provedor")
    if not prov:
        _dialogo_mensagem("Erro", "Selecione um provedor primeiro.", "erro")
        return

    nome = entry_nome.get().strip()
    if not nome:
        _dialogo_mensagem("Erro", "Informe um nome para o cofre.", "erro")
        return

    senha = entry_senha.get().strip()
    senha2 = entry_senha2.get().strip()
    if not senha or len(senha) < 8:
        _dialogo_mensagem("Erro", "A senha deve ter pelo menos 8 caracteres.", "erro")
        return
    if senha != senha2:
        _dialogo_mensagem("Erro", "As senhas nao coincidem.", "erro")
        return

    janela.destroy()

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
                f"Provedor '{prov_nome}' requer configuracao manual.\n"
                f"Use 'rclone config' no terminal para configura-lo primeiro.",
                "erro"
            )))
            return

        remoto_base = nome_base + ":"
        sucesso, msg = gerenciador.criar_crypt(nome, remoto_base, senha, senha2)
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
                f"Use o menu do tray para desbloquear.",
                "info"
            )))
            _dialog_queue.put(("atualizar_menu", None))
        else:
            _dialog_queue.put(("msg", ("Erro", msg, "erro")))

    threading.Thread(target=_executar, daemon=True).start()


def _fluxo_oauth(tipo, nome_base):
    """Executa fluxo OAuth, abrindo o navegador, e cria o remoto base com o token."""
    gerenciador.iniciar_oauth(tipo)
    time.sleep(1)

    status = gerenciador.obter_status_oauth()
    if status["url"]:
        webbrowser.open(status["url"])
        _dialog_queue.put(("msg", (
            "Autorizacao",
            "O navegador foi aberto para autorizacao.\n"
            "Apos concluir, volte para esta janela.",
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
                    return False, "Token OAuth invalido (JSON malformado)."
                except Exception as e:
                    return False, str(e)
            return False, "Token nao encontrado na saida do rclone."

    gerenciador.abortar_oauth()
    return False, "Timeout: Autorizacao nao concluida em 2 minutos."


def _dialogo_config_vfs():
    """Dialogo para configurar parametros VFS."""
    import tkinter as tk

    janela = tk.Toplevel(_root)
    janela.title("RuntimeCrypto - Configuracoes VFS")
    janela.configure(bg="#0d1b2a")
    janela.resizable(False, False)

    try:
        janela.iconbitmap(default="cofre.ico")
    except:
        pass

    janela.transient(_root)
    janela.grab_set()

    frame = tk.Frame(janela, bg="#0d1b2a", padx=20, pady=16)
    frame.pack(fill="both", expand=True)

    tk.Label(
        frame, text="Configuracoes VFS",
        font=("Segoe UI", 12, "bold"),
        fg="#10b981", bg="#0d1b2a"
    ).pack(pady=(0, 12))

    canvas = tk.Canvas(frame, bg="#0d1b2a", highlightthickness=0, height=300)
    scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    scroll_frame = tk.Frame(canvas, bg="#0d1b2a")

    scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    cfg_atual = gerenciador.obter_configuracoes_vfs()
    entries = {}

    descricoes = {
        "vfs_cache_mode": "Modo de cache (off, minimal, writes, full)",
        "vfs_cache_max_size": "Tamanho maximo do cache em disco",
        "vfs_cache_max_age": "Tempo maximo de vida do cache",
        "vfs_read_chunk_size": "Tamanho do chunk de leitura",
        "vfs_read_chunk_size_limit": "Limite de chunk de leitura (0 = ilimitado)",
        "vfs_read_ahead": "Tamanho de read-ahead",
        "buffer_size": "Tamanho do buffer de memoria",
        "dir_cache_time": "Tempo de cache de diretorios",
        "poll_interval": "Intervalo de polling para mudancas",
    }

    for chave, valor in cfg_atual.items():
        row = tk.Frame(scroll_frame, bg="#0d1b2a", pady=2)
        row.pack(fill="x")

        tk.Label(
            row, text=chave + ":", font=("Segoe UI", 9),
            fg="#8899aa", bg="#0d1b2a", width=28, anchor="w"
        ).pack(side="left")

        entry = tk.Entry(
            row, font=("Segoe UI", 9),
            bg="#1b2838", fg="#e0e0e0",
            insertbackground="#10b981",
            relief="flat", bd=0, highlightthickness=1,
            highlightbackground="#1b3a2a", highlightcolor="#10b981",
            width=16
        )
        entry.insert(0, valor)
        entry.pack(side="left", ipady=2)
        entries[chave] = entry

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    btn_frame = tk.Frame(frame, bg="#0d1b2a", pady=(10, 0))
    btn_frame.pack(fill="x")

    tk.Button(
        btn_frame, text="Restaurar Padroes", command=lambda: _restaurar_vfs(entries, gerenciador),
        bg="#1b2838", fg="#8899aa",
        font=("Segoe UI", 9),
        relief="flat", bd=0, padx=12, pady=6,
        activebackground="#2a3a4a", activeforeground="#e0e0e0",
        cursor="hand2"
    ).pack(side="left")

    tk.Button(
        btn_frame, text="Cancelar", command=janela.destroy,
        bg="#1b2838", fg="#8899aa",
        font=("Segoe UI", 9),
        relief="flat", bd=0, padx=16, pady=6,
        activebackground="#2a3a4a", activeforeground="#e0e0e0",
        cursor="hand2"
    ).pack(side="left", padx=(6, 0))

    tk.Button(
        btn_frame, text="Salvar", command=lambda: _salvar_vfs(entries, gerenciador, janela),
        bg="#10b981", fg="#0d1b2a",
        font=("Segoe UI", 9, "bold"),
        relief="flat", bd=0, padx=24, pady=6,
        activebackground="#0d9668", activeforeground="#0d1b2a",
        cursor="hand2"
    ).pack(side="right")

    janela.bind("<Escape>", lambda e: janela.destroy())
    janela.protocol("WM_DELETE_WINDOW", janela.destroy)
    janela.update_idletasks()
    janela.geometry("500x440")
    janela.focus_set()
    janela.wait_window()


def _salvar_vfs(entries, gerenciador, janela):
    config = {chave: entry.get().strip() for chave, entry in entries.items()}
    gerenciador.atualizar_configuracoes_vfs(config)
    janela.destroy()
    _dialogo_mensagem("VFS", "Configuracoes VFS salvas com sucesso.", "info")


def _restaurar_vfs(entries, gerenciador):
    gerenciador.restaurar_configuracoes_vfs()
    cfg = gerenciador.obter_configuracoes_vfs()
    for chave, entry in entries.items():
        entry.delete(0, "end")
        entry.insert(0, cfg.get(chave, ""))


# ---------------------------------------------------------------------------
# Acoes do menu
# ---------------------------------------------------------------------------

def _callback_novo_cofre(icon, item):
    _dialog_queue.put(("novo_cofre", None))


def _callback_config_vfs(icon, item):
    _dialog_queue.put(("config_vfs", None))


def _callback_verificar_winfsp(icon, item):
    def _executar():
        info = gerenciador.verificar_winfsp()
        if info.get("instalado"):
            _dialog_queue.put(("msg", ("WinFsp", "WinFsp esta instalado e funcionando.", "info")))
        else:
            _dialog_queue.put(("msg", (
                "WinFsp Ausente",
                f"WinFsp nao encontrado.\n\n{info.get('motivo', '')}\n\n"
                f"Baixe em: {info.get('url_download', 'https://winfsp.dev/')}",
                "aviso"
            )))
    threading.Thread(target=_executar, daemon=True).start()


def _callback_sobre(icon, item):
    _dialog_queue.put(("msg", (
        "RuntimeCrypto",
        "RuntimeCrypto - Cofre Criptografado na Nuvem\n\n"
        "Versao 2.0\n"
        "Cryptomator-style cloud vault manager\n\n"
        "Usa RClone + Crypt para criptografia ponta-a-ponta.\n"
        "Seus arquivos sao criptografados antes de enviados a nuvem\n"
        "e descriptografados instantaneamente no seu PC.\n\n"
        "Apache 2.0 - Douglas Eufrauzino de Souza",
        "info"
    )))


def _callback_auto_iniciar(icon, item):
    atual = _verificar_auto_iniciar()
    if atual:
        _remover_auto_iniciar()
    else:
        _adicionar_auto_iniciar()
    _atualizar_menu()


def _callback_sair(icon, item):
    _dialog_queue.put(("sair", None))


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
        _dialog_queue.put(("msg", ("Erro", f"Erro ao configurar auto-inicio: {e}", "erro")))


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
        _dialog_queue.put(("msg", ("Erro", f"Erro ao remover auto-inicio: {e}", "erro")))


# ---------------------------------------------------------------------------
# Processador de acoes (thread principal)
# ---------------------------------------------------------------------------

def _processar_acoes():
    """Processa acoes da fila na thread principal (tkinter)."""
    try:
        while True:
            acao, dados = _dialog_queue.get_nowait()

            try:
                if acao == "cofre":
                    nome = dados
                    cofre = gerenciador.obter_cofre(nome)
                    if not cofre:
                        continue

                    if cofre.get("montado"):
                        _travar_cofre(nome)
                    else:
                        _destravar_cofre(nome)

                elif acao == "novo_cofre":
                    resultado = _dialogo_novo_cofre()
                    if resultado.get("sucesso"):
                        _atualizar_menu()

                elif acao == "config_vfs":
                    _dialogo_config_vfs()

                elif acao == "msg":
                    titulo, mensagem, tipo = dados
                    _dialogo_mensagem(titulo, mensagem, tipo)

                elif acao == "atualizar_menu":
                    _atualizar_menu()

                elif acao == "sair":
                    _sair_aplicacao()

                elif acao == "resultado_montagem":
                    nome, sucesso, msg, letra, senha = dados
                    _resultado_montagem(nome, sucesso, msg, letra, senha)

                elif acao == "auto_montar":
                    _auto_montar_cofres()

            except Exception as e:
                print(f"Erro ao processar acao '{acao}': {e}")

    except queue.Empty:
        pass

    _root.after(200, _processar_acoes)


def _destravar_cofre(nome):
    """Destranca (monta) um cofre especifico."""
    senha = gerenciador.obter_senha(nome)
    if not senha:
        senha = _dialogo_senha(nome, "desbloquear")
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
    """Tranca (desmonta) um cofre especifico."""
    letra = gerenciador.obter_letra_por_remoto(nome)
    if letra:
        sucesso, msg = gerenciador.desmontar_unidade(letra)
    else:
        sucesso, msg = gerenciador.desmontar_unidade(nome)

    gerenciador.limpar_senha(nome)
    _atualizar_menu()

    tipo = "info" if sucesso else "erro"
    _dialogo_mensagem("Cofre Trancado" if sucesso else "Erro",
                      msg, tipo)


def _resultado_montagem(nome, sucesso, msg, letra, senha):
    """Callback apos tentativa de montagem."""
    if sucesso and letra:
        subprocess.Popen(["explorer", f"{letra}:\\"],
                         creationflags=subprocess.CREATE_NO_WINDOW)
        _dialogo_mensagem(
            "Cofre Destrancado",
            f"'{nome}' montado em {letra}:\\\n\nO Explorador de Arquivos foi aberto.",
            "info"
        )
        _atualizar_menu()
    else:
        gerenciador.limpar_senha(nome)
        _dialogo_mensagem("Erro ao Destrancar",
                          f"Falha ao montar '{nome}':\n{msg}", "erro")


def _auto_montar_cofres():
    """Monta automaticamente cofres configurados para auto-montagem."""
    for cofre in gerenciador.listar_cofres():
        if cofre.get("auto_montar") and cofre.get("tem_senha"):
            nome = cofre["nome"]
            if not cofre.get("montado"):
                senha = gerenciador.obter_senha(nome)
                if senha:
                    gerenciador.montar_unidade(nome, letra=None, senha=senha)


def _sair_aplicacao():
    """Encerra a aplicacao limpamente."""
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
        if _root:
            _root.destroy()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------

def main():
    global _icon, _root

    import tkinter as tk
    import pystray

    _root = tk.Tk()
    _root.withdraw()
    _root.title("RuntimeCrypto")

    try:
        _root.iconbitmap(default="cofre.ico")
    except Exception:
        pass

    imagem_tray = _gerar_icone_tray(64)

    cofres = gerenciador.listar_cofres()
    montados = [c for c in cofres if c.get("montado")]
    trancados = [c for c in cofres if not c.get("montado")]

    menu_items = []

    if trancados:
        menu_items.append(pystray.MenuItem("--- Cofres Trancados ---", None, enabled=False))
        for c in trancados:
            menu_items.append(pystray.MenuItem(
                f"  {c['nome']}",
                _criar_callback_cofre(c["nome"]),
                default=False
            ))

    if montados:
        if menu_items:
            menu_items.append(pystray.Menu.SEPARATOR)
        menu_items.append(pystray.MenuItem("--- Cofres Destrancados ---", None, enabled=False))
        for c in montados:
            letra = c.get("letra", "?")
            menu_items.append(pystray.MenuItem(
                f"  {c['nome']}  ({letra}:)",
                _criar_callback_cofre(c["nome"]),
                default=False
            ))

    if not menu_items:
        menu_items.append(pystray.MenuItem("Nenhum cofre configurado", None, enabled=False))

    menu_items.append(pystray.Menu.SEPARATOR)
    menu_items.append(pystray.MenuItem(
        "Novo Cofre...",
        _callback_novo_cofre,
        default=True
    ))
    menu_items.append(pystray.Menu.SEPARATOR)

    sub_config = pystray.Menu(
        pystray.MenuItem(
            "Auto-iniciar com Windows",
            _callback_auto_iniciar,
            checked=lambda item: _verificar_auto_iniciar(),
            default=False
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Configuracoes VFS...",
            _callback_config_vfs,
            default=False
        ),
        pystray.MenuItem(
            "Verificar WinFsp",
            _callback_verificar_winfsp,
            default=False
        ),
    )

    menu_items.append(pystray.MenuItem("Configuracoes", sub_config))
    menu_items.append(pystray.Menu.SEPARATOR)
    menu_items.append(pystray.MenuItem("Sobre", _callback_sobre, default=False))
    menu_items.append(pystray.MenuItem("Sair", _callback_sair, default=False))

    menu = pystray.Menu(*menu_items)

    _icon = pystray.Icon(
        "RuntimeCrypto",
        imagem_tray,
        "RuntimeCrypto",
        menu
    )

    _root.after(500, _processar_acoes)
    _root.after(1500, lambda: _dialog_queue.put(("auto_montar", None)))

    try:
        threading.Thread(target=_icon.run, daemon=True).start()
    except Exception:
        _icon.run_detached()

    _root.mainloop()


if __name__ == "__main__":
    main()
