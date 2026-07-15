"""
운영 데이터가 관리 기준을 벗어났는지 자동으로 확인하는 이상 알림 모듈.
pandas로 직접 비교하는 규칙 기반 로직이라, 계산 오류나 지어낸 알림 없이 항상 정확하다.
"""
from __future__ import annotations

import pandas as pd

# menu_id -> 이상 여부 판정 규칙. "over"는 기준 초과 시, "under"는 기준 미달 시 경고.
# 임계치는 예시 값이며, 실제 운영 기준에 맞게 조정해서 쓰면 된다.
ALERT_RULES = {
    4: {"direction": "over", "threshold": 3.0, "reason": "관리 기준(3%)을 초과한 불량률"},
    8: {"direction": "under", "threshold": 500, "reason": "안전 재고 기준(500개) 미만"},
    14: {"direction": "under", "threshold": 85.0, "reason": "정상 가동 기준(85%) 미만"},
}


def check_alerts(records: pd.DataFrame, menu_df: pd.DataFrame) -> list[dict]:
    """모든 규칙을 현재 데이터에 대입해, 기준을 벗어난 항목 목록을 반환한다."""
    alerts = []
    for menu_id, rule in ALERT_RULES.items():
        sub = records[records["menu_id"] == menu_id]
        if sub.empty:
            continue
        row = menu_df.loc[menu_df["id"] == menu_id].iloc[0]
        unit = row["unit"] if row["unit"] != "-" else ""

        for _, r in sub.iterrows():
            is_alert = (
                r["value"] > rule["threshold"] if rule["direction"] == "over"
                else r["value"] < rule["threshold"]
            )
            if is_alert:
                alerts.append({
                    "menu_id": menu_id,
                    "data_name": row["data_name"],
                    "label": r["label"],
                    "value": r["value"],
                    "unit": unit,
                    "reason": rule["reason"],
                })
    return alerts


def alerts_for_row(all_alerts: list[dict], row_id: int) -> list[dict]:
    return [a for a in all_alerts if a["menu_id"] == row_id]


def format_alert_line(alert: dict) -> str:
    return f"{alert['label']} {alert['value']}{alert['unit']} — {alert['reason']}"
