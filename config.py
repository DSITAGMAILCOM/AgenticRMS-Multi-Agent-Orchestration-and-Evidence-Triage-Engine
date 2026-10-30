# config.py
import os
from dotenv import load_dotenv
from rich.console import Console
from groq import Groq

# 1. Base Paths & Environment
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "university.db")
ADMIN_DB_PATH = os.path.join(BASE_DIR, "admin.db")
ENV_PATH = os.path.join(BASE_DIR, ".env")

load_dotenv(dotenv_path=ENV_PATH, override=True)

console = Console()

# 2. Groq Client Initialization
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip().strip("'\"")
if not GROQ_API_KEY or GROQ_API_KEY.startswith("gsk_your_groq"):
    try:
        import streamlit as _st
        if hasattr(_st, "secrets") and "GROQ_API_KEY" in _st.secrets:
            GROQ_API_KEY = str(_st.secrets["GROQ_API_KEY"]).strip().strip("'\"")
    except Exception:
        pass

if not GROQ_API_KEY or GROQ_API_KEY.startswith("gsk_your_groq"):
    console.print("[bold yellow]⚠️ WARNING: Valid GROQ_API_KEY not found in .env or st.secrets. Please configure your Groq API key.[/bold yellow]")

client = Groq(api_key=GROQ_API_KEY or "dummy_key_to_prevent_init_crash")

# 3. Fixed Model Definition (Locked strictly to gpt-oss-20b)
ACTIVE_MODEL = "openai/gpt-oss-20b"
AGENT_MODEL = ACTIVE_MODEL

def get_model(custom_model: str = None) -> str:
    """
    Enforces openai/gpt-oss-20b universally across all agents.
    Disallows fallback or switching to other models.
    """
    return ACTIVE_MODEL