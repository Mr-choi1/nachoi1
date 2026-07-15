"""
PC에 설치된 Ollama(로컬 LLM 실행 프로그램)와 통신하는 모듈.
인터넷의 외부 AI API(OpenAI/Anthropic 등)는 전혀 호출하지 않는다 —
오직 이 컴퓨터에서 실행 중인 http://127.0.0.1:11434 로만 요청을 보낸다.
"""
from __future__ import annotations

import json
import re

import requests

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL_NAME = "qwen2.5:3b-instruct"
TIMEOUT_SEC = 120
KEEP_ALIVE = "30m"  # 마지막 요청 후 이 시간 동안 모델을 메모리에 상주시켜, 질문마다 재로딩되는 지연을 없앤다

SYSTEM_PROMPT = """당신은 'SB선보 ERP 데이터 챗봇'입니다. 사내 직원들이 ERP 시스템 어디에 어떤 데이터가 있는지 몰라 헤매는 문제를 해결하기 위해 만들어졌습니다.

규칙:
1. 답변은 반드시 한국어로만 작성합니다. 중국어, 영어 등 다른 언어를 절대 섞지 마세요. 친근하고 간결한 대화체를 사용하세요.
2. 사용자 메시지 앞에 '[참고 데이터]' 블록이 주어지면, 그 안의 사실(부서, 경로, 수치)만 근거로 답변하세요. 참고 데이터에 없는 숫자나 사실을 지어내지 마세요.
3. 합계/평균/최댓값/최솟값이 '[참고 데이터]'에 이미 계산되어 적혀 있으면 그 숫자를 반드시 그대로 인용하세요. 당신은 여러 자리 숫자 암산을 자주 틀리니, 직접 덧셈·나눗셈 등을 다시 계산하지 마세요. 참고 데이터에 없는 계산이 필요하면 "정확한 계산은 어렵다"고 솔직히 말하세요.
4. '[참고 데이터]'가 없는데 ERP 데이터에 대한 질문이라면, 잘 모르겠다고 솔직히 말하고 어떤 종류의 데이터를 찾아줄 수 있는지 예시를 들어 안내하세요.
5. 인사, 감사 인사, 잡담에는 짧고 자연스럽게 응답하세요.
6. 표나 그래프는 화면에 별도로 자동으로 그려지므로, 답변 텍스트 안에서는 '|---|---|' 같은 마크다운 표를 절대 만들지 마세요. 핵심 내용만 문장으로 설명하세요."""

MAX_HISTORY_TURNS = 8  # 최근 8턴(사용자+챗봇 합쳐 최대 16개 메시지)만 모델에 전달해 속도를 확보


class OllamaError(Exception):
    """Ollama 서버에 연결하지 못했거나 응답이 실패했을 때"""


def strip_markdown_tables(text: str) -> str:
    """모델이 시스템 프롬프트 지시를 무시하고 마크다운 표를 그렸다면 제거한다 (실제 표는 화면에 별도로 렌더링됨)."""
    # 문장 중간에 "...입니다.|---|---|" 처럼 표 구분선이 섞여 나오는 경우도 있어, 줄 단위 필터 전에 먼저 지운다.
    text = re.sub(r"\|-{2,}\|(?:-{2,}\|)*", "", text)

    cleaned_lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        is_table_row = stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2
        is_separator_row = bool(re.fullmatch(r"[|\s:\-]+", stripped)) and "-" in stripped
        if is_table_row or is_separator_row:
            continue
        cleaned_lines.append(line)

    result = "\n".join(cleaned_lines)
    result = re.sub(r"[ \t]{2,}", " ", result)
    return re.sub(r"\n{3,}", "\n\n", result).strip()


def is_available() -> bool:
    try:
        requests.get("http://127.0.0.1:11434/api/version", timeout=2)
        return True
    except requests.exceptions.RequestException:
        return False


def warmup(model: str = MODEL_NAME) -> None:
    """서버가 뜨자마자 모델을 미리 메모리에 올려서, 첫 사용자 질문부터 느린 콜드 스타트 없이 답할 수 있게 한다."""
    try:
        requests.post(
            OLLAMA_URL,
            json={"model": model, "messages": [{"role": "user", "content": "안녕"}], "stream": False, "keep_alive": KEEP_ALIVE},
            timeout=TIMEOUT_SEC,
        )
    except requests.exceptions.RequestException:
        pass


def _build_messages(history: list[dict], context_block: str | None) -> list[dict]:
    trimmed = history[-(MAX_HISTORY_TURNS * 2):]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if context_block:
        messages.extend(trimmed[:-1])
        messages.append({"role": "system", "content": f"[참고 데이터]\n{context_block}"})
        messages.append(trimmed[-1])
    else:
        messages.extend(trimmed)

    return messages


def chat_stream(history: list[dict], context_block: str | None, model: str = MODEL_NAME):
    """
    history: [{'role': 'user'|'assistant', 'content': str}, ...] (마지막 항목이 이번 사용자 질문)
    context_block: 이번 질문에 대해 실제로 확인한 ERP 데이터(있다면). 마지막 사용자 메시지 앞에 근거로 삽입한다.
    응답 텍스트 조각을 순서대로 yield한다 (실시간 타이핑 효과용).
    """
    messages = _build_messages(history, context_block)

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": model, "messages": messages, "stream": True, "keep_alive": KEEP_ALIVE},
            timeout=TIMEOUT_SEC,
            stream=True,
        )
        resp.raise_for_status()
    except requests.exceptions.ConnectionError as e:
        raise OllamaError("로컬 LLM 서버(Ollama)에 연결할 수 없어요. Ollama가 실행 중인지 확인해주세요.") from e
    except requests.exceptions.Timeout as e:
        raise OllamaError("응답이 너무 오래 걸려요. PC 리소스가 부족하거나 모델이 너무 클 수 있어요.") from e
    except requests.exceptions.HTTPError as e:
        raise OllamaError(f"모델 호출에 실패했어요: {e}") from e

    try:
        for line in resp.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            content = chunk.get("message", {}).get("content", "")
            if content:
                yield content
            if chunk.get("done"):
                break
    except requests.exceptions.RequestException as e:
        raise OllamaError("응답을 받는 도중 로컬 LLM 연결이 끊겼어요.") from e


def chat(history: list[dict], context_block: str | None, model: str = MODEL_NAME) -> str:
    """스트리밍 없이 완성된 답변 전체를 한 번에 받고 싶을 때 쓰는 편의 함수."""
    full_text = "".join(chat_stream(history, context_block, model))
    return strip_markdown_tables(full_text.strip())
