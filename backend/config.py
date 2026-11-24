import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
DB = Path(os.getenv("TRUTHTRACE_DB", ROOT / "data/truthtrace.sqlite3"))


def provider():
    name = os.getenv("AI_PROVIDER") or (
        "groq" if os.getenv("GROQ_API_KEY") else "gemini"
    )
    if name not in {"groq", "gemini"}:
        raise ValueError("AI_PROVIDER must be groq or gemini")
    default = "openai/gpt-oss-20b" if name == "groq" else "gemini-3.1-flash-lite"
    key = os.getenv(name.upper() + "_API_KEY", "").strip()
    return (
        name,
        os.getenv(name.upper() + "_MODEL", default),
        "" if key == "PASTE_YOUR_KEY_HERE" else key,
    )
