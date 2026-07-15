"""
SB선보 ERP 데이터 찾기 챗봇

로컬에 설치된 오픈소스 LLM(Ollama)이 실제 ERP 데이터를 근거로 자유롭게 대화한다.
검색은 키워드 매칭을 우선 시도하고, 실패하면 임베딩 기반 의미 검색(bge-m3)으로 오타·유의어에도 대응한다.
외부 AI API(OpenAI/Anthropic 등)는 전혀 사용하지 않으며, 모든 계산과 생성이 이 PC 안에서만 이뤄진다.
Ollama가 꺼져 있을 때는 자체 규칙 기반 요약으로 자동 대체된다 (오프라인 모드).

실행 방법:
    pip install -r requirements.txt
    streamlit run chatAI.py
"""
import os

import pandas as pd
import plotly.express as px
import streamlit as st

import alerts
import analyzer
import embedding_search
import llm_engine
from matcher import ERPMenuMatcher, detect_format, detect_smalltalk

# 짧은 후속 질문이 직전 대화 주제를 이어받도록 하기 위한 신호 단어
# (지시어뿐 아니라 "평균은?", "제일 낮은 건?"처럼 직전 데이터에 대한 분석 질문도 포함)
CONTINUATION_CUES = {
    "그거", "그것", "이거", "이것", "그럼", "그래서", "방금", "아까", "위에", "해당",
    "평균", "합계", "총", "제일", "가장", "최고", "최저", "비교", "얼마", "증가", "감소", "차이",
}
FORMAT_LABEL = {"table": "표", "graph": "그래프"}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MENU_CSV = os.path.join(BASE_DIR, "data", "erp_menu.csv")
RECORDS_CSV = os.path.join(BASE_DIR, "data", "sample_records.csv")
DETAIL_CSV = os.path.join(BASE_DIR, "data", "detail_records.csv")

st.set_page_config(page_title="SB선보 ERP 데이터 챗봇", page_icon="🔎", layout="centered")


@st.cache_resource
def load_matcher() -> ERPMenuMatcher:
    return ERPMenuMatcher(MENU_CSV)


@st.cache_data
def load_records() -> pd.DataFrame:
    return pd.read_csv(RECORDS_CSV)


@st.cache_data
def load_details() -> pd.DataFrame:
    return pd.read_csv(DETAIL_CSV)


@st.cache_resource
def warmup_llm() -> bool:
    """서버 프로세스당 한 번만 실행되어 모델을 미리 메모리에 올려둔다 (첫 질문부터 빠르게 응답하도록)."""
    if llm_engine.is_available():
        llm_engine.warmup()
    return True


@st.cache_resource
def load_semantic_index() -> embedding_search.SemanticIndex | None:
    """임베딩 모델(bge-m3)로 메뉴 목록을 미리 인덱싱한다. 모델이 없거나 Ollama가 꺼져 있으면
    None을 반환하고, 이 경우 키워드 매칭만으로 정상 동작한다 (성능 저하 없는 안전한 degrade)."""
    try:
        return embedding_search.SemanticIndex(load_matcher().df)
    except embedding_search.EmbeddingError:
        return None


@st.cache_data(ttl=5)
def check_ollama_status() -> bool:
    """Ollama 연결 상태를 확인한다. 매 리런(부서 선택, 버튼 클릭 등)마다 매번 새로 확인하면
    체감 지연이 생기므로 5초간 결과를 캐싱한다."""
    return llm_engine.is_available()


matcher = load_matcher()
records = load_records()
details = load_details()
warmup_llm()
semantic_index = load_semantic_index()
all_alerts = alerts.check_alerts(records, matcher.df)


def get_row(row_id: int) -> pd.Series:
    return matcher.df.loc[matcher.df["id"] == row_id].iloc[0]


def resolve_row(query: str, last_row_id: int | None):
    """이번 질문이 어떤 ERP 메뉴와 관련 있는지 결정한다.
    1) 키워드 매칭(가장 정확) -> 2) 직전 대화 문맥 이어받기 -> 3) 임베딩 기반 의미 검색(오타·유의어 대응) 순으로 시도한다."""
    requested = detect_format(query)
    result = matcher.match(query)

    row_id = None
    used_context = False
    used_semantic = False

    if result.best is not None:
        row_id = int(result.best.row["id"])
    elif last_row_id is not None:
        weak_score = matcher.score_against(query, int(last_row_id))
        has_cue = any(cue in query for cue in CONTINUATION_CUES)
        if requested or weak_score > 0 or has_cue:
            row_id = int(last_row_id)
            used_context = True

    if row_id is None and semantic_index is not None:
        try:
            candidates = semantic_index.search(query, top_k=1)
        except embedding_search.EmbeddingError:
            candidates = []
        if candidates and candidates[0][1] >= embedding_search.SIMILARITY_THRESHOLD:
            row_id = candidates[0][0]
            used_semantic = True

    return row_id, used_context, requested, result.suggestions, used_semantic


