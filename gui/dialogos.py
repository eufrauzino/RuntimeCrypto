import customtkinter as ctk

from core.rclone_manager import PROVEDORES, CONFIGURACOES_VFS_PADRAO


# Paleta
_COR_BG = "#0d1b2a"
_COR_CARD = "#1b2838"
_COR_VERDE = "#10b981"
_COR_VERDE_HOVER = "#0d9668"
_COR_TEXTO = "#e0e0e0"
_COR_TEXTO_SEC = "#8899aa"
_COR_ERRO = "#ef4444"
_COR_AVISO = "#f59e0b"
_COR_ENTRY_BG = "#111d2e"
_COR_BORDA = "#1b3a2a"
_COR_BTN_SEC = "#3a4a5a"
_COR_BTN_SEC_HOVER = "#4a5a6a"


def _centralizar_janela(janela, largura, altura, pai=None):
    """Centraliza uma janela na tela ou em relação ao pai."""
    janela.update_idletasks()
    janela.minsize(max(320, largura - 60), max(200, altura - 80))
    if pai:
        try:
            x = pai.winfo_x() + (pai.winfo_width() - largura) // 2
            y = pai.winfo_y() + (pai.winfo_height() - altura) // 2
        except Exception:
            x = (janela.winfo_screenwidth() - largura) // 2
            y = (janela.winfo_screenheight() - altura) // 2
    else:
        x = (janela.winfo_screenwidth() - largura) // 2
        y = (janela.winfo_screenheight() - altura) // 2
    janela.geometry(f"{largura}x{altura}+{max(0,x)}+{max(0,y)}")


# ---------------------------------------------------------------------------
# Diálogo de Senha
# ---------------------------------------------------------------------------

class DialogoSenha(ctk.CTkToplevel):
    """Diálogo modal para entrada de senha de cofre."""

    def __init__(self, master, nome_cofre, acao="desbloquear"):
        super().__init__(master)

        self.title(f"RuntimeCrypto — {acao.capitalize()}")
        self.resizable(True, True)
        self.configure(fg_color=_COR_BG)
        self.transient(master)
        self.grab_set()

        self._resultado = None

        # Frame principal
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=28, pady=24)

        # Ícone de cadeado
        lbl_icone = ctk.CTkLabel(
            frame, text="🔐",
            font=ctk.CTkFont(size=36),
        )
        lbl_icone.pack(pady=(0, 8))

        # Título
        ctk.CTkLabel(
            frame,
            text=f"{acao.capitalize()} cofre",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=_COR_VERDE,
        ).pack(pady=(0, 2))

        ctk.CTkLabel(
            frame,
            text=nome_cofre,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=_COR_TEXTO_SEC,
        ).pack(pady=(0, 16))

        # Campo de senha
        ctk.CTkLabel(
            frame,
            text="Senha do cofre:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=_COR_TEXTO_SEC,
            anchor="w",
        ).pack(anchor="w")

        self._entry_senha = ctk.CTkEntry(
            frame,
            show="•",
            height=40,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            placeholder_text="Digite a senha...",
        )
        self._entry_senha.pack(fill="x", pady=(4, 20))
        self._entry_senha.focus_set()

        # Botões
        frame_btns = ctk.CTkFrame(frame, fg_color="transparent")
        frame_btns.pack(fill="x")

        ctk.CTkButton(
            frame_btns,
            text="Cancelar",
            width=100,
            height=36,
            fg_color=_COR_BTN_SEC,
            hover_color=_COR_BTN_SEC_HOVER,
            text_color=_COR_TEXTO,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self._cancelar,
        ).pack(side="left")

        ctk.CTkButton(
            frame_btns,
            text=acao.capitalize(),
            width=120,
            height=36,
            fg_color=_COR_VERDE,
            hover_color=_COR_VERDE_HOVER,
            text_color="#0d1b2a",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._confirmar,
        ).pack(side="right")

        # Atalhos
        self._entry_senha.bind("<Return>", lambda e: self._confirmar())
        self.bind("<Escape>", lambda e: self._cancelar())
        self.protocol("WM_DELETE_WINDOW", self._cancelar)

        _centralizar_janela(self, 400, 280, master)

    def _confirmar(self):
        senha = self._entry_senha.get().strip()
        if senha:
            self._resultado = senha
            self.grab_release()
            self.destroy()

    def _cancelar(self):
        self._resultado = None
        self.grab_release()
        self.destroy()

    def obter_resultado(self):
        self.wait_window()
        return self._resultado


