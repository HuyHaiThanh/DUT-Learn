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
    llm_num_ctx: int = Field(default=4096, gt=0)
    llm_keep_alive: str = "30m"
    llm_queue_wait_s: float = Field(default=30, gt=0)
    embed_model: str = "intfloat/multilingual-e5-small"
    retriever: Literal["dense", "hybrid"] = "dense"
    top_k: int = 5
    # T14c locks calibrated scores on the dev set; zero is uncalibrated.
    min_score_dense: float = 0.0
    min_score_hybrid: float = 0.0
    prefer_material_bonus: float = Field(default=0.02, ge=0, allow_inf_nan=False)
    prefer_page_bonus: float = Field(default=0.01, ge=0, allow_inf_nan=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