def build_context_block(row_id: int | None, suggestions: list) -> str | None:
    """LLM에게 근거로 넘겨줄 실제 데이터 텍스트. 매칭된 항목이 있으면 그 데이터를, 없으면 애매한 후보만 전달한다."""
    if row_id is not None:
        row = get_row(row_id)
        numeric_sub = records[records["menu_id"] == row_id]
        detail_sub = details[details["menu_id"] == row_id]
        block = analyzer.build_context_block(row, numeric_sub, detail_sub)

        row_alerts = alerts.alerts_for_row(all_alerts, row_id)
        if row_alerts:
            lines = ["⚠️ 이상 감지됨 (답변에 반드시 이 사실을 먼저 언급하고 주의를 당부하세요):"]
            lines += [f"- {alerts.format_alert_line(a)}" for a in row_alerts]
            block += "\n\n" + "\n".join(lines)
        return block

    if suggestions:
        lines = ["다음은 이번 질문과 약하게 관련될 수 있는 ERP 메뉴 후보입니다 (확신할 수 없으니 사용자에게 되물어보세요):"]
        for s in suggestions:
            r = s.row
            lines.append(f"- {r['data_name']} (부서: {r['department']}, 경로: {r['menu_path']})")
        return "\n".join(lines)

    return None


def fallback_reply(row_id: int | None, used_context: bool, suggestions: list) -> str:
    """Ollama에 연결할 수 없거나 근거 데이터가 없을 때 쓰는 안전한 대체 답변 (기존 규칙 기반 요약)."""
    if row_id is None:
        if suggestions:
            lines = ["음, 정확히 어떤 데이터를 찾으시는지 못 알아들었어요. 혹시 이 중에 있을까요?"]
            for s in suggestions:
                r = s.row
                lines.append(f"- {r['data_name']} (`{r['menu_path']}`)")
            lines.append("아니라면 다른 단어로 다시 한 번 말씀해 주세요!")
            return "\n".join(lines)
        return (
            "죄송해요, 관련된 데이터를 찾지 못했어요. 😥 "
            "'원자재 단가', '공장별 매출액', '재고 현황'처럼 구체적인 데이터명으로 물어봐 주세요."
        )

    row = get_row(row_id)
    numeric_sub = records[records["menu_id"] == row_id]
    detail_sub = details[details["menu_id"] == row_id]
    if not numeric_sub.empty:
        summary = analyzer.summarize_numeric(row, numeric_sub)
    elif not detail_sub.empty:
        summary = analyzer.summarize_detail(row, detail_sub, row["detail_columns"].split("|"))
    else:
        summary = row["description"]

    if used_context:
        prefix = f"'{row['data_name']}' 관련해서 이어서 확인해볼게요."
    else:
        prefix = f"'{row['data_name']}'는 **{row['department']}**에서 관리하는 데이터예요 (`{row['menu_path']}`)."

    row_alerts = alerts.alerts_for_row(all_alerts, row_id)
    alert_note = ""
    if row_alerts:
        lines = ["⚠️ **이상 감지**"] + [f"- {alerts.format_alert_line(a)}" for a in row_alerts]
        alert_note = "\n\n" + "\n".join(lines)

    return f"{prefix}\n\n{summary}{alert_note}"


def available_formats(row_id: int | None) -> set:
    if row_id is None:
        return set()
    row = get_row(row_id)
    numeric_sub = records[records["menu_id"] == row_id]
    if not numeric_sub.empty:
        return {"table", "graph"} if row["output_type"] == "both" else {"table"}
    detail_sub = details[details["menu_id"] == row_id]
    if not detail_sub.empty:
        return {"table"}
    return set()


