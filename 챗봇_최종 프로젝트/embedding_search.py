"""
Ollama의 임베딩 모델(bge-m3)로 의미 기반(semantic) 검색을 수행하는 모듈.
키워드 매칭(matcher.py)이 실패했을 때의 2차 검색 수단이다 — 오타나 완전히 다른 표현
(예: "쇠 값 얼마야?" -> 원자재 단가)에도 대응할 수 있다. 외부 API 없이 로컬 Ollama만 사용한다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import requests

OLLAMA_EMBED_URL = "http://127.0.0.1:11434/api/embed"
EMBED_MODEL = "bge-m3"
SIMILARITY_THRESHOLD = 0.48  # 이 값 미만이면 관련 없다고 판단해 매칭하지 않는다 (실측: 연관 질문 0.52~0.61 vs 무관 질문 0.30~0.43)


class EmbeddingError(Exception):
    """임베딩 모델 호출에 실패했을 때"""


def _embed(texts: list[str]) -> np.ndarray:
    try:
        resp = requests.post(
            OLLAMA_EMBED_URL,
            json={"model": EMBED_MODEL, "input": texts},
            timeout=30,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise EmbeddingError(f"임베딩 모델 호출에 실패했어요: {e}") from e

    data = resp.json()
    return np.array(data["embeddings"], dtype=np.float32)


def _searchable_text(row: pd.Series) -> str:
    keywords = row["keywords"].replace("|", ", ")
    return f"{row['data_name']}. {row['description']} 관련 키워드: {keywords}"


class SemanticIndex:
    """ERP 메뉴 목록을 미리 임베딩해두고, 질문과의 코사인 유사도로 가장 가까운 항목을 찾는다."""

    def __init__(self, menu_df: pd.DataFrame):
        self.menu_df = menu_df
        self.ids = menu_df["id"].tolist()

        texts = [_searchable_text(r) for _, r in menu_df.iterrows()]
        embeddings = _embed(texts)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        self._normed = embeddings / np.clip(norms, 1e-8, None)

    def search(self, query: str, top_k: int = 1) -> list[tuple[int, float]]:
        """(menu_id, 유사도) 목록을 유사도 내림차순으로 반환한다."""
        q_emb = _embed([query])[0]
        q_emb = q_emb / max(float(np.linalg.norm(q_emb)), 1e-8)

        sims = self._normed @ q_emb
        order = np.argsort(-sims)[:top_k]
        return [(self.ids[i], float(sims[i])) for i in order]
