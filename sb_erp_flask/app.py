import copy
import os
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# ---------- 포텐스닷(potens.ai) LLM 연동 ----------
# 키는 코드에 직접 넣지 말고 환경변수 POTENS_API_KEY 로 설정합니다.
POTENS_API_URL = 'https://ai.potens.ai/api/chat'
POTENS_MODEL = 'claude-4-6-sonnet'


def call_potens_ai(prompt):
    api_key = os.environ.get('POTENS_API_KEY')
    if not api_key:
        raise RuntimeError('POTENS_API_KEY 환경변수가 설정되어 있지 않습니다.')

    response = requests.post(
        POTENS_API_URL,
        json={'prompt': prompt, 'model': POTENS_MODEL},
        headers={'Authorization': f'Bearer {api_key}'},
        timeout=15
    )
    response.raise_for_status()
    return response.json().get('message', '')


# ---------- 오타 보정 (레벤슈타인 유사도) ----------
# 각 카테고리 키워드 목록 자체가 유사어 사전 역할을 하고,
# 여기에 오타까지 허용하기 위해 단어 단위 유사도 매칭을 함께 사용한다.
def calculate_similarity(a, b):
    len1, len2 = len(a), len(b)
    if len1 == 0 or len2 == 0:
        return 1.0 if len1 == len2 else 0.0

    matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]
    for i in range(len1 + 1):
        matrix[i][0] = i
    for j in range(len2 + 1):
        matrix[0][j] = j

    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            if a[i - 1] == b[j - 1]:
                matrix[i][j] = matrix[i - 1][j - 1]
            else:
                matrix[i][j] = min(
                    matrix[i - 1][j - 1] + 1,
                    matrix[i][j - 1] + 1,
                    matrix[i - 1][j] + 1
                )

    distance = matrix[len1][len2]
    return 1 - distance / max(len1, len2)


def contains_keyword(query, keywords):
    for keyword in keywords:
        if keyword in query:
            return True
        for word in query.split():
            # 한글 2음절 키워드는 오타 한 글자만 나도 유사도가 0.5까지 떨어지므로
            # 기준을 0.5로 낮춰서 실사용 오타(메출→매출 등)를 잡는다.
            if len(word) >= 2 and calculate_similarity(word, keyword) >= 0.5:
                return True
    return False


# ---------- 웹 앱 실행 ----------
@app.route('/')
def index():
    return render_template('index.html')


# ---------- AI 챗봇 응답 처리 ----------
@app.route('/api/query', methods=['POST'])
def process_ai_query_route():
    user_query = request.json.get('query', '')
    return jsonify(process_ai_query(user_query))


def process_ai_query(user_query):
    query = user_query.lower()

    period = extract_period(query)
    is_comparison = contains_keyword(query, ['비교', '차이', '대비'])
    specific_item = extract_specific_item(query)
    stats_type = extract_stats_type(query)
    is_cause_analysis = contains_keyword(query, ['원인', '이유', '왜'])

    result = None

    if contains_keyword(query, ['재무', '매출', '수익', '손익', '이익']):
        result = handle_financial_query(query, period, is_comparison, specific_item, stats_type)
    elif contains_keyword(query, ['생산', '제품', '생산량', '공장']):
        result = handle_production_query(query, period, is_comparison, specific_item, stats_type)
    elif contains_keyword(query, ['구매', '발주', '자재', '공급']):
        result = handle_purchase_query(query, period, is_comparison, specific_item, stats_type)
    elif contains_keyword(query, ['품질', '불량', '검사', '합격']):
        result = handle_quality_query(query, period, is_comparison, specific_item, stats_type, is_cause_analysis)
    elif contains_keyword(query, ['인사', '직원', '사원', '근태', '부서']):
        result = handle_hr_query(query, period, is_comparison, specific_item, stats_type)
    elif contains_keyword(query, ['전체', '모든', '종합']):
        result = handle_comprehensive_query(query)

    if result:
        return enrich_structured_response(result)

    # 정형 카테고리 키워드에 걸리지 않은 자유 질문은 포텐스닷 LLM에게 위임
    try:
        ai_answer = call_potens_ai(user_query)
        return {
            'type': 'text',
            'data': None,
            'message': (
                f'🤖 {ai_answer}\n\n'
                '※ ERP 정형 데이터가 아닌 AI 자유 응답입니다.'
            )
        }
    except Exception as e:
        print(f'Potens AI 호출 실패: {e}')

    suggestions = get_suggestions(query)
    suggestion_text = ''
    if suggestions:
        suggestion_text = (
            '혹시 이런 질문을 하신 건가요?\n' +
            '\n'.join(f'- "{s}"' for s in suggestions) +
            '\n\n'
        )

    return {
        'type': 'text',
        'data': None,
        'message': (
            '질문을 더 구체적으로 해주시면 정확한 데이터를 찾아드리겠습니다.\n\n' +
            suggestion_text +
            '💡 질문 예시:\n'
            '- "3월과 4월 매출 비교해줘"\n'
            '- "4월 생산량 알려줘"\n'
            '- "불량의 주요 원인은?"\n'
            '- "생산부 출근율 보여줘"\n'
            '- "A-100 모델 생산 현황"'
        )
    }


