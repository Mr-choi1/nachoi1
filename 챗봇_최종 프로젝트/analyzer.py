"""
매칭된 ERP 데이터(레코드)를 직접 읽어 통계를 계산하고, 대화체 문장으로 요약하는 모듈.
외부 AI 없이 pandas 연산 + 문장 템플릿만으로 동작한다.
"""
from __future__ import annotations

import pandas as pd


def _fmt(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.1f}"


def summarize_numeric(row: pd.Series, sub: pd.DataFrame) -> str:
    """sample_records.csv의 (label, value) 시계열/범주형 수치 데이터를 요약한다."""
    unit = row["unit"] if row["unit"] != "-" else ""
    n = len(sub)
    values = sub["value"]

    max_row = sub.loc[values.idxmax()]
    min_row = sub.loc[values.idxmin()]
    avg = values.mean()

    sentences = [f"제가 직접 데이터를 확인해봤어요. '{row['data_name']}' 항목은 총 {n}개예요."]

    if unit == "%":
        sentences.append(
            f"평균은 {_fmt(avg)}{unit}이고, 가장 높은 건 {max_row['label']} ({_fmt(max_row['value'])}{unit}), "
            f"가장 낮은 건 {min_row['label']} ({_fmt(min_row['value'])}{unit})이에요."
        )
    else:
        total = values.sum()
        sentences.append(
            f"합계는 {_fmt(total)}{unit}, 평균은 {_fmt(avg)}{unit}이에요. "
            f"가장 높은 건 {max_row['label']} ({_fmt(max_row['value'])}{unit}), "
            f"가장 낮은 건 {min_row['label']} ({_fmt(min_row['value'])}{unit})이에요."
        )

    labels = sub["label"].tolist()
    if len(labels) >= 2 and (str(labels[0]).endswith("월") or str(labels[0]).endswith("분기")):
        first, last = values.iloc[0], values.iloc[-1]
        if first:
            pct = (last - first) / first * 100
            direction = "증가" if pct >= 0 else "감소"
            sentences.append(f"{labels[0]} 대비 {labels[-1]}은 {abs(pct):.1f}% {direction}했어요.")

    return " ".join(sentences)


def summarize_detail(row: pd.Series, detail_sub: pd.DataFrame, columns: list) -> str:
    """detail_records.csv의 표 형태(비정형) 데이터를 요약한다."""
    n = len(detail_sub)
    first = detail_sub.iloc[0]
    field_cols = [c for c in detail_sub.columns if c.startswith("field")][: len(columns)]

    highlight = ", ".join(
        f"{label}: {first[col]}" for label, col in zip(columns, field_cols)
    )
    return (
        f"제가 직접 데이터를 확인해봤어요. '{row['data_name']}'에는 최근 {n}건이 등록돼 있어요. "
        f"가장 최근 항목은 {highlight} 이에요."
    )


def build_context_block(row: pd.Series, numeric_sub: pd.DataFrame, detail_sub: pd.DataFrame) -> str:
    """LLM에게 근거로 넘겨줄, 있는 그대로의 원본 데이터 텍스트를 만든다 (LLM이 직접 해석/계산하도록)."""
    lines = [
        f"데이터명: {row['data_name']}",
        f"담당 부서: {row['department']}",
        f"ERP 메뉴 경로: {row['menu_path']}",
        f"설명: {row['description']}",
    ]

    if not numeric_sub.empty:
        unit = row["unit"] if row["unit"] != "-" else ""
        lines.append("수치 데이터 (항목: 값):")
        for _, r in numeric_sub.iterrows():
            lines.append(f"- {r['label']}: {_fmt(r['value'])}{unit}")

        # LLM은 다자리 숫자 암산에서 자주 틀리므로, 합계/평균/최댓값/최솟값은 pandas로 미리 정확히 계산해서 넘긴다.
        values = numeric_sub["value"]
        max_row = numeric_sub.loc[values.idxmax()]
        min_row = numeric_sub.loc[values.idxmin()]
        lines.append(
            "이미 정확히 계산된 통계 (아래 숫자를 그대로 인용하세요. 절대 직접 다시 계산하지 마세요):"
        )
        if unit != "%":
            lines.append(f"- 합계: {_fmt(values.sum())}{unit}")
        lines.append(f"- 평균: {_fmt(values.mean())}{unit}")
        lines.append(f"- 최댓값: {max_row['label']} ({_fmt(max_row['value'])}{unit})")
        lines.append(f"- 최솟값: {min_row['label']} ({_fmt(min_row['value'])}{unit})")
    elif not detail_sub.empty:
        columns = row["detail_columns"].split("|")
        field_cols = [c for c in detail_sub.columns if c.startswith("field")][: len(columns)]
        lines.append("세부 기록:")
        for _, r in detail_sub.iterrows():
            pairs = ", ".join(f"{label}: {r[col]}" for label, col in zip(columns, field_cols))
            lines.append(f"- {pairs}")

    return "\n".join(lines)
