from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DUT_", env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://dutlearn:dutlearn@127.0.0.1:5433/dutlearn"
    data_dir: Path = Path("../../data")
    session_ttl_hours: int = Field(default=12, gt=0)
    cookie_secure: bool = False
    seed_password: str = "dutlearn-dev"
    llm_base_url: str = "http://127.0.0.1:11434"
    llm_model: str = "qwen2.5:7b-instruct"
    llm_timeout_s: float = 90
    embed_model: str = "intfloat/multilingual-e5-small"
    retriever: Literal["dense", "hybrid"] = "dense"
    top_k: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