# ---------- 질문 추천 ----------
def get_suggestions(query):
    templates = [
        '3월과 4월 매출 비교해줘',
        '4월 생산량 알려줘',
        '불량의 주요 원인은?',
        '생산부 출근율 보여줘',
        'A-100 모델 생산 현황',
        '이번 달 구매 발주 현황 알려줘',
        '부서별 인원 현황 보여줘',
        '전체 경영 현황 요약해줘'
    ]

    words = [w for w in query.split() if len(w) >= 2]
    suggestions = []

    for template in templates:
        if any(w in template for w in words):
            suggestions.append(template)
        if len(suggestions) >= 3:
            break

    return suggestions


# ---------- 응답별 신뢰도 표시 + 관련 메뉴 안내 ----------
MENU_GUIDE = {
    'financial': '재무관리 > 손익현황',
    'production': '생산관리 > 생산실적',
    'purchase': '구매관리 > 발주현황',
    'quality': '품질관리 > 검사현황',
    'quality_cause': '품질관리 > 불량원인분석',
    'hr': '인사관리 > 근태/부서현황',
    'comprehensive': '경영현황판 > 전체 요약'
}


def enrich_structured_response(result):
    footer = '✅ 사내 DB 기반 확정 데이터입니다.'
    menu = MENU_GUIDE.get(result.get('type'))
    if menu:
        footer += f'\n📁 관련 메뉴: {menu}'

    result['message'] = f"{result['message']}\n\n{footer}"
    return result


# ---------- 기간 추출 ----------
def extract_period(query):
    months = ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월']
    found_months = [m for m in months if m in query]

    if contains_keyword(query, ['최근', '이번주', '이번달']):
        return {'type': 'recent', 'value': None}
    if contains_keyword(query, ['지난', '전']):
        return {'type': 'past', 'value': None}
    if found_months:
        return {'type': 'specific', 'value': found_months}

    return {'type': 'all', 'value': None}


# ---------- 특정 항목 추출 ----------
def extract_specific_item(query):
    if 'a-100' in query or 'a100' in query:
        return 'A-100 모델'
    if 'b-200' in query or 'b200' in query:
        return 'B-200 모델'
    if 'c-300' in query or 'c300' in query:
        return 'C-300 모델'
    if 'd-400' in query or 'd400' in query:
        return 'D-400 모델'

    if '생산부' in query:
        return '생산부'
    if '영업부' in query:
        return '영업부'
    if '기술부' in query:
        return '기술부'
    if '관리부' in query:
        return '관리부'
    if '품질부' in query:
        return '품질부'

    if '외관' in query:
        return '외관 불량'
    if '치수' in query:
        return '치수 불량'
    if '기능' in query:
        return '기능 불량'
    if '포장' in query:
        return '포장 불량'

    return None


# ---------- 통계 유형 추출 ----------
def extract_stats_type(query):
    if contains_keyword(query, ['평균']):
        return 'average'
    if contains_keyword(query, ['최대', '가장 높', '제일 높', '가장 많']):
        return 'max'
    if contains_keyword(query, ['최소', '가장 낮', '제일 낮', '가장 적']):
        return 'min'
    if contains_keyword(query, ['합계', '총']):
        return 'sum'
    if contains_keyword(query, ['증가', '상승']):
        return 'increase'
    if contains_keyword(query, ['감소', '하락']):
        return 'decrease'
    if contains_keyword(query, ['추세', '트렌드']):
        return 'trend'

    return None


