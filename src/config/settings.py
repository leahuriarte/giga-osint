from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv
from pathlib import Path

# Load .env from repo root (cwd-agnostic)
repo_root = Path(__file__).resolve().parents[2]
load_dotenv(repo_root / ".env")

class Settings(BaseSettings):
    gemini_api_key: str = Field(alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", alias="EMBEDDING_MODEL")
    chroma_dir: str = Field(default=".chromadb", alias="CHROMA_DIR")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    cross_encoder_model: str = Field(default="cross-encoder/ms-marco-MiniLM-L-6-v2", alias="CROSS_ENCODER_MODEL")
    default_recent_days: int = Field(default=30, alias="DEFAULT_RECENT_DAYS")
    graph_path: str = Field(default=".graph/osint_graph.pkl", alias="GRAPH_PATH")
    use_graph_bias: bool = Field(default=True, alias="USE_GRAPH_BIAS")
    verify_strength: int = Field(default=2, alias="VERIFY_STRENGTH")  # 1–3, higher = slower/stricter



    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()  # import this elsewhere
