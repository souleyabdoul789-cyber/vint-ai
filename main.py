"""
╔══════════════════════════════════════════════════════╗
║              VINT-AI  —  Interface KivyMD            ║
║      Bulles de chat + Menu historique + Mémoire      ║
╚══════════════════════════════════════════════════════╝

Dépendances :
    pip install kivy kivymd openai

Lancement :
    python vint_ai.py
"""
import certifi
import os, json, threading
from datetime import datetime
from openai import OpenAI

# ── KivyMD ────────────────────────────────────────────────────────────────────
from kivy.lang import Builder
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp, sp

from kivymd.app import MDApp
from kivymd.uix.label import MDLabel
from kivymd.uix.card import MDCard
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDIconButton, MDFlatButton
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.navigationdrawer import (
    MDNavigationDrawer, MDNavigationDrawerHeader,
    MDNavigationDrawerItem, MDNavigationDrawerDivider,
    MDNavigationDrawerMenu
)
from kivymd.uix.dialog import MDDialog
from kivymd.uix.list import MDList, TwoLineListItem
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.screen import MDScreen
from kivymd.uix.screenmanager import MDScreenManager

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
MODEL_NAME   = "openai/gpt-oss-120b"
MEMORY_FILE  = "memory.json"
MAX_HISTORY  = 20
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['PYTHONOPTIMIZE'] = '2'

SYSTEM_RULES = """Tu es Vint-AI, un assistant expert en programmation Python et cybersécurité.

RÈGLES DE COMPORTEMENT :
1. Réponds toujours en français sauf si l'utilisateur écrit dans une autre langue.
2. Sois précis, professionnel et concis dans tes réponses.
3. Pour tout code, utilise des blocs formatés avec des commentaires clairs.
4. En cybersécurité, ne fournis jamais d'aide pour des activités illégales ou malveillantes.
5. Si tu ne connais pas la réponse, dis-le clairement plutôt que d'inventer.
6. Fais référence aux échanges précédents si pertinent pour enrichir tes réponses.
7. Adopte un ton professionnel mais accessible.
8. Propose toujours des ressources ou étapes suivantes à la fin de tes réponses complexes.
9. Respecte la confidentialité des informations partagées par l'utilisateur.
"""

# ─── COULEURS ─────────────────────────────────────────────────────────────────
COLOR_USER_BUBBLE = (0.45, 0.24, 0.10, 1)   # marron
COLOR_AI_BUBBLE   = (0.10, 0.10, 0.10, 1)   # noir
COLOR_BG          = (0.07, 0.07, 0.07, 1)   # fond très sombre
COLOR_TOOLBAR     = (0.13, 0.07, 0.02, 1)   # marron foncé toolbar
COLOR_INPUT_BG    = (0.14, 0.14, 0.14, 1)

# ─── GESTION MÉMOIRE ──────────────────────────────────────────────────────────

def load_memory() -> dict:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "user_info": {"name": None},
        "conversation_history": [],
        "sessions": [],
        "session_count": 0,
        "last_session": None
    }

def save_memory(memory: dict):
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"[⚠] Sauvegarde échouée : {e}")

def add_to_history(memory: dict, role: str, content: str):
    memory["conversation_history"].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    })
    if len(memory["conversation_history"]) > MAX_HISTORY * 2:
        memory["conversation_history"] = memory["conversation_history"][-(MAX_HISTORY * 2):]

# ─── CLIENT GROQ ──────────────────────────────────────────────────────────────

def build_api_messages(history: list) -> list:
    msgs = [{"role": "system", "content": SYSTEM_RULES}]
    for e in history:
        msgs.append({"role": e["role"], "content": e["content"]})
    return msgs

def ask_groq(history: list) -> str:
    client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
    try:
        r = client.chat.completions.create(
            model=MODEL_NAME,
            messages=build_api_messages(history),
            temperature=0.7,
            max_tokens=2048
        )
        return r.choices[0].message.content
    except Exception as e:
        return f"❌ Erreur : {str(e)}"

# ─── WIDGETS ──────────────────────────────────────────────────────────────────