# ---------- 재무 질문 처리 ----------
def handle_financial_query(query, period, is_comparison, specific_item, stats_type):
    data = get_financial_data()
    message = ''
    processed_data = copy.deepcopy(data)

    if period['type'] == 'specific' and period['value']:
        processed_data['monthly'] = [m for m in data['monthly'] if m['month'] in period['value']]
        message += f"📅 {', '.join(period['value'])} 재무 데이터:\n\n"

        for m in processed_data['monthly']:
            message += f"[{m['month']}]\n"
            message += f"💰 매출: {format_number(m['revenue'])}원\n"
            message += f"💸 비용: {format_number(m['expense'])}원\n"
            message += f"📈 이익: {format_number(m['profit'])}원\n"
            message += f"📊 수익률: {(m['profit'] / m['revenue'] * 100):.1f}%\n\n"

    if is_comparison and len(processed_data['monthly']) >= 2:
        first = processed_data['monthly'][0]
        last = processed_data['monthly'][-1]
        revenue_diff = last['revenue'] - first['revenue']
        profit_diff = last['profit'] - first['profit']

        message += f"\n📊 비교 분석 ({first['month']} vs {last['month']}):\n"
        message += f"- 매출 변화: {format_number(abs(revenue_diff))}원 {'📈 증가' if revenue_diff > 0 else '📉 감소'} ({(revenue_diff / first['revenue'] * 100):.1f}%)\n"
        message += f"- 이익 변화: {format_number(abs(profit_diff))}원 {'📈 증가' if profit_diff > 0 else '📉 감소'} ({(profit_diff / first['profit'] * 100):.1f}%)\n"

        processed_data['comparison'] = {
            'revenueDiff': revenue_diff,
            'profitDiff': profit_diff,
            'revenuePercent': round(revenue_diff / first['revenue'] * 100, 2),
            'profitPercent': round(profit_diff / first['profit'] * 100, 2)
        }

    if stats_type:
        revenues = [m['revenue'] for m in processed_data['monthly']]
        profits = [m['profit'] for m in processed_data['monthly']]

        if stats_type == 'average':
            avg_revenue = sum(revenues) / len(revenues)
            avg_profit = sum(profits) / len(profits)
            message += f"\n📈 평균 데이터:\n"
            message += f"- 평균 매출: {format_number(round(avg_revenue))}원\n"
            message += f"- 평균 이익: {format_number(round(avg_profit))}원\n"
            processed_data['stats'] = {'avgRevenue': avg_revenue, 'avgProfit': avg_profit}

        elif stats_type == 'max':
            max_revenue = max(revenues)
            max_revenue_month = next(m for m in processed_data['monthly'] if m['revenue'] == max_revenue)
            message += f"\n🔝 최대 매출:\n"
            message += f"- {max_revenue_month['month']}: {format_number(max_revenue)}원\n"
            processed_data['highlight'] = max_revenue_month

        elif stats_type == 'min':
            min_revenue = min(revenues)
            min_revenue_month = next(m for m in processed_data['monthly'] if m['revenue'] == min_revenue)
            message += f"\n📉 최소 매출:\n"
            message += f"- {min_revenue_month['month']}: {format_number(min_revenue)}원\n"
            processed_data['highlight'] = min_revenue_month

        elif stats_type == 'sum':
            total_revenue = sum(revenues)
            total_profit = sum(profits)
            message += f"\n💰 총합:\n"
            message += f"- 총 매출: {format_number(total_revenue)}원\n"
            message += f"- 총 이익: {format_number(total_profit)}원\n"

        elif stats_type == 'trend':
            is_increasing = revenues[-1] > revenues[0]
            message += f"\n📊 추세 분석:\n"
            message += f"- 전반적으로 {'📈 증가' if is_increasing else '📉 감소'} 추세입니다.\n"

    if not message:
        message = '재무 현황을 조회했습니다.'

    return {
        'type': 'financial',
        'data': processed_data,
        'message': message,
        'query': query
    }


