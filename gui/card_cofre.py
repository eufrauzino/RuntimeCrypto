import customtkinter as ctk


# Cores dos provedores
_CORES_PROVEDORES = {
    "drive": "#34A853",
    "onedrive": "#0078D4",
    "dropbox": "#0061FF",
    "s3": "#FF9900",
    "local_path": "#10b981",
}

_COR_MONTADO = "#10b981"
_COR_TRANCADO = "#ef4444"
_COR_FUNDO = "#1b2838"
_COR_FUNDO_HOVER = "#223344"
_COR_TEXTO = "#e0e0e0"
_COR_TEXTO_SEC = "#8899aa"


class CardCofre(ctk.CTkFrame):
    """Card visual representando um cofre."""

    def __init__(self, master, cofre: dict, callback_acao=None, **kwargs):
        super().__init__(
            master,
            corner_radius=10,
            fg_color=_COR_FUNDO,
            border_width=1,
            border_color="#1b3a2a",
            height=76,
            **kwargs,
        )
        self.pack_propagate(False)

        self._cofre = cofre
        self._callback_acao = callback_acao

        nome = cofre.get("nome", "Cofre")
        provedor_id = cofre.get("provedor_id", "local_path")
        provedor_nome = cofre.get("provedor_nome", "Local")
        montado = cofre.get("montado", False)
        letra = cofre.get("letra")

        cor_provedor = _CORES_PROVEDORES.get(provedor_id, "#10b981")

        # Layout com grid: [indicador] [info] [botão]
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Coluna 0: Indicador vertical colorido do provedor
        indicador = ctk.CTkFrame(
            self,
            width=4,
            corner_radius=2,
            fg_color=cor_provedor,
        )
        indicador.grid(row=0, column=0, sticky="ns", padx=(10, 0), pady=12)

        # Coluna 1: Info (nome + provedor + status)
        frame_info = ctk.CTkFrame(self, fg_color="transparent")
        frame_info.grid(row=0, column=1, sticky="nsew", padx=(10, 8), pady=10)

        ctk.CTkLabel(
            frame_info,
            text=nome,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=_COR_TEXTO,
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            frame_info,
            text=provedor_nome,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=_COR_TEXTO_SEC,
            anchor="w",
        ).pack(anchor="w")

        # Status
        if montado:
            texto_status = f"● Destrancado  •  {letra}:\\" if letra else "● Destrancado"
            cor_status = _COR_MONTADO
        else:
            texto_status = "● Trancado"
            cor_status = _COR_TRANCADO

        ctk.CTkLabel(
            frame_info,
            text=texto_status,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=cor_status,
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        # Coluna 2: Botão
        if montado:
            texto_btn = "Trancar"
            cor_btn = "#3a4a5a"
            cor_btn_hover = "#4a5a6a"
            cor_texto_btn = _COR_TEXTO
        else:
            texto_btn = "Destrancar"
            cor_btn = "#10b981"
            cor_btn_hover = "#0d9668"
            cor_texto_btn = "#0d1b2a"

        btn_acao = ctk.CTkButton(
            self,
            text=texto_btn,
            width=100,
            height=34,
            corner_radius=8,
            fg_color=cor_btn,
            hover_color=cor_btn_hover,
            text_color=cor_texto_btn,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._ao_clicar,
        )
        btn_acao.grid(row=0, column=2, padx=(0, 12), pady=10)

        # Hover no card inteiro
        self.bind("<Enter>", self._ao_entrar)
        self.bind("<Leave>", self._ao_sair)

    def _ao_clicar(self):
        if self._callback_acao:
            self._callback_acao(self._cofre)

    def _ao_entrar(self, evento=None):
        self.configure(fg_color=_COR_FUNDO_HOVER)

    def _ao_sair(self, evento=None):
        self.configure(fg_color=_COR_FUNDO)

    @property
    def cofre(self):
        return self._cofre


class BotaoNovoCofre(ctk.CTkButton):
    """Botão estilizado para adicionar novo cofre."""

    def __init__(self, master, command=None, **kwargs):
        super().__init__(
            master,
            text="＋  Adicionar Cofre",
            height=50,
            corner_radius=10,
            fg_color="transparent",
            hover_color="#152232",
            border_width=2,
            border_color="#1b3a2a",
            text_color="#8899aa",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            command=command,
            **kwargs,
        )