# ---------------------------------------------------------------------------
# Diálogo de Mensagem
# ---------------------------------------------------------------------------

class DialogoMensagem(ctk.CTkToplevel):
    """Diálogo de mensagem (info / erro / aviso)."""

    _ICONES = {"info": "✅", "erro": "❌", "aviso": "⚠️"}
    _CORES = {"info": _COR_VERDE, "erro": _COR_ERRO, "aviso": _COR_AVISO}

    def __init__(self, master, titulo, mensagem, tipo="info"):
        super().__init__(master)

        self.title(titulo)
        self.resizable(True, True)
        self.configure(fg_color=_COR_BG)
        self.transient(master)
        self.grab_set()

        cor = self._CORES.get(tipo, _COR_VERDE)
        icone = self._ICONES.get(tipo, "ℹ️")

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=28, pady=24)

        # Ícone
        ctk.CTkLabel(
            frame, text=icone,
            font=ctk.CTkFont(size=32),
        ).pack(pady=(0, 10))

        # Título
        ctk.CTkLabel(
            frame,
            text=titulo,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=cor,
        ).pack(pady=(0, 8))

        # Mensagem
        ctk.CTkLabel(
            frame,
            text=mensagem,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=_COR_TEXTO,
            wraplength=340,
            justify="center",
        ).pack(pady=(0, 20))

        # Botão OK
        ctk.CTkButton(
            frame,
            text="OK",
            width=120,
            height=36,
            fg_color=cor,
            hover_color=cor,
            text_color="#0d1b2a" if tipo != "erro" else _COR_TEXTO,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._fechar,
        ).pack()

        self.bind("<Return>", lambda e: self._fechar())
        self.bind("<Escape>", lambda e: self._fechar())
        self.protocol("WM_DELETE_WINDOW", self._fechar)

        _centralizar_janela(self, 420, 280, master)

    def _fechar(self):
        self.grab_release()
        self.destroy()

    def aguardar(self):
        self.wait_window()


# ---------------------------------------------------------------------------
# Diálogo Novo Cofre (Wizard)
# ---------------------------------------------------------------------------