# ---------- 생산 질문 처리 ----------
def handle_production_query(query, period, is_comparison, specific_item, stats_type):
    data = get_production_data()
    message = ''
    processed_data = copy.deepcopy(data)

    if period['type'] == 'specific' and period['value']:
        processed_data['monthly'] = [m for m in data['monthly'] if m['month'] in period['value']]
        message += f"📅 {', '.join(period['value'])} 생산 데이터:\n\n"

        for m in processed_data['monthly']:
            message += f"[{m['month']}]\n"
            message += f"🏭 총 생산량: {format_number(m['totalProduction'])}개\n"
            message += f"✅ 양품: {format_number(m['goodProducts'])}개\n"
            message += f"❌ 불량품: {format_number(m['defectProducts'])}개\n"
            message += f"📊 불량률: {m['defectRate']}%\n"
            message += f"⚡ 가동률: {m['efficiency']}%\n\n"

    if is_comparison and processed_data.get('monthly') and len(processed_data['monthly']) >= 2:
        first = processed_data['monthly'][0]
        last = processed_data['monthly'][-1]
        prod_diff = last['totalProduction'] - first['totalProduction']
        eff_diff = last['efficiency'] - first['efficiency']

        message += f"\n📊 비교 분석 ({first['month']} vs {last['month']}):\n"
        message += f"- 생산량 변화: {format_number(abs(prod_diff))}개 {'📈 증가' if prod_diff > 0 else '📉 감소'} ({(prod_diff / first['totalProduction'] * 100):.1f}%)\n"
        message += f"- 가동률 변화: {abs(eff_diff):.1f}% {'📈 향상' if eff_diff > 0 else '📉 하락'}\n"
        message += f"- 불량률: {first['defectRate']}% → {last['defectRate']}% ({'⚠️ 증가' if last['defectRate'] > first['defectRate'] else '✅ 감소'})\n"

    if specific_item:
        processed_data['products'] = [p for p in data['products'] if p['name'] == specific_item]
        if processed_data['products']:
            product = processed_data['products'][0]
            message += f"\n🏷️ {specific_item} 상세 정보:\n"
            message += f"- 생산량: {format_number(product['quantity'])}개\n"
            message += f"- 목표량: {format_number(product['target'])}개\n"
            message += f"- 달성률: {product['rate']}%\n"
            message += f"- 목표 달성까지: {format_number(product['target'] - product['quantity'])}개 남음\n"

            if product['rate'] >= 95:
                message += "\n✅ 목표 달성률이 우수합니다!"
            elif product['rate'] < 90:
                message += "\n⚠️ 목표 달성률이 낮습니다. 생산 증대가 필요합니다."

    if stats_type and not specific_item:
        quantities = [p['quantity'] for p in processed_data['products']]
        rates = [p['rate'] for p in processed_data['products']]

        if stats_type == 'max':
            max_qty = max(quantities)
            max_product = next(p for p in processed_data['products'] if p['quantity'] == max_qty)
            message += f"\n🏆 최다 생산 제품:\n"
            message += f"- {max_product['name']}: {format_number(max_product['quantity'])}개\n"
            message += f"- 목표 달성률: {max_product['rate']}%\n"
            processed_data['highlight'] = max_product

        elif stats_type == 'min':
            min_qty = min(quantities)
            min_product = next(p for p in processed_data['products'] if p['quantity'] == min_qty)
            message += f"\n⚠️ 최소 생산 제품:\n"
            message += f"- {min_product['name']}: {format_number(min_product['quantity'])}개\n"
            message += f"- 목표 달성률: {min_product['rate']}%\n"
            message += "- 생산 증대가 필요합니다.\n"
            processed_data['highlight'] = min_product

        elif stats_type == 'average':
            avg_qty = sum(quantities) / len(quantities)
            avg_rate = sum(rates) / len(rates)
            message += f"\n📊 평균 생산 데이터:\n"
            message += f"- 평균 생산량: {format_number(round(avg_qty))}개\n"
            message += f"- 평균 달성률: {avg_rate:.1f}%\n"

        elif stats_type == 'sum':
            total_qty = sum(quantities)
            message += f"\n💰 총 생산량: {format_number(total_qty)}개\n"

    if not message:
        message = '생산 현황을 조회했습니다.'

    return {
        'type': 'production',
        'data': processed_data,
        'message': message,
        'query': query
    }


# ---------- 구매 질문 처리 ----------
def handle_purchase_query(query, period, is_comparison, specific_item, stats_type):
    data = get_purchase_data()
    message = ''
    processed_data = copy.deepcopy(data)

    if '완료' in query:
        processed_data['orders'] = [o for o in data['orders'] if o['status'] == '완료']
        message += f"✅ 완료된 발주: {len(processed_data['orders'])}건\n\n"
    elif '진행' in query or '대기' in query:
        processed_data['orders'] = [o for o in data['orders'] if o['status'] != '완료']
        message += f"⏳ 진행중/대기 발주: {len(processed_data['orders'])}건\n\n"

    if stats_type:
        amounts = [o['amount'] for o in processed_data['orders']]

        if stats_type == 'max':
            max_amount = max(amounts)
            max_order = next(o for o in processed_data['orders'] if o['amount'] == max_amount)
            message += f"\n💰 최대 발주:\n"
            message += f"- 공급업체: {max_order['supplier']}\n"
            message += f"- 품목: {max_order['item']}\n"
            message += f"- 금액: {format_number(max_amount)}원\n"
            message += f"- 상태: {max_order['status']}\n"
            processed_data['highlight'] = max_order

        elif stats_type == 'sum':
            total_amount = sum(amounts)
            message += f"\n📊 총 발주 금액: {format_number(total_amount)}원\n"
            message += f"- 발주 건수: {len(processed_data['orders'])}건\n"
            message += f"- 평균 발주액: {format_number(round(total_amount / len(processed_data['orders'])))}원\n"

        elif stats_type == 'average':
            avg_amount = sum(amounts) / len(amounts)
            message += f"\n📊 평균 발주 금액: {format_number(round(avg_amount))}원\n"

    if not message:
        message = '구매 현황을 조회했습니다.'

    return {
        'type': 'purchase',
        'data': processed_data,
        'message': message,
        'query': query
    }