def render_visual(row_id: int | None, requested_formats: list):
    """표/그래프는 LLM이 아니라 실제 데이터로 직접 그린다 (수치 왜곡 없이 정확하게 보여주기 위함)."""
    if row_id is None:
        return

    avail = available_formats(row_id)
    requested = set(requested_formats)
    show = requested & avail

    if requested and not show and avail:
        avail_label = "/".join(FORMAT_LABEL[f] for f in sorted(avail))
        st.caption(f"(이 데이터는 {avail_label} 형태로만 볼 수 있어요.)")
        show = avail

    if not show:
        return

    row = get_row(row_id)
    numeric_sub = records[records["menu_id"] == row_id]
    detail_sub = details[details["menu_id"] == row_id]

    if not numeric_sub.empty:
        unit = row["unit"] if row["unit"] != "-" else ""
        value_col = f"값({unit})" if unit else "값"

        if "table" in show:
            table = numeric_sub.rename(columns={"label": row["data_name"], "value": value_col})
            st.dataframe(table[[row["data_name"], value_col]], hide_index=True, width="stretch")

        if "graph" in show:
            fig = px.bar(
                numeric_sub, x="label", y="value",
                labels={"label": row["data_name"], "value": unit or "값"},
                title=f"{row['data_name']} ({unit})" if unit else row["data_name"],
            )
            st.plotly_chart(fig, width="stretch")

    elif not detail_sub.empty and "table" in show:
        columns = row["detail_columns"].split("|")
        field_cols = [c for c in detail_sub.columns if c.startswith("field")][: len(columns)]
        table = detail_sub[field_cols].rename(columns=dict(zip(field_cols, columns)))
        st.dataframe(table, hide_index=True, width="stretch")


def render_alert_box(row_id: int | None):
    """해당 항목에 이상 알림이 있으면 눈에 띄는 경고 박스로 한 번 더 강조한다."""
    if row_id is None:
        return
    row_alerts = alerts.alerts_for_row(all_alerts, row_id)
    if row_alerts:
        st.warning("⚠️ 이상 감지\n\n" + "\n".join(f"- {alerts.format_alert_line(a)}" for a in row_alerts))


def render_message(msg: dict):
    st.markdown(msg["text"])
    if msg["role"] == "assistant":
        if msg.get("mode") == "fallback":
            st.caption("⚠️ 로컬 LLM(Ollama)에 연결하지 못해 기본 요약으로 답변했어요.")
        if msg.get("used_semantic"):
            st.caption("🔍 정확히 일치하는 단어는 없었지만, 의미가 비슷한 데이터를 찾았어요.")
        render_alert_box(msg.get("row_id"))
        render_visual(msg.get("row_id"), msg.get("requested_formats", []))


st.title("🔎 SB선보 ERP 데이터 챗봇")
st.caption(
    "이 PC에 설치된 로컬 AI(오프라인 LLM)가 실제 ERP 데이터를 참고해서 자유롭게 대화해드려요. "
    "외부 서버로는 아무것도 전송되지 않아요. '표로 보여줘', '그래프로 보여줘'처럼 요청하면 실제 표/그래프도 함께 보여드립니다."
)

if all_alerts:
    with st.expander(f"⚠️ 현재 이상 데이터 {len(all_alerts)}건 감지됨 — 클릭해서 확인하세요", expanded=False):
        for a in all_alerts:
            st.markdown(f"- **{a['data_name']}** · {alerts.format_alert_line(a)}")

with st.sidebar:
    ollama_ok = check_ollama_status()
    if ollama_ok:
        st.success(f"로컬 AI 연결됨 ({llm_engine.MODEL_NAME})")
    else:
        st.warning("로컬 AI(Ollama) 연결 안 됨 — 기본 요약 모드로 동작해요.")

    if semantic_index is not None:
        st.caption(f"🔍 의미 기반 검색 사용 가능 ({embedding_search.EMBED_MODEL})")
    else:
        st.caption("🔍 의미 기반 검색 비활성 — 키워드 검색만 사용해요.")

    if all_alerts:
        st.error(f"⚠️ 이상 알림 {len(all_alerts)}건")
        for a in all_alerts:
            st.caption(f"· {a['data_name']}: {alerts.format_alert_line(a)}")
        st.divider()

    sidebar_clicked = None

    st.subheader("👤 내 부서")
    departments = ["선택 안 함"] + sorted(matcher.df["department"].unique().tolist())
    selected_dept = st.selectbox(
        "부서를 선택하면 자주 쓰는 데이터를 바로가기로 추천해드려요 (신입/이직자도 헤맬 필요 없이!)",
        departments,
    )

    if selected_dept != "선택 안 함":
        dept_rows = matcher.df[matcher.df["department"] == selected_dept]
        st.markdown(f"**⭐ {selected_dept} 자주 찾는 데이터**")
        for _, r in dept_rows.iterrows():
            if st.button(r["data_name"], key=f"quick_{r['id']}", width="stretch"):
                sidebar_clicked = f"{r['data_name']} 알려줘"

    st.divider()
    st.subheader("💡 이렇게 물어보세요")
    examples = [
        "원자재 단가 어디서 봐?",
        "이번 달 불량률을 그래프로 보여줘",
        "공장별 매출액을 표로 보여줘",
        "재고 현황 확인하고 싶어",
        "분기 경영보고서 어디 있어?",
    ]
    for ex in examples:
        if st.button(ex, width="stretch"):
            sidebar_clicked = ex

    st.divider()
    st.subheader("📋 등록된 메뉴 목록")
    menu_display = matcher.df[["department", "data_name", "menu_path"]].copy()
    if selected_dept != "선택 안 함":
        menu_display["_내부서"] = menu_display["department"] != selected_dept
        menu_display = menu_display.sort_values("_내부서").drop(columns="_내부서")
    st.dataframe(
        menu_display.rename(
            columns={"department": "부서", "data_name": "데이터명", "menu_path": "ERP 경로"}
        ),
        hide_index=True,
        width="stretch",
    )