class DialogoNovoCofre(ctk.CTkToplevel):
    """Wizard de criação de novo cofre estilo Cryptomator."""

    def __init__(self, master):
        super().__init__(master)

        self.title("RuntimeCrypto — Novo Cofre")
        self.resizable(True, True)
        self.configure(fg_color=_COR_BG)
        self.transient(master)
        self.grab_set()

        self._resultado = {"sucesso": False, "provedor": None, "nome": None, "senha": None}
        self._provedor_selecionado = None

        # Frame principal
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=24, pady=20)

        # Título
        ctk.CTkLabel(
            frame, text="🔒",
            font=ctk.CTkFont(size=32),
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            frame,
            text="Criar Novo Cofre",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=_COR_VERDE,
        ).pack(pady=(0, 16))

        # Abas
        self._abas = ctk.CTkTabview(
            frame,
            corner_radius=10,
            segmented_button_fg_color=_COR_CARD,
            segmented_button_selected_color=_COR_VERDE,
            segmented_button_selected_hover_color=_COR_VERDE_HOVER,
            segmented_button_unselected_color=_COR_CARD,
            segmented_button_unselected_hover_color="#2a3a4a",
        )
        self._abas.pack(fill="both", expand=True)

        aba_provedor = self._abas.add("  1. Provedor  ")
        aba_senha = self._abas.add("  2. Senha  ")

        # --- Aba 1: Provedores ---
        ctk.CTkLabel(
            aba_provedor,
            text="Escolha o provedor de nuvem:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=_COR_TEXTO,
        ).pack(anchor="w", pady=(4, 10))

        provedores_filtrados = [p for p in PROVEDORES if not p.get("local_only")]
        self._botoes_provedor = []

        for prov in provedores_filtrados:
            frame_prov = ctk.CTkFrame(
                aba_provedor,
                fg_color=_COR_CARD,
                corner_radius=8,
                height=42,
            )
            frame_prov.pack(fill="x", pady=2)
            frame_prov.pack_propagate(False)

            # Indicador de cor
            indicador = ctk.CTkFrame(
                frame_prov,
                width=5, corner_radius=3,
                fg_color=prov["cor"],
            )
            indicador.pack(side="left", fill="y", padx=(8, 0), pady=6)

            lbl = ctk.CTkLabel(
                frame_prov,
                text=f"  {prov['nome']}",
                font=ctk.CTkFont(family="Segoe UI", size=13),
                text_color=_COR_TEXTO,
                anchor="w",
            )
            lbl.pack(side="left", fill="both", expand=True, padx=(8, 0))

            # Clique seleciona o provedor
            for widget in [frame_prov, lbl, indicador]:
                widget.bind("<Button-1>", lambda e, p=prov: self._selecionar_provedor(p))
                widget.bind("<Enter>", lambda e, f=frame_prov: f.configure(fg_color="#2a3a4a"))
                widget.bind("<Leave>", lambda e, f=frame_prov: f.configure(fg_color=_COR_CARD))

            self._botoes_provedor.append((frame_prov, prov))

        # --- Aba 2: Senha e nome ---
        ctk.CTkLabel(
            aba_senha,
            text="Defina a senha do cofre:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=_COR_TEXTO,
        ).pack(anchor="w", pady=(4, 12))

        # Senha
        ctk.CTkLabel(
            aba_senha, text="Senha:",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=_COR_TEXTO_SEC,
        ).pack(anchor="w")

        self._entry_senha = ctk.CTkEntry(
            aba_senha, show="•", height=38,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            placeholder_text="Mínimo 8 caracteres",
        )
        self._entry_senha.pack(fill="x", pady=(2, 8))

        # Confirmar senha
        ctk.CTkLabel(
            aba_senha, text="Confirmar senha:",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=_COR_TEXTO_SEC,
        ).pack(anchor="w")

        self._entry_senha2 = ctk.CTkEntry(
            aba_senha, show="•", height=38,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            placeholder_text="Repita a senha",
        )
        self._entry_senha2.pack(fill="x", pady=(2, 8))

        # Nome do cofre
        ctk.CTkLabel(
            aba_senha, text="Nome do cofre:",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=_COR_TEXTO_SEC,
        ).pack(anchor="w")

        self._entry_nome = ctk.CTkEntry(
            aba_senha, height=38,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            placeholder_text="Ex: MeusDocumentos",
        )
        self._entry_nome.pack(fill="x", pady=(2, 16))

        # Botões da aba 2
        frame_btns = ctk.CTkFrame(aba_senha, fg_color="transparent")
        frame_btns.pack(fill="x")

        ctk.CTkButton(
            frame_btns,
            text="Cancelar",
            width=100, height=36,
            fg_color=_COR_BTN_SEC,
            hover_color=_COR_BTN_SEC_HOVER,
            text_color=_COR_TEXTO,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self._cancelar,
        ).pack(side="left")

        ctk.CTkButton(
            frame_btns,
            text="Criar Cofre",
            width=120, height=36,
            fg_color=_COR_VERDE,
            hover_color=_COR_VERDE_HOVER,
            text_color="#0d1b2a",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._criar,
        ).pack(side="right")

        self.bind("<Escape>", lambda e: self._cancelar())
        self.protocol("WM_DELETE_WINDOW", self._cancelar)

        self._abas.set("  1. Provedor  ")
        _centralizar_janela(self, 500, 560, master)

    def _selecionar_provedor(self, prov):
        self._provedor_selecionado = prov
        self._resultado["provedor"] = prov
        self._abas.set("  2. Senha  ")
        self._entry_senha.focus_set()

    def _criar(self):
        if not self._provedor_selecionado:
            DialogoMensagem(self, "Erro", "Selecione um provedor primeiro.", "erro").aguardar()
            return

        nome = self._entry_nome.get().strip()
        if not nome:
            DialogoMensagem(self, "Erro", "Informe um nome para o cofre.", "erro").aguardar()
            return

        senha = self._entry_senha.get().strip()
        senha2 = self._entry_senha2.get().strip()
        if not senha or len(senha) < 8:
            DialogoMensagem(self, "Erro", "A senha deve ter pelo menos 8 caracteres.", "erro").aguardar()
            return
        if senha != senha2:
            DialogoMensagem(self, "Erro", "As senhas não coincidem.", "erro").aguardar()
            return

        self._resultado["sucesso"] = True
        self._resultado["nome"] = nome
        self._resultado["senha"] = senha
        self.grab_release()
        self.destroy()

    def _cancelar(self):
        self._resultado["sucesso"] = False
        self.grab_release()
        self.destroy()

    def obter_resultado(self):
        self.wait_window()
        return self._resultado