# ---------- 품질 질문 처리 ----------
def handle_quality_query(query, period, is_comparison, specific_item, stats_type, is_cause_analysis):
    data = get_quality_data()
    message = ''
    processed_data = copy.deepcopy(data)

    if is_cause_analysis:
        message += "🔍 불량 원인 분석:\n\n"

        max_defect = max(data['defectTypes'], key=lambda d: d['count'])

        message += f"📊 주요 불량 유형: {max_defect['type']} ({max_defect['count']}건, {max_defect['rate']}%)\n\n"

        processed_data['causeAnalysis'] = {
            'mainDefect': max_defect['type'],
            'causes': []
        }

        if max_defect['type'] == '외관 불량':
            message += "💡 외관 불량 주요 원인:\n"
            message += "1. 작업자 숙련도 부족 (35%)\n"
            message += "2. 원자재 품질 문제 (28%)\n"
            message += "3. 설비 노후화 (22%)\n"
            message += "4. 작업 환경 (15%)\n\n"
            message += "✅ 개선 방안:\n"
            message += "- 작업자 교육 강화\n"
            message += "- 원자재 입고 검사 강화\n"
            message += "- 설비 정기 점검 및 교체\n"

            processed_data['causeAnalysis']['causes'] = [
                {'cause': '작업자 숙련도 부족', 'percent': 35},
                {'cause': '원자재 품질 문제', 'percent': 28},
                {'cause': '설비 노후화', 'percent': 22},
                {'cause': '작업 환경', 'percent': 15}
            ]
        elif max_defect['type'] == '치수 불량':
            message += "💡 치수 불량 주요 원인:\n"
            message += "1. 설비 캘리브레이션 오차 (42%)\n"
            message += "2. 온습도 변화 (28%)\n"
            message += "3. 측정 기구 오차 (20%)\n"
            message += "4. 원자재 변형 (10%)\n\n"
            message += "✅ 개선 방안:\n"
            message += "- 설비 정밀 캘리브레이션\n"
            message += "- 작업장 온습도 관리\n"
            message += "- 측정 기구 정기 교정\n"

            processed_data['causeAnalysis']['causes'] = [
                {'cause': '설비 캘리브레이션 오차', 'percent': 42},
                {'cause': '온습도 변화', 'percent': 28},
                {'cause': '측정 기구 오차', 'percent': 20},
                {'cause': '원자재 변형', 'percent': 10}
            ]
        elif max_defect['type'] == '기능 불량':
            message += "💡 기능 불량 주요 원인:\n"
            message += "1. 부품 조립 불량 (38%)\n"
            message += "2. 전기적 결함 (32%)\n"
            message += "3. 소프트웨어 오류 (20%)\n"
            message += "4. 부품 호환성 (10%)\n\n"
            message += "✅ 개선 방안:\n"
            message += "- 조립 공정 표준화\n"
            message += "- 전기 검사 강화\n"
            message += "- 소프트웨어 테스트 강화\n"

            processed_data['causeAnalysis']['causes'] = [
                {'cause': '부품 조립 불량', 'percent': 38},
                {'cause': '전기적 결함', 'percent': 32},
                {'cause': '소프트웨어 오류', 'percent': 20},
                {'cause': '부품 호환성', 'percent': 10}
            ]
        else:
            message += "💡 포장 불량 주요 원인:\n"
            message += "1. 포장 작업 미숙 (45%)\n"
            message += "2. 포장재 품질 (30%)\n"
            message += "3. 물류 과정 손상 (15%)\n"
            message += "4. 포장 설비 문제 (10%)\n\n"
            message += "✅ 개선 방안:\n"
            message += "- 포장 작업 교육\n"
            message += "- 고품질 포장재 사용\n"
            message += "- 물류 프로세스 개선\n"

            processed_data['causeAnalysis']['causes'] = [
                {'cause': '포장 작업 미숙', 'percent': 45},
                {'cause': '포장재 품질', 'percent': 30},
                {'cause': '물류 과정 손상', 'percent': 15},
                {'cause': '포장 설비 문제', 'percent': 10}
            ]

        return {
            'type': 'quality_cause',
            'data': processed_data,
            'message': message,
            'query': query
        }

    if specific_item:
        processed_data['defectTypes'] = [d for d in data['defectTypes'] if d['type'] == specific_item]
        if processed_data['defectTypes']:
            defect = processed_data['defectTypes'][0]
            message += f"📋 {specific_item} 분석:\n"
            message += f"- 발생 건수: {defect['count']}건\n"
            message += f"- 전체 불량 중 비율: {defect['rate']}%\n"
            message += f"- 총 검사 대비: {(defect['count'] / data['summary']['totalInspections'] * 100):.2f}%\n"

    if stats_type and not specific_item:
        counts = [d['count'] for d in processed_data['defectTypes']]

        if stats_type == 'max':
            max_count = max(counts)
            max_defect = next(d for d in processed_data['defectTypes'] if d['count'] == max_count)
            message += f"\n⚠️ 가장 많은 불량 유형:\n"
            message += f"- {max_defect['type']}: {max_defect['count']}건 ({max_defect['rate']}%)\n"
            message += "- ⚡ 우선 개선이 필요합니다!\n"
            processed_data['highlight'] = max_defect

        elif stats_type == 'min':
            min_count = min(counts)
            min_defect = next(d for d in processed_data['defectTypes'] if d['count'] == min_count)
            message += f"\n✅ 가장 적은 불량 유형:\n"
            message += f"- {min_defect['type']}: {min_defect['count']}건 ({min_defect['rate']}%)\n"
            message += "- 관리가 잘 되고 있습니다.\n"
            processed_data['highlight'] = min_defect

        elif stats_type == 'sum':
            total_defects = sum(counts)
            message += f"\n📊 총 불량 건수: {total_defects}건\n"
            message += f"- 전체 검사 대비: {(total_defects / data['summary']['totalInspections'] * 100):.2f}%\n"

    if '합격률' in query or '불량률' in query:
        message += f"\n📊 품질 지표:\n"
        message += f"- ✅ 합격률: {data['summary']['passRate']}%\n"
        message += f"- ❌ 불량률: {(100 - data['summary']['passRate']):.1f}%\n"
        message += f"- 📋 총 검사: {format_number(data['summary']['totalInspections'])}건\n"
        message += f"- ⚠️ 총 불량: {data['summary']['defectCount']}건\n"

    if not message:
        message = '품질 현황을 조회했습니다.'

    return {
        'type': 'quality',
        'data': processed_data,
        'message': message,
        'query': query
    }


