import os


class Settings:
    LLM_PROVIDER: str = os.environ.get("LLM_PROVIDER", "ollama")

    OLLAMA_HOST: str = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL: str = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
    OLLAMA_NUM_CTX: int = int(os.environ.get("OLLAMA_NUM_CTX", "8192"))

    OPENROUTER_API_KEY: str = os.environ.get("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.environ.get(
        "OPENROUTER_MODEL", "qwen/qwen-2.5-72b-instruct"
    )

    SQLITE_PATH: str = os.environ.get("SQLITE_PATH", "app.db")

    MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024  # 5MB


settings = Settings()