# ---------------------------------------------------------------------------
# Diálogo Importar Cofre Existente
# ---------------------------------------------------------------------------

class DialogoImportarCofre(ctk.CTkToplevel):
    """Wizard para importar um cofre crypt existente na nuvem."""

    def __init__(self, master):
        super().__init__(master)

        self.title("RuntimeCrypto — Importar Cofre Existente")
        self.resizable(True, True)
        self.configure(fg_color=_COR_BG)
        self.transient(master)
        self.grab_set()

        self._resultado = {
            "sucesso": False, "provedor": None, "nome": None,
            "senha": None, "senha2": None,
        }
        self._provedor_selecionado = None

        # Frame principal
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=24, pady=20)

        # Título
        ctk.CTkLabel(
            frame, text="📥",
            font=ctk.CTkFont(size=32),
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            frame,
            text="Importar Cofre Existente",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=_COR_VERDE,
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            frame,
            text="Conecte-se a um cofre criptografado já existente",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=_COR_TEXTO_SEC,
        ).pack(pady=(0, 14))

        # Abas
        self._abas = ctk.CTkTabview(
            frame,
            corner_radius=10,
            segmented_button_fg_color=_COR_CARD,
            segmented_button_selected_color=_COR_VERDE,
            segmented_button_selected_hover_color=_COR_VERDE_HOVER,
            segmented_button_unselected_color=_COR_CARD,
            segmented_button_unselected_hover_color="#2a3a4a",
        )
        self._abas.pack(fill="both", expand=True)

        aba_provedor = self._abas.add("  1. Provedor  ")
        aba_dados = self._abas.add("  2. Senhas  ")

        # --- Aba 1: Provedores ---
        ctk.CTkLabel(
            aba_provedor,
            text="Onde está o cofre existente?",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=_COR_TEXTO,
        ).pack(anchor="w", pady=(4, 10))

        for prov in PROVEDORES:
            frame_prov = ctk.CTkFrame(
                aba_provedor,
                fg_color=_COR_CARD,
                corner_radius=8,
                height=42,
            )
            frame_prov.pack(fill="x", pady=2)
            frame_prov.pack_propagate(False)

            indicador = ctk.CTkFrame(
                frame_prov,
                width=5, corner_radius=3,
                fg_color=prov["cor"],
            )
            indicador.pack(side="left", fill="y", padx=(8, 0), pady=6)

            lbl = ctk.CTkLabel(
                frame_prov,
                text=f"  {prov['nome']}",
                font=ctk.CTkFont(family="Segoe UI", size=13),
                text_color=_COR_TEXTO,
                anchor="w",
            )
            lbl.pack(side="left", fill="both", expand=True, padx=(8, 0))

            for widget in [frame_prov, lbl, indicador]:
                widget.bind("<Button-1>", lambda e, p=prov: self._selecionar_provedor(p))
                widget.bind("<Enter>", lambda e, f=frame_prov: f.configure(fg_color="#2a3a4a"))
                widget.bind("<Leave>", lambda e, f=frame_prov: f.configure(fg_color=_COR_CARD))

        # --- Aba 2: Senhas e nome ---
        ctk.CTkLabel(
            aba_dados,
            text="Informe as senhas usadas na criação do cofre:",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=_COR_TEXTO,
        ).pack(anchor="w", pady=(4, 12))

        # Senha
        ctk.CTkLabel(
            aba_dados, text="Senha do cofre (password):",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=_COR_TEXTO_SEC,
        ).pack(anchor="w")

        self._entry_senha = ctk.CTkEntry(
            aba_dados, show="•", height=38,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            placeholder_text="Senha usada na criação do cofre",
        )
        self._entry_senha.pack(fill="x", pady=(2, 8))

        # Senha2 (salt)
        ctk.CTkLabel(
            aba_dados, text="Senha 2 / salt (password2):",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=_COR_TEXTO_SEC,
        ).pack(anchor="w")

        self._entry_senha2 = ctk.CTkEntry(
            aba_dados, show="•", height=38,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            placeholder_text="Deixe vazio se igual à senha",
        )
        self._entry_senha2.pack(fill="x", pady=(2, 8))

        # Nome do cofre
        ctk.CTkLabel(
            aba_dados, text="Nome para o cofre (identificação local):",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=_COR_TEXTO_SEC,
        ).pack(anchor="w")

        self._entry_nome = ctk.CTkEntry(
            aba_dados, height=38,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            placeholder_text="Ex: MeusDocumentos",
        )
        self._entry_nome.pack(fill="x", pady=(2, 8))

        # Info
        ctk.CTkLabel(
            aba_dados,
            text="💡 Após confirmar, você selecionará a pasta\nonde o cofre está na nuvem.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=_COR_TEXTO_SEC,
            justify="left",
        ).pack(anchor="w", pady=(4, 10))

        # Botões
        frame_btns = ctk.CTkFrame(aba_dados, fg_color="transparent")
        frame_btns.pack(fill="x")

        ctk.CTkButton(
            frame_btns,
            text="Cancelar",
            width=100, height=36,
            fg_color=_COR_BTN_SEC,
            hover_color=_COR_BTN_SEC_HOVER,
            text_color=_COR_TEXTO,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self._cancelar,
        ).pack(side="left")

        ctk.CTkButton(
            frame_btns,
            text="Avançar  →",
            width=130, height=36,
            fg_color=_COR_VERDE,
            hover_color=_COR_VERDE_HOVER,
            text_color="#0d1b2a",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._avancar,
        ).pack(side="right")

        self.bind("<Escape>", lambda e: self._cancelar())
        self.protocol("WM_DELETE_WINDOW", self._cancelar)

        self._abas.set("  1. Provedor  ")
        _centralizar_janela(self, 520, 560, master)

    def _selecionar_provedor(self, prov):
        self._provedor_selecionado = prov
        self._resultado["provedor"] = prov
        self._abas.set("  2. Senhas  ")
        self._entry_senha.focus_set()

    def _avancar(self):
        if not self._provedor_selecionado:
            DialogoMensagem(self, "Erro", "Selecione um provedor primeiro.", "erro").aguardar()
            return

        nome = self._entry_nome.get().strip()
        if not nome:
            DialogoMensagem(self, "Erro", "Informe um nome para o cofre.", "erro").aguardar()
            return

        senha = self._entry_senha.get().strip()
        if not senha:
            DialogoMensagem(self, "Erro", "Informe a senha do cofre.", "erro").aguardar()
            return

        senha2 = self._entry_senha2.get().strip()
        if not senha2:
            senha2 = senha

        self._resultado["sucesso"] = True
        self._resultado["nome"] = nome
        self._resultado["senha"] = senha
        self._resultado["senha2"] = senha2
        self.grab_release()
        self.destroy()

    def _cancelar(self):
        self._resultado["sucesso"] = False
        self.grab_release()
        self.destroy()

    def obter_resultado(self):
        self.wait_window()
        return self._resultado