# ---------- 인사 질문 처리 ----------
def handle_hr_query(query, period, is_comparison, specific_item, stats_type):
    data = get_hr_data()
    message = ''
    processed_data = copy.deepcopy(data)

    if specific_item:
        processed_data['departments'] = [d for d in data['departments'] if d['name'] == specific_item]
        if processed_data['departments']:
            dept = processed_data['departments'][0]
            message += f"👥 {specific_item} 상세 정보:\n"
            message += f"- 인원: {dept['employees']}명\n"
            message += f"- 출근율: {dept['attendance']}%\n"
            message += f"- 전체 직원 대비: {(dept['employees'] / data['summary']['totalEmployees'] * 100):.1f}%\n"

            if dept['attendance'] >= 97:
                message += "\n✅ 출근율이 우수합니다!"
            elif dept['attendance'] < 96:
                message += "\n⚠️ 출근율 관리가 필요합니다."

    if stats_type and not specific_item:
        employees = [d['employees'] for d in processed_data['departments']]
        attendances = [d['attendance'] for d in processed_data['departments']]

        if stats_type == 'max':
            if '인원' in query:
                max_emp = max(employees)
                max_dept = next(d for d in processed_data['departments'] if d['employees'] == max_emp)
                message += f"\n👥 최대 인원 부서:\n"
                message += f"- {max_dept['name']}: {max_dept['employees']}명\n"
                message += f"- 전체의 {(max_dept['employees'] / data['summary']['totalEmployees'] * 100):.1f}%\n"
                processed_data['highlight'] = max_dept
            else:
                max_att = max(attendances)
                max_dept = next(d for d in processed_data['departments'] if d['attendance'] == max_att)
                message += f"\n⭐ 최고 출근율 부서:\n"
                message += f"- {max_dept['name']}: {max_dept['attendance']}%\n"
                message += f"- 인원: {max_dept['employees']}명\n"
                processed_data['highlight'] = max_dept

        elif stats_type == 'min':
            if '인원' in query:
                min_emp = min(employees)
                min_dept = next(d for d in processed_data['departments'] if d['employees'] == min_emp)
                message += f"\n👥 최소 인원 부서:\n"
                message += f"- {min_dept['name']}: {min_dept['employees']}명\n"
                processed_data['highlight'] = min_dept
            else:
                min_att = min(attendances)
                min_dept = next(d for d in processed_data['departments'] if d['attendance'] == min_att)
                message += f"\n⚠️ 최저 출근율 부서:\n"
                message += f"- {min_dept['name']}: {min_dept['attendance']}%\n"
                message += "- 관리가 필요합니다.\n"
                processed_data['highlight'] = min_dept

        elif stats_type == 'average':
            avg_emp = sum(employees) / len(employees)
            avg_att = sum(attendances) / len(attendances)
            message += f"\n📊 부서별 평균:\n"
            message += f"- 평균 인원: {round(avg_emp)}명\n"
            message += f"- 평균 출근율: {avg_att:.1f}%\n"

        elif stats_type == 'sum':
            total_emp = sum(employees)
            message += f"\n👥 총 직원 수: {total_emp}명\n"

    if '입사' in query or '퇴사' in query or '이직' in query:
        message += f"\n📋 인력 변동 현황:\n"
        message += f"- 신규 입사: {data['summary']['newHires']}명\n"
        message += f"- 퇴사자: {data['summary']['resignations']}명\n"
        net_change = data['summary']['newHires'] - data['summary']['resignations']
        message += f"- 순증감: {'+' if net_change > 0 else ''}{net_change}명\n"
        message += f"- 이직률: {(data['summary']['resignations'] / data['summary']['totalEmployees'] * 100):.2f}%\n"

    if not message:
        message = '인사 현황을 조회했습니다.'

    return {
        'type': 'hr',
        'data': processed_data,
        'message': message,
        'query': query
    }