def make_bubble(text: str, is_user: bool) -> MDBoxLayout:
    """Crée une bulle de message avec la méthode Builder (sans KV file)."""
    # Conteneur aligné gauche ou droite
    row = MDBoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        padding=[dp(8), dp(4)],
        spacing=dp(6),
    )

    # Carte bulle
    card = MDCard(
        orientation="vertical",
        size_hint=(None, None),
        md_bg_color=COLOR_USER_BUBBLE if is_user else COLOR_AI_BUBBLE,
        radius=[dp(18), dp(18), dp(4) if is_user else dp(18), dp(18) if is_user else dp(4)],
        padding=[dp(14), dp(10)],
        elevation=2,
    )

    label = MDLabel(
        text=text,
        theme_text_color="Custom",
        text_color=(1, 1, 1, 1),
        font_size=sp(16),
        size_hint=(None, None),
        width=dp(280),
        halign="left",
        valign="top",
    )
    label.bind(texture_size=lambda inst, val: setattr(inst, 'height', val[1]))
    label.text_size = (dp(270), None)

    card.add_widget(label)
    card.bind(
        minimum_height=card.setter('height'),
        minimum_width=card.setter('width'),
    )

    # Timestamp
    ts = MDLabel(
        text=datetime.now().strftime("%H:%M"),
        theme_text_color="Custom",
        text_color=(0.6, 0.6, 0.6, 1),
        font_size=sp(11),
        size_hint=(None, None),
        width=dp(38),
        height=dp(20),
        halign="center",
        valign="bottom",
    )

    if is_user:
        row.add_widget(MDBoxLayout(size_hint_x=1))   # pousse à droite
        row.add_widget(card)
        row.add_widget(ts)
    else:
        row.add_widget(ts)
        row.add_widget(card)
        row.add_widget(MDBoxLayout(size_hint_x=1))   # pousse à gauche

    row.bind(minimum_height=row.setter('height'))
    return row


def make_typing_indicator() -> MDCard:
    """Indicateur 'Vint-AI écrit...'"""
    card = MDCard(
        orientation="vertical",
        size_hint=(None, None),
        md_bg_color=COLOR_AI_BUBBLE,
        radius=[dp(18), dp(18), dp(18), dp(4)],
        padding=[dp(14), dp(10)],
        elevation=2,
        width=dp(160),
        height=dp(44),
    )
    label = MDLabel(
        text="⏳  Vint-AI écrit…",
        theme_text_color="Custom",
        text_color=(0.7, 0.7, 0.7, 1),
        font_size=sp(15),
        size_hint=(1, 1),
    )
    card.add_widget(label)

    row = MDBoxLayout(
        orientation="horizontal",
        size_hint_y=None,
        height=dp(52),
        padding=[dp(8), dp(4)],
    )
    row.add_widget(card)
    row.add_widget(MDBoxLayout(size_hint_x=1))
    return row

# ─── ÉCRAN HISTORIQUE ─────────────────────────────────────────────────────────

class HistoryScreen(MDScreen):
    def __init__(self, memory_ref, on_load_session, **kwargs):
        super().__init__(**kwargs)
        self.name = "history"
        self.memory_ref = memory_ref
        self.on_load_session = on_load_session
        self._build()

    def _build(self):
        layout = MDBoxLayout(orientation="vertical")

        # Toolbar
        toolbar = MDTopAppBar(
            title="Historique",
            md_bg_color=COLOR_TOOLBAR,
            specific_text_color=(1, 1, 1, 1),
        )
        toolbar.left_action_items = [["arrow-left", lambda x: self._go_back()]]
        layout.add_widget(toolbar)

        # Liste des sessions
        scroll = MDScrollView()
        self.list_widget = MDList()
        scroll.add_widget(self.list_widget)
        layout.add_widget(scroll)
        self.add_widget(layout)

    def _go_back(self):
        self.manager.current = "chat"

    def refresh(self):
        self.list_widget.clear_widgets()
        sessions = self.memory_ref.get("sessions", [])
        if not sessions:
            item = TwoLineListItem(
                text="Aucune session sauvegardée",
                secondary_text="Lance une conversation !",
            )
            self.list_widget.add_widget(item)
            return

        for i, session in enumerate(reversed(sessions)):
            preview = session.get("preview", "Session vide")
            date    = session.get("date", "")[:16].replace("T", " ")
            count   = session.get("message_count", 0)
            idx     = len(sessions) - 1 - i

            item = TwoLineListItem(
                text=f"Session {idx + 1}  —  {date}",
                secondary_text=f"{count} messages  ·  {preview[:50]}…",
            )
            item._session_index = idx
            item.bind(on_release=lambda x, si=idx: self._load(si))
            self.list_widget.add_widget(item)

    def _load(self, session_index):
        self.on_load_session(session_index)
        self.manager.current = "chat"

# ─── ÉCRAN PRINCIPAL (CHAT) ───────────────────────────────────────────────────

