"""
Central app configuration. Loaded once from environment variables / .env.
Nothing in here should hold secrets in code - everything comes from env.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Groq
    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Chroma Cloud
    CHROMA_API_KEY: str
    CHROMA_TENANT: str
    CHROMA_DATABASE: str
    CHROMA_COLLECTION: str = "documents"

    # Firebase
    FIREBASE_SERVICE_ACCOUNT_PATH: str = "./firebase-service-account.json"
    FIREBASE_SERVICE_ACCOUNT_JSON: str | None = None

    # Chunking
    CHUNK_SIZE: int = 1800
    CHUNK_OVERLAP: int = 200
    CHUNK_STRATEGY: str = "hybrid"  # recursive|token|character|sentence|hybrid|semantic

    # Token safety ceiling per chunk, kept under the LLM's real context limit
    MAX_CHUNK_TOKENS: int = 1500

    # Retrieval: MMR diversity + score threshold
    MMR_ENABLED: bool = True
    MMR_FETCH_K: int = 20        # candidate pool pulled before MMR reranking
    MMR_LAMBDA: float = 0.5      # 1.0 = pure relevance, 0.0 = pure diversity
    SCORE_DISTANCE_THRESHOLD: float = 0.6  # candidates with distance above this are dropped as too weak

    # App
    ENV: str = "development"
    CORS_ORIGINS: str = "http://localhost:5173"

    # Security
    MAX_UPLOAD_SIZE_MB: int = 20
    RATE_LIMIT_UPLOAD: str = "10/minute"
    RATE_LIMIT_QUERY: str = "20/minute"
    ENABLE_PII_REDACTION: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
