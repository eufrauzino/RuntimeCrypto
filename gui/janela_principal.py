import os
import customtkinter as ctk

from gui.card_cofre import CardCofre, BotaoNovoCofre


# Paleta
_COR_BG = "#0d1b2a"
_COR_CARD = "#1b2838"
_COR_VERDE = "#10b981"
_COR_TEXTO = "#e0e0e0"
_COR_TEXTO_SEC = "#8899aa"
_COR_BTN_SEC = "#3a4a5a"
_COR_BTN_SEC_HOVER = "#4a5a6a"
_VERSAO = "2.0"


class JanelaPrincipal(ctk.CTk):
    """Janela principal do RuntimeCrypto estilo Cryptomator."""

    def __init__(
        self,
        gerenciador,
        callback_cofre=None,
        callback_novo_cofre=None,
        callback_importar_cofre=None,
        callback_config_vfs=None,
        callback_verificar_winfsp=None,
        callback_sobre=None,
        callback_sair=None,
    ):
        # Tema
        caminho_tema = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "tema_runtime.json",
        )
        if os.path.exists(caminho_tema):
            ctk.set_default_color_theme(caminho_tema)
        ctk.set_appearance_mode("dark")

        super().__init__()

        self._gerenciador = gerenciador
        self._callback_cofre = callback_cofre
        self._callback_novo_cofre = callback_novo_cofre
        self._callback_importar_cofre = callback_importar_cofre
        self._callback_config_vfs = callback_config_vfs
        self._callback_verificar_winfsp = callback_verificar_winfsp
        self._callback_sobre = callback_sobre
        self._callback_sair = callback_sair
        self._cards = {}
        self._estado_anterior = {}
        self._visivel = True

        # Janela
        self.title("RuntimeCrypto")
        self.geometry("520x640")
        self.minsize(400, 400)
        self.configure(fg_color=_COR_BG)

        # Layout responsivo com grid
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        try:
            self.iconbitmap(default="cofre.ico")
        except Exception:
            pass

        # Fechar (X) = esconder pro tray
        self.protocol("WM_DELETE_WINDOW", self.esconder)

        self._construir_interface()

        # Atualização periódica dos cards
        self._agendar_atualizacao()

    def _construir_interface(self):
        """Constroi toda a interface da janela principal."""

        # ===================== HEADER =====================
        frame_header = ctk.CTkFrame(
            self, fg_color=_COR_CARD, corner_radius=0, height=72
        )
        frame_header.grid(row=0, column=0, sticky="ew")
        frame_header.grid_propagate(False)
        frame_header.grid_columnconfigure(0, weight=1)

        frame_header_inner = ctk.CTkFrame(frame_header, fg_color="transparent")
        frame_header_inner.grid(row=0, column=0, sticky="nsew", padx=20)
        frame_header_inner.grid_rowconfigure(0, weight=1)

        # Logo + Titulo
        frame_titulo = ctk.CTkFrame(frame_header_inner, fg_color="transparent")
        frame_titulo.pack(side="left", fill="y", pady=10)

        ctk.CTkLabel(
            frame_titulo,
            text="🔒",
            font=ctk.CTkFont(size=26),
        ).pack(side="left", padx=(0, 10))

        frame_textos = ctk.CTkFrame(frame_titulo, fg_color="transparent")
        frame_textos.pack(side="left")

        ctk.CTkLabel(
            frame_textos,
            text="RuntimeCrypto",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=_COR_VERDE,
        ).pack(anchor="w")

        ctk.CTkLabel(
            frame_textos,
            text=f"Cofre Criptografado na Nuvem  •  v{_VERSAO}",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=_COR_TEXTO_SEC,
        ).pack(anchor="w")

        # ===================== AREA CENTRAL =====================
        self._frame_cofres = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
        )
        self._frame_cofres.grid(
            row=1, column=0, sticky="nsew", padx=12, pady=(10, 6)
        )
        self._frame_cofres.grid_columnconfigure(0, weight=1)

        # Mensagem quando não há cofres
        self._lbl_vazio = ctk.CTkLabel(
            self._frame_cofres,
            text="Nenhum cofre configurado.\n\nClique em '＋ Adicionar Cofre' para começar.",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=_COR_TEXTO_SEC,
            justify="center",
        )

        # Botão de adicionar cofre
        self._btn_novo = BotaoNovoCofre(
            self._frame_cofres,
            command=self._ao_novo_cofre,
        )

        # Botão de importar cofre existente
        self._btn_importar = ctk.CTkButton(
            self._frame_cofres,
            text="📥  Importar Cofre Existente",
            height=42,
            corner_radius=10,
            fg_color="transparent",
            hover_color="#152232",
            border_width=1,
            border_color="#1b3a2a",
            text_color="#8899aa",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            command=self._ao_importar_cofre,
        )

        # ===================== FOOTER =====================
        frame_footer = ctk.CTkFrame(
            self, fg_color=_COR_CARD, corner_radius=0, height=46
        )
        frame_footer.grid(row=2, column=0, sticky="ew")
        frame_footer.grid_propagate(False)
        frame_footer.grid_columnconfigure(0, weight=1)

        frame_footer_inner = ctk.CTkFrame(frame_footer, fg_color="transparent")
        frame_footer_inner.grid(row=0, column=0, sticky="nsew", padx=12)
        frame_footer_inner.grid_rowconfigure(0, weight=1)

        # Botões do footer
        ctk.CTkButton(
            frame_footer_inner,
            text="⚙  Configurações",
            width=120, height=30,
            fg_color="transparent",
            hover_color="#2a3a4a",
            text_color=_COR_TEXTO_SEC,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._ao_config,
        ).pack(side="left", pady=8)

        ctk.CTkButton(
            frame_footer_inner,
            text="ℹ  Sobre",
            width=70, height=30,
            fg_color="transparent",
            hover_color="#2a3a4a",
            text_color=_COR_TEXTO_SEC,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._ao_sobre,
        ).pack(side="left", padx=(4, 0), pady=8)

        ctk.CTkButton(
            frame_footer_inner,
            text="✕  Sair",
            width=60, height=30,
            fg_color="transparent",
            hover_color="#3a2020",
            text_color="#ef4444",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            command=self._ao_sair,
        ).pack(side="right", pady=8)

        # Primeira renderização
        self._atualizar_cofres()

    # ==================== ATUALIZAÇÃO INTELIGENTE ====================

    def _gerar_estado_cofres(self):
        """Gera snapshot do estado atual dos cofres para comparação."""
        cofres = self._gerenciador.listar_cofres()
        estado = {}
        for c in cofres:
            nome = c.get("nome", "?")
            estado[nome] = {
                "montado": c.get("montado", False),
                "letra": c.get("letra"),
                "provedor_id": c.get("provedor_id", ""),
                "provedor_nome": c.get("provedor_nome", ""),
            }
        return cofres, estado

    def _atualizar_cofres(self):
        """Atualiza os cards. Reconstroi apenas se houver mudanças."""
        cofres, estado_novo = self._gerar_estado_cofres()

        # Se o estado não mudou, não reconstroi
        if estado_novo == self._estado_anterior and self._cards:
            return

        self._estado_anterior = estado_novo

        # Limpar cards antigos
        for card in self._cards.values():
            card.destroy()
        self._cards.clear()

        self._lbl_vazio.pack_forget()
        self._btn_novo.pack_forget()
        self._btn_importar.pack_forget()

        if not cofres:
            self._lbl_vazio.pack(pady=(40, 20))
        else:
            for cofre in cofres:
                nome = cofre.get("nome", "?")
                card = CardCofre(
                    self._frame_cofres,
                    cofre,
                    callback_acao=self._ao_clicar_cofre,
                )
                card.pack(fill="x", pady=3)
                self._cards[nome] = card

        # Botões sempre no final
        self._btn_novo.pack(fill="x", pady=(8, 3))
        self._btn_importar.pack(fill="x", pady=(2, 4))

    def _agendar_atualizacao(self):
        """Agenda atualização periódica dos cards (3s)."""
        if self._visivel:
            try:
                self._atualizar_cofres()
            except Exception:
                pass
        self.after(3000, self._agendar_atualizacao)

    # ==================== CALLBACKS ====================

    def _ao_clicar_cofre(self, cofre):
        if self._callback_cofre:
            self._callback_cofre(cofre)

    def _ao_novo_cofre(self):
        if self._callback_novo_cofre:
            self._callback_novo_cofre()

    def _ao_importar_cofre(self):
        if self._callback_importar_cofre:
            self._callback_importar_cofre()

    def _ao_config(self):
        if self._callback_config_vfs:
            self._callback_config_vfs()

    def _ao_sobre(self):
        if self._callback_sobre:
            self._callback_sobre()

    def _ao_sair(self):
        if self._callback_sair:
            self._callback_sair()

    # ==================== MOSTRAR / ESCONDER ====================

    def mostrar(self):
        """Traz a janela para frente."""
        self._visivel = True
        self.deiconify()
        self.lift()
        self.focus_force()
        self.forcar_atualizacao()

    def esconder(self):
        """Esconde a janela (minimiza pro tray)."""
        self._visivel = False
        self.withdraw()

    def forcar_atualizacao(self):
        """Força reconstrução imediata dos cards."""
        self._estado_anterior = {}
        self._atualizar_cofres()
