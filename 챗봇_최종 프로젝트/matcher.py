"""
외부 AI(OpenAI/Anthropic 등) API를 전혀 사용하지 않는 자체 규칙 기반(키워드 매칭) 챗봇 엔진.
ERP 메뉴/데이터 목록(data/erp_menu.csv)에서 사용자 질문과 가장 관련 있는 항목을 찾아준다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

# 질문에서 의미 없는 조사/요청 표현을 제거하기 위한 목록
JOSA_SUFFIXES = [
    "으로는", "에서는", "이라는", "에게서", "으로써", "로써",
    "까지", "부터", "에서", "에게", "이랑", "이나",
    "은", "는", "이", "가", "을", "를", "의", "도", "만", "에", "로", "와", "과", "랑", "요",
]

STOPWORDS = {
    "알려줘", "알려주세요", "찾아줘", "찾아주세요", "보여줘", "보여주세요",
    "어디", "어디야", "어디있어", "어디있나요", "궁금해", "궁금해요", "궁금합니다",
    "있나요", "있어요", "싶어요", "싶습니다", "좀", "혹시", "그", "저", "제가",
    "챗봇", "데이터", "자료", "정보", "확인", "조회", "하고", "해줘", "부탁해",
}


# 사용자가 표/그래프 형태를 직접 요청했는지 감지하기 위한 단어 목록
TABLE_WORDS = {"표", "테이블", "리스트", "목록", "엑셀"}
GRAPH_WORDS = {"그래프", "차트", "도표", "그림", "시각화"}

# 잡담(인사/감사/자기소개 질문)에 대한 고정 응답
SMALLTALK_PATTERNS = [
    (("안녕", "hi", "hello", "하이"), "안녕하세요! 궁금한 ERP 데이터를 편하게 물어보세요. 예) '원자재 단가 어디서 봐?' 😊"),
    (("고마워", "고맙", "감사"), "천만에요! 더 궁금한 데이터 있으면 언제든 물어보세요."),
    (
        ("너 누구", "너는 누구", "당신은 누구", "누구야", "정체가 뭐", "정체는 뭐", "챗봇 소개", "자기소개", "무슨 챗봇", "어떤 챗봇", "소개해"),
        "저는 SB선보 ERP 데이터를 찾아드리는 사내 챗봇이에요. 외부 AI 없이 자체 규칙 기반으로 동작하고, ERP 메뉴 경로와 실제 데이터 요약을 알려드려요.",
    ),
]


def _strip_josa(token: str, min_remaining: int) -> str:
    """토큰 끝에 붙은 조사를 남지 않을 때까지 반복해서 제거한다 (예: '표로도' -> '표')."""
    changed = True
    while changed:
        changed = False
        for josa in JOSA_SUFFIXES:
            if token.endswith(josa) and len(token) - len(josa) >= min_remaining:
                token = token[: -len(josa)]
                changed = True
                break
    return token


def detect_smalltalk(query: str) -> str | None:
    """인사/감사/자기소개 같은 잡담이면 고정 응답을, 아니면 None을 반환한다."""
    text = query.strip()
    for keywords, reply in SMALLTALK_PATTERNS:
        if any(kw in text for kw in keywords):
            return reply
    return None


def detect_format(query: str) -> set:
    """질문에 '표로 보여줘', '그래프로 알려줘' 같은 출력 형태 요청이 있는지 감지한다."""
    text = re.sub(r"[^가-힣a-zA-Z0-9\s]", " ", query)
    formats = set()
    for tok in text.split():
        stripped = _strip_josa(tok, min_remaining=1)
        if stripped in TABLE_WORDS:
            formats.add("table")
        elif stripped in GRAPH_WORDS:
            formats.add("graph")
    return formats


def tokenize(text: str) -> set:
    """질문 문장을 단순 토큰 집합으로 변환한다 (형태소 분석기 없이 규칙 기반으로 처리)."""
    text = re.sub(r"[^가-힣a-zA-Z0-9\s]", " ", text)
    raw_tokens = text.split()

    tokens = set()
    for tok in raw_tokens:
        stripped = _strip_josa(tok, min_remaining=2)
        if stripped in STOPWORDS or len(stripped) < 2:
            continue
        tokens.add(stripped)
    return tokens


@dataclass
class MatchResult:
    row: pd.Series
    score: int


@dataclass
class MatchResponse:
    best: MatchResult | None
    suggestions: list = field(default_factory=list)


class ERPMenuMatcher:
    SCORE_THRESHOLD = 2  # 이 점수 미만이면 '못 찾음'으로 처리

    def __init__(self, menu_csv_path: str):
        self.df = pd.read_csv(menu_csv_path)
        self._keyword_sets = {}
        for _, row in self.df.iterrows():
            kw = set(row["keywords"].split("|"))
            kw |= tokenize(row["data_name"])
            kw.add(row["department"].replace("팀", ""))
            self._keyword_sets[row["id"]] = kw

    def _score_row(self, query_tokens: set, row: pd.Series) -> int:
        score = 0
        kw_set = self._keyword_sets[row["id"]]

        # 1) 키워드 완전 일치
        score += 3 * len(query_tokens & kw_set)

        # 2) 부분 문자열 일치 (예: '단가표' 안에 '단가' 포함)
        for qt in query_tokens:
            for kw in kw_set:
                if qt != kw and (qt in kw or kw in qt):
                    score += 1

        # 3) 메뉴명/설명 문자열에 직접 포함되는 경우 가산점
        for qt in query_tokens:
            if qt in row["data_name"]:
                score += 2
            if qt in row["description"]:
                score += 1

        return score

    def score_against(self, query: str, row_id: int) -> int:
        """특정 항목(row_id)이 이번 질문과 얼마나 관련 있는지 점수를 매긴다. (후속 질문 문맥 판단용)"""
        row = self.df.loc[self.df["id"] == row_id].iloc[0]
        return self._score_row(tokenize(query), row)

    def match(self, query: str, top_k: int = 3) -> MatchResponse:
        query_tokens = tokenize(query)
        if not query_tokens:
            return MatchResponse(best=None, suggestions=[])

        results = []
        for _, row in self.df.iterrows():
            score = self._score_row(query_tokens, row)
            if score > 0:
                results.append(MatchResult(row=row, score=score))

        results.sort(key=lambda r: r.score, reverse=True)

        if not results or results[0].score < self.SCORE_THRESHOLD:
            return MatchResponse(best=None, suggestions=results[:top_k])

        return MatchResponse(best=results[0], suggestions=results[1:top_k])