if "messages" not in st.session_state:
    greeting = "안녕하세요! 궁금한 ERP 데이터를 편하게 물어보세요. 예) '원자재 단가 어디서 봐?' 😊"
    if all_alerts:
        alert_names = ", ".join(sorted({a["data_name"] for a in all_alerts}))
        greeting = (
            f"안녕하세요! 참고로 지금 {len(all_alerts)}건의 이상 데이터가 감지됐어요 ({alert_names}). "
            "궁금한 ERP 데이터를 편하게 물어보세요. 예) '원자재 단가 어디서 봐?' 😊"
        )

    st.session_state["messages"] = [
        {
            "role": "assistant",
            "text": greeting,
            "row_id": None,
            "requested_formats": [],
            "mode": "greeting",
        }
    ]

for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        render_message(msg)

query = st.chat_input("질문을 입력하세요 (예: 원자재 단가 어디서 봐?)") or sidebar_clicked

if query:
    st.session_state["messages"].append({"role": "user", "text": query})
    with st.chat_message("user"):
        st.markdown(query)

    row_id, used_context, requested, suggestions, used_semantic = resolve_row(
        query, st.session_state.get("last_row_id")
    )
    smalltalk = detect_smalltalk(query)

    with st.chat_message("assistant"):
        if smalltalk:
            # 인사/감사 같은 잡담은 LLM 호출 없이 바로 답한다 (빠르고, 엉뚱한 ERP 내용을 지어낼 위험도 없음).
            reply_text, mode = smalltalk, "smalltalk"
            st.markdown(reply_text)
        elif row_id is None:
            # 근거로 삼을 실제 ERP 데이터가 없는 상태에서 LLM에게 자유 생성을 맡기면 존재하지 않는
            # 메뉴 경로를 지어낼 위험이 있어(실제로 확인됨), 이 경우엔 검증된 안내 문구만 사용한다.
            reply_text, mode = fallback_reply(row_id, used_context, suggestions), "no_context"
            st.markdown(reply_text)
        else:
            if used_semantic:
                st.caption("🔍 정확히 일치하는 단어는 없었지만, 의미가 비슷한 데이터를 찾았어요.")
            context_block = build_context_block(row_id, suggestions)
            llm_history = [{"role": m["role"], "content": m["text"]} for m in st.session_state["messages"]]
            try:
                # ChatGPT처럼 실시간으로 글자가 나오도록 스트리밍으로 받는다.
                raw_text = st.write_stream(llm_engine.chat_stream(llm_history, context_block))
                reply_text = llm_engine.strip_markdown_tables(raw_text)
                mode = "llm"
            except llm_engine.OllamaError:
                reply_text = fallback_reply(row_id, used_context, suggestions)
                mode = "fallback"
                st.markdown(reply_text)
                st.caption("⚠️ 로컬 LLM(Ollama)에 연결하지 못해 기본 요약으로 답변했어요.")

            render_alert_box(row_id)
            render_visual(row_id, sorted(requested))

    if row_id is not None:
        st.session_state["last_row_id"] = row_id

    st.session_state["messages"].append({
        "role": "assistant",
        "text": reply_text,
        "row_id": row_id,
        "requested_formats": sorted(requested),
        "mode": mode,
        "used_semantic": used_semantic,
    })
