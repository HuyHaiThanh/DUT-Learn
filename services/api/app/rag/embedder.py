"""Embedding boundary shared by ingest and retrieval; unit tests never load E5."""

import hashlib
import math
import threading
from typing import Any, Protocol

from app.config import Settings, get_settings


class Tokenizer(Protocol):
    def encode(self, text: str, *, add_special_tokens: bool = True) -> list[int]: ...


class Embedder(Protocol):
    dim: int

    @property
    def tokenizer(self) -> Tokenizer: ...

    def count_tokens(self, text: str) -> int: ...
    def embed_passages(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class WhitespaceTokenizer:
    def encode(self, text: str, *, add_special_tokens: bool = True) -> list[int]:
        ids = [int.from_bytes(hashlib.sha256(t.encode()).digest()[:4]) for t in text.split()]
        return [0, *ids, 1] if add_special_tokens else ids


class FakeEmbedder:
    dim = 384
    model_name = "fake-sha256-384"
    tokenizer = WhitespaceTokenizer()

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text))

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in text.split():
            digest = hashlib.sha256(token.encode()).digest()
            vector[int.from_bytes(digest[:4]) % self.dim] += 1 if digest[4] & 1 else -1
        norm = math.sqrt(sum(v * v for v in vector))
        if not norm:
            vector[0] = norm = 1.0
        return [v / norm for v in vector]

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._embed("passage: " + text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed("query: " + text)


class E5Embedder:
    dim = 384
    # One model per configured name in this process, including concurrent callers.
    _models: dict[str, Any] = {}
    _lock = threading.RLock()

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or get_settings().embed_model

    def _model(self) -> Any:
        with self._lock:
            if self.model_name not in self._models:
                import torch
                from sentence_transformers import SentenceTransformer

                model = SentenceTransformer(
                    self.model_name, device="cuda" if torch.cuda.is_available() else "cpu"
                )
                if model.get_sentence_embedding_dimension() != self.dim:
                    raise ValueError("Mô hình embedding phải có 384 chiều.")
                model.max_seq_length = 512
                self._models[self.model_name] = model
            return self._models[self.model_name]

    @property
    def tokenizer(self) -> Any:
        return self._model().tokenizer

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=True))

    def _encode(self, texts: list[str], prefix: str) -> list[list[float]]:
        if not texts:
            return []
        inputs = [prefix + text for text in texts]
        if any(self.count_tokens(text) > 512 for text in inputs):
            raise ValueError("Đoạn vượt giới hạn 512 token của embedding.")
        with self._lock:
            result: list[list[float]] = (
                self._model()
                .encode(
                    inputs,
                    batch_size=32,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                    prompt="",
                )
                .tolist()
            )
        return result

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts, "passage: ")

    def embed_query(self, text: str) -> list[float]:
        return self._encode([text], "query: ")[0]


def get_embedder(settings: Settings) -> Embedder:
    return E5Embedder(settings.embed_model)