# ---------- 종합 질문 처리 ----------
def handle_comprehensive_query(query):
    return {
        'type': 'comprehensive',
        'data': {
            'financial': get_financial_data()['summary'],
            'production': get_production_data()['summary'],
            'purchase': get_purchase_data()['summary'],
            'quality': get_quality_data()['summary'],
            'hr': get_hr_data()['summary']
        },
        'message': '전체 경영 현황을 조회했습니다.',
        'query': query
    }


# ---------- 숫자 포맷팅 ----------
def format_number(num):
    return f"{num:,}"


# ---------- 재무 데이터 ----------
def get_financial_data():
    return {
        'summary': {
            'totalRevenue': 15800000000,
            'totalExpense': 12300000000,
            'netProfit': 3500000000,
            'profitRate': 22.15
        },
        'monthly': [
            {'month': '1월', 'revenue': 1200000000, 'expense': 950000000, 'profit': 250000000},
            {'month': '2월', 'revenue': 1350000000, 'expense': 1050000000, 'profit': 300000000},
            {'month': '3월', 'revenue': 1280000000, 'expense': 1020000000, 'profit': 260000000},
            {'month': '4월', 'revenue': 1420000000, 'expense': 1100000000, 'profit': 320000000},
            {'month': '5월', 'revenue': 1380000000, 'expense': 1080000000, 'profit': 300000000},
            {'month': '6월', 'revenue': 1470000000, 'expense': 1150000000, 'profit': 320000000}
        ]
    }


# ---------- 생산 데이터 ----------
def get_production_data():
    return {
        'summary': {
            'totalProduction': 125000,
            'defectRate': 1.8,
            'efficiency': 94.5
        },
        'monthly': [
            {'month': '1월', 'totalProduction': 19500, 'goodProducts': 19140, 'defectProducts': 360, 'defectRate': 1.85, 'efficiency': 93.2},
            {'month': '2월', 'totalProduction': 20200, 'goodProducts': 19838, 'defectProducts': 362, 'defectRate': 1.79, 'efficiency': 94.1},
            {'month': '3월', 'totalProduction': 20800, 'goodProducts': 20426, 'defectProducts': 374, 'defectRate': 1.80, 'efficiency': 94.8},
            {'month': '4월', 'totalProduction': 21500, 'goodProducts': 21115, 'defectProducts': 385, 'defectRate': 1.79, 'efficiency': 95.2},
            {'month': '5월', 'totalProduction': 21200, 'goodProducts': 20828, 'defectProducts': 372, 'defectRate': 1.75, 'efficiency': 94.6},
            {'month': '6월', 'totalProduction': 21800, 'goodProducts': 21404, 'defectProducts': 396, 'defectRate': 1.82, 'efficiency': 95.4}
        ],
        'products': [
            {'name': 'A-100 모델', 'quantity': 35000, 'target': 40000, 'rate': 87.5},
            {'name': 'B-200 모델', 'quantity': 42000, 'target': 45000, 'rate': 93.3},
            {'name': 'C-300 모델', 'quantity': 28000, 'target': 30000, 'rate': 93.3},
            {'name': 'D-400 모델', 'quantity': 20000, 'target': 22000, 'rate': 90.9}
        ],
        'daily': [
            {'date': '2026-07-10', 'production': 2100, 'defect': 38},
            {'date': '2026-07-11', 'production': 2250, 'defect': 41},
            {'date': '2026-07-12', 'production': 2180, 'defect': 35},
            {'date': '2026-07-13', 'production': 2300, 'defect': 42},
            {'date': '2026-07-14', 'production': 2150, 'defect': 39}
        ]
    }