# ---------------------------------------------------------------------------
# Diálogo Seletor de Pasta Remota
# ---------------------------------------------------------------------------

class DialogoSeletorPastaRemota(ctk.CTkToplevel):
    """Navegador visual de pastas em um remoto rclone."""

    def __init__(self, master, gerenciador, nome_remoto, titulo_provedor=""):
        super().__init__(master)

        self.title("RuntimeCrypto — Selecionar Pasta")
        self.resizable(False, True)
        self.configure(fg_color=_COR_BG)
        self.transient(master)
        self.grab_set()

        self._gerenciador = gerenciador
        self._nome_remoto = nome_remoto
        self._caminho_atual = ""
        self._resultado = None

        # Frame principal
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=24, pady=20)

        # Título
        ctk.CTkLabel(
            frame, text="📂",
            font=ctk.CTkFont(size=28),
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            frame,
            text="Selecionar Pasta do Cofre",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=_COR_VERDE,
        ).pack(pady=(0, 2))

        if titulo_provedor:
            ctk.CTkLabel(
                frame,
                text=f"Navegando em: {titulo_provedor}",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=_COR_TEXTO_SEC,
            ).pack(pady=(0, 10))

        # Barra de caminho atual
        self._frame_caminho = ctk.CTkFrame(frame, fg_color=_COR_CARD, corner_radius=8, height=36)
        self._frame_caminho.pack(fill="x", pady=(0, 8))
        self._frame_caminho.pack_propagate(False)

        self._lbl_caminho = ctk.CTkLabel(
            self._frame_caminho,
            text=f"  {nome_remoto}/",
            font=ctk.CTkFont(family="Consolas", size=12),
            text_color=_COR_TEXTO,
            anchor="w",
        )
        self._lbl_caminho.pack(side="left", fill="both", expand=True, padx=8)

        # Botão voltar
        self._btn_voltar = ctk.CTkButton(
            self._frame_caminho,
            text="⬆",
            width=36, height=28,
            fg_color=_COR_BTN_SEC,
            hover_color=_COR_BTN_SEC_HOVER,
            text_color=_COR_TEXTO,
            font=ctk.CTkFont(size=14),
            command=self._voltar,
        )
        self._btn_voltar.pack(side="right", padx=4, pady=4)

        # Lista de pastas
        self._frame_lista = ctk.CTkScrollableFrame(
            frame,
            fg_color=_COR_CARD,
            corner_radius=10,
            height=280,
        )
        self._frame_lista.pack(fill="both", expand=True)

        # Status / carregando
        self._lbl_status = ctk.CTkLabel(
            self._frame_lista,
            text="🔄 Carregando pastas...",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=_COR_TEXTO_SEC,
        )

        # Dica
        ctk.CTkLabel(
            frame,
            text="💡 Clique duas vezes para entrar em uma pasta.\n"
                 "Clique 'Selecionar esta pasta' para usar a pasta atual.",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=_COR_TEXTO_SEC,
            justify="left",
        ).pack(anchor="w", pady=(8, 8))

        # Botões
        frame_btns = ctk.CTkFrame(frame, fg_color="transparent")
        frame_btns.pack(fill="x")

        ctk.CTkButton(
            frame_btns,
            text="Cancelar",
            width=100, height=36,
            fg_color=_COR_BTN_SEC,
            hover_color=_COR_BTN_SEC_HOVER,
            text_color=_COR_TEXTO,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            command=self._cancelar,
        ).pack(side="left")

        ctk.CTkButton(
            frame_btns,
            text="✓  Selecionar esta pasta",
            width=180, height=36,
            fg_color=_COR_VERDE,
            hover_color=_COR_VERDE_HOVER,
            text_color="#0d1b2a",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._selecionar,
        ).pack(side="right")

        self.bind("<Escape>", lambda e: self._cancelar())
        self.protocol("WM_DELETE_WINDOW", self._cancelar)

        _centralizar_janela(self, 520, 540, master)

        # Carregar pastas iniciais
        self.after(100, self._carregar_pastas)

    def _carregar_pastas(self):
        """Carrega a listagem de pastas do caminho atual."""
        # Limpar lista
        for widget in self._frame_lista.winfo_children():
            widget.destroy()

        # Mostrar status
        self._lbl_status = ctk.CTkLabel(
            self._frame_lista,
            text="🔄 Carregando pastas...",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=_COR_TEXTO_SEC,
        )
        self._lbl_status.pack(pady=20)

        # Atualizar label do caminho
        caminho_display = self._caminho_atual if self._caminho_atual else "/"
        self._lbl_caminho.configure(text=f"  {self._nome_remoto}:{caminho_display}")

        # Carregar em thread (pode demorar para nuvem)
        import threading
        def _carregar():
            dirs = self._gerenciador.listar_diretorios_remoto(
                self._nome_remoto, self._caminho_atual
            )
            self.after(0, lambda: self._exibir_pastas(dirs))

        threading.Thread(target=_carregar, daemon=True).start()

    def _exibir_pastas(self, dirs):
        """Exibe a lista de pastas na UI."""
        # Limpar
        for widget in self._frame_lista.winfo_children():
            widget.destroy()

        if not dirs:
            ctk.CTkLabel(
                self._frame_lista,
                text="📁 Nenhuma subpasta encontrada.\n\nVocê pode selecionar esta pasta.",
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=_COR_TEXTO_SEC,
                justify="center",
            ).pack(pady=30)
            return

        for nome_pasta in dirs:
            frame_item = ctk.CTkFrame(
                self._frame_lista,
                fg_color="transparent",
                corner_radius=6,
                height=38,
            )
            frame_item.pack(fill="x", padx=4, pady=1)
            frame_item.pack_propagate(False)

            lbl_icone = ctk.CTkLabel(
                frame_item,
                text="📁",
                font=ctk.CTkFont(size=14),
                width=28,
            )
            lbl_icone.pack(side="left", padx=(8, 0))

            lbl_nome = ctk.CTkLabel(
                frame_item,
                text=nome_pasta,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=_COR_TEXTO,
                anchor="w",
            )
            lbl_nome.pack(side="left", fill="both", expand=True, padx=(4, 0))

            lbl_seta = ctk.CTkLabel(
                frame_item,
                text="→",
                font=ctk.CTkFont(size=12),
                text_color=_COR_TEXTO_SEC,
                width=24,
            )
            lbl_seta.pack(side="right", padx=(0, 8))

            # Duplo clique para entrar na pasta
            for widget in [frame_item, lbl_icone, lbl_nome, lbl_seta]:
                widget.bind("<Double-Button-1>", lambda e, p=nome_pasta: self._entrar_pasta(p))
                widget.bind("<Enter>", lambda e, f=frame_item: f.configure(fg_color="#2a3a4a"))
                widget.bind("<Leave>", lambda e, f=frame_item: f.configure(fg_color="transparent"))

    def _entrar_pasta(self, nome_pasta):
        """Navega para uma subpasta."""
        if self._caminho_atual:
            self._caminho_atual = self._caminho_atual.rstrip("/") + "/" + nome_pasta
        else:
            self._caminho_atual = nome_pasta
        self._carregar_pastas()

    def _voltar(self):
        """Volta para a pasta pai."""
        if not self._caminho_atual:
            return
        partes = self._caminho_atual.rstrip("/").split("/")
        if len(partes) <= 1:
            self._caminho_atual = ""
        else:
            self._caminho_atual = "/".join(partes[:-1])
        self._carregar_pastas()

    def _selecionar(self):
        """Confirma a seleção da pasta atual."""
        self._resultado = self._caminho_atual
        self.grab_release()
        self.destroy()

    def _cancelar(self):
        self._resultado = None
        self.grab_release()
        self.destroy()

    def obter_resultado(self):
        self.wait_window()
        return self._resultado