class ChatScreen(MDScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "chat"
        self.memory = load_memory()
        self.memory["session_count"] += 1
        self.memory["last_session"] = datetime.now().isoformat()
        save_memory(self.memory)
        self._typing_widget = None
        self._build_ui()

    # ── Construction UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = MDBoxLayout(orientation="vertical", md_bg_color=COLOR_BG)

        # ── Toolbar ──
        self.toolbar = MDTopAppBar(
            title="Vint-AI",
            md_bg_color=COLOR_TOOLBAR,
            specific_text_color=(1, 1, 1, 1),
        )
        self.toolbar.left_action_items  = [["menu", lambda x: self._open_history()]]
        self.toolbar.right_action_items = [["delete-sweep", lambda x: self._clear_chat()]]
        root.add_widget(self.toolbar)

        # ── Zone messages ──
        self.scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.chat_box = MDBoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=[dp(6), dp(8)],
            spacing=dp(6),
        )
        self.chat_box.bind(minimum_height=self.chat_box.setter('height'))
        self.scroll.add_widget(self.chat_box)
        root.add_widget(self.scroll)

        # ── Barre de saisie ──
        input_bar = MDBoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(64),
            padding=[dp(8), dp(8)],
            spacing=dp(6),
            md_bg_color=COLOR_INPUT_BG,
        )

        self.text_input = MDTextField(
            hint_text="Écris ton message…",
            mode="round",
            size_hint=(1, None),
            height=dp(48),
            font_size=sp(16),
            multiline=False,
        )
        self.text_input.bind(on_text_validate=lambda x: self._send())

        send_btn = MDIconButton(
            icon="send-circle",
            icon_size=dp(36),
            theme_icon_color="Custom",
            icon_color=COLOR_USER_BUBBLE,
            on_release=lambda x: self._send(),
        )

        input_bar.add_widget(self.text_input)
        input_bar.add_widget(send_btn)
        root.add_widget(input_bar)

        self.add_widget(root)

        # Message de bienvenue
        name = self.memory["user_info"].get("name") or "toi"
        self._append_ai(f"👋 Bonjour {name} ! Je suis Vint-AI. Comment puis-je t'aider ?")

        # Recharger la conv en cours
        for msg in self.memory["conversation_history"]:
            bubble = make_bubble(msg["content"], is_user=(msg["role"] == "user"))
            self.chat_box.add_widget(bubble)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _send(self):
        text = self.text_input.text.strip()
        if not text:
            return
        self.text_input.text = ""

        # Bulle utilisateur
        self.chat_box.add_widget(make_bubble(text, is_user=True))
        self._scroll_down()

        # Indicateur de frappe
        self._typing_widget = make_typing_indicator()
        self.chat_box.add_widget(self._typing_widget)
        self._scroll_down()

        add_to_history(self.memory, "user", text)
        save_memory(self.memory)

        threading.Thread(target=self._fetch_response, daemon=True).start()

    def _fetch_response(self):
        response = ask_groq(self.memory["conversation_history"])
        Clock.schedule_once(lambda dt: self._on_response(response))

    def _on_response(self, response: str):
        # Supprimer indicateur
        if self._typing_widget:
            self.chat_box.remove_widget(self._typing_widget)
            self._typing_widget = None

        self._append_ai(response)
        add_to_history(self.memory, "assistant", response)

        # Sauvegarder session dans l'historique
        hist = self.memory["conversation_history"]
        if hist:
            preview = next((m["content"] for m in hist if m["role"] == "user"), "")
            session_data = {
                "date": datetime.now().isoformat(),
                "message_count": len(hist),
                "preview": preview,
                "messages": hist.copy(),
            }
            sessions = self.memory.setdefault("sessions", [])
            # Màj la dernière session ou en créer une nouvelle
            if sessions and sessions[-1].get("date", "")[:10] == datetime.now().isoformat()[:10]:
                sessions[-1] = session_data
            else:
                sessions.append(session_data)

        save_memory(self.memory)
        self._scroll_down()

    def _append_ai(self, text: str):
        self.chat_box.add_widget(make_bubble(text, is_user=False))
        self._scroll_down()

    def _scroll_down(self):
        Clock.schedule_once(lambda dt: setattr(self.scroll, 'scroll_y', 0), 0.1)

    def _clear_chat(self):
        self.chat_box.clear_widgets()
        self.memory["conversation_history"] = []
        save_memory(self.memory)
        self._append_ai("🗑️ Conversation effacée. Nouvelle session prête !")

    def _open_history(self):
        hist_screen = self.manager.get_screen("history")
        hist_screen.memory_ref = self.memory
        hist_screen.refresh()
        self.manager.current = "history"

    def load_session(self, session_index):
        sessions = self.memory.get("sessions", [])
        if session_index >= len(sessions):
            return
        session = sessions[session_index]
        self.chat_box.clear_widgets()
        self.memory["conversation_history"] = session["messages"].copy()
        for msg in session["messages"]:
            bubble = make_bubble(msg["content"], is_user=(msg["role"] == "user"))
            self.chat_box.add_widget(bubble)
        self._scroll_down()

# ─── APPLICATION ──────────────────────────────────────────────────────────────

class VintAIApp(MDApp):

    def build(self):
        self.title = "Vint-AI"
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Brown"

        sm = MDScreenManager()

        chat_screen = ChatScreen()
        history_screen = HistoryScreen(
            memory_ref=chat_screen.memory,
            on_load_session=chat_screen.load_session,
        )

        sm.add_widget(chat_screen)
        sm.add_widget(history_screen)
        sm.current = "chat"
        return sm


if __name__ == "__main__":
    VintAIApp().run()