# ---------- 구매 데이터 ----------
def get_purchase_data():
    return {
        'summary': {
            'totalOrders': 245,
            'totalAmount': 4800000000,
            'pendingOrders': 18
        },
        'orders': [
            {'supplier': '(주)대한소재', 'item': '철강 원자재', 'amount': 850000000, 'status': '완료'},
            {'supplier': '글로벌부품', 'item': '전자부품 세트', 'amount': 620000000, 'status': '진행중'},
            {'supplier': '한국화학', 'item': '산업용 화학제', 'amount': 450000000, 'status': '완료'},
            {'supplier': '프리미엄자재', 'item': '특수 합금', 'amount': 720000000, 'status': '대기'},
            {'supplier': '스마트부품상사', 'item': 'PCB 기판', 'amount': 380000000, 'status': '완료'}
        ]
    }


# ---------- 품질 데이터 ----------
def get_quality_data():
    return {
        'summary': {
            'totalInspections': 8500,
            'passRate': 98.2,
            'defectCount': 153
        },
        'defectTypes': [
            {'type': '외관 불량', 'count': 62, 'rate': 40.5},
            {'type': '치수 불량', 'count': 38, 'rate': 24.8},
            {'type': '기능 불량', 'count': 28, 'rate': 18.3},
            {'type': '포장 불량', 'count': 25, 'rate': 16.4}
        ],
        'inspections': [
            {'date': '2026-07-10', 'total': 1700, 'pass': 1668, 'fail': 32},
            {'date': '2026-07-11', 'total': 1750, 'pass': 1719, 'fail': 31},
            {'date': '2026-07-12', 'total': 1680, 'pass': 1651, 'fail': 29},
            {'date': '2026-07-13', 'total': 1800, 'pass': 1767, 'fail': 33},
            {'date': '2026-07-14', 'total': 1570, 'pass': 1542, 'fail': 28}
        ]
    }


# ---------- 인사 데이터 ----------
def get_hr_data():
    return {
        'summary': {
            'totalEmployees': 485,
            'newHires': 12,
            'resignations': 5,
            'avgAttendance': 96.8
        },
        'departments': [
            {'name': '생산부', 'employees': 180, 'attendance': 97.2},
            {'name': '영업부', 'employees': 85, 'attendance': 95.8},
            {'name': '기술부', 'employees': 95, 'attendance': 96.5},
            {'name': '관리부', 'employees': 65, 'attendance': 97.8},
            {'name': '품질부', 'employees': 60, 'attendance': 98.1}
        ],
        'attendance': [
            {'date': '2026-07-10', 'present': 472, 'absent': 8, 'leave': 5},
            {'date': '2026-07-11', 'present': 468, 'absent': 10, 'leave': 7},
            {'date': '2026-07-12', 'present': 475, 'absent': 6, 'leave': 4},
            {'date': '2026-07-13', 'present': 470, 'absent': 9, 'leave': 6},
            {'date': '2026-07-14', 'present': 473, 'absent': 7, 'leave': 5}
        ]
    }


# ---------- 카테고리별 데이터 조회 ----------
@app.route('/api/category/<category>', methods=['GET'])
def get_category_data_route(category):
    return jsonify(get_category_data(category))


def get_category_data(category):
    if category == 'financial':
        return {'type': 'financial', 'data': get_financial_data(), 'message': '재무 현황입니다.'}
    if category == 'production':
        return {'type': 'production', 'data': get_production_data(), 'message': '생산 현황입니다.'}
    if category == 'purchase':
        return {'type': 'purchase', 'data': get_purchase_data(), 'message': '구매 현황입니다.'}
    if category == 'quality':
        return {'type': 'quality', 'data': get_quality_data(), 'message': '품질 현황입니다.'}
    if category == 'hr':
        return {'type': 'hr', 'data': get_hr_data(), 'message': '인사 현황입니다.'}
    return {'type': 'text', 'data': None, 'message': '데이터를 찾을 수 없습니다.'}


if __name__ == '__main__':
    import os
    app.run(debug=True, port=int(os.environ.get('PORT', 5000)))