# ---------------------------------------------------------------------------
# Diálogo Configurações VFS
# ---------------------------------------------------------------------------

class DialogoConfigVfs(ctk.CTkToplevel):
    """Diálogo para configurar parâmetros VFS."""

    _DESCRICOES = {
        "vfs_cache_mode": "Modo de cache (off, minimal, writes, full)",
        "vfs_cache_max_size": "Tamanho máximo do cache em disco",
        "vfs_cache_max_age": "Tempo máximo de vida do cache",
        "vfs_read_chunk_size": "Tamanho do chunk de leitura",
        "vfs_read_chunk_size_limit": "Limite de chunk (0 = ilimitado)",
        "vfs_read_ahead": "Tamanho de read-ahead",
        "buffer_size": "Tamanho do buffer de memória",
        "dir_cache_time": "Tempo de cache de diretórios",
        "poll_interval": "Intervalo de polling para mudanças",
        "attr_timeout": "Cache de atributos (evita consultas repetidas)",
        "vfs_write_back": "Atraso antes de enviar arquivo à nuvem",
        "vfs_disk_space_total_size": "Tamanho total virtual da unidade",
        "cache_dir": "Pasta local para cache VFS (SSD recomendado)",
    }

    def __init__(self, master, gerenciador):
        super().__init__(master)

        self.title("RuntimeCrypto — Configurações VFS")
        self.resizable(True, True)
        self.configure(fg_color=_COR_BG)
        self.transient(master)
        self.grab_set()

        self._gerenciador = gerenciador
        self._entries = {}

        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=24, pady=20)

        # Título
        ctk.CTkLabel(
            frame, text="⚙️",
            font=ctk.CTkFont(size=28),
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            frame,
            text="Configurações VFS",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=_COR_VERDE,
        ).pack(pady=(0, 4))

        ctk.CTkLabel(
            frame,
            text="Ajustes de cache e streaming do RClone",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=_COR_TEXTO_SEC,
        ).pack(pady=(0, 14))

        # ScrollableFrame para os campos
        scroll = ctk.CTkScrollableFrame(
            frame,
            fg_color=_COR_CARD,
            corner_radius=10,
            height=260,
        )
        scroll.pack(fill="both", expand=True)

        cfg_atual = gerenciador.obter_configuracoes_vfs()

        for chave, valor in cfg_atual.items():
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=3)

            desc = self._DESCRICOES.get(chave, chave)

            ctk.CTkLabel(
                row,
                text=desc,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=_COR_TEXTO_SEC,
                anchor="w",
                width=220,
            ).pack(side="left")

            entry = ctk.CTkEntry(
                row,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                height=30,
                width=130,
            )
            entry.insert(0, valor)
            entry.pack(side="right")
            self._entries[chave] = entry

        # Botões
        frame_btns = ctk.CTkFrame(frame, fg_color="transparent")
        frame_btns.pack(fill="x", pady=(12, 0))

        ctk.CTkButton(
            frame_btns,
            text="Restaurar Padrões",
            width=130, height=34,
            fg_color=_COR_BTN_SEC,
            hover_color=_COR_BTN_SEC_HOVER,
            text_color=_COR_TEXTO,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._restaurar,
        ).pack(side="left")

        ctk.CTkButton(
            frame_btns,
            text="Cancelar",
            width=90, height=34,
            fg_color=_COR_BTN_SEC,
            hover_color=_COR_BTN_SEC_HOVER,
            text_color=_COR_TEXTO,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._cancelar,
        ).pack(side="left", padx=(6, 0))

        ctk.CTkButton(
            frame_btns,
            text="Salvar",
            width=100, height=34,
            fg_color=_COR_VERDE,
            hover_color=_COR_VERDE_HOVER,
            text_color="#0d1b2a",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            command=self._salvar,
        ).pack(side="right")

        self.bind("<Escape>", lambda e: self._cancelar())
        self.protocol("WM_DELETE_WINDOW", self._cancelar)

        _centralizar_janela(self, 520, 500, master)

    def _salvar(self):
        config = {chave: entry.get().strip() for chave, entry in self._entries.items()}
        self._gerenciador.atualizar_configuracoes_vfs(config)
        self.grab_release()
        self.destroy()
        DialogoMensagem(
            self.master, "VFS", "Configurações VFS salvas com sucesso.", "info"
        ).aguardar()

    def _restaurar(self):
        self._gerenciador.restaurar_configuracoes_vfs()
        cfg = self._gerenciador.obter_configuracoes_vfs()
        for chave, entry in self._entries.items():
            entry.delete(0, "end")
            entry.insert(0, cfg.get(chave, ""))

    def _cancelar(self):
        self.grab_release()
        self.destroy()
