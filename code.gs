// 웹 앱 실행 함수
function doGet() {
  return HtmlService.createHtmlOutputFromFile('Index')
    .setTitle('SB선보 ERP 시스템')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

// AI 챗봇 응답 처리 함수 (대폭 개선)
function processAIQuery(userQuery) {
  const query = userQuery.toLowerCase();
  
  // 기간 분석
  const period = extractPeriod(query);
  
  // 비교 요청 분석
  const isComparison = query.includes('비교') || query.includes('차이') || query.includes('대비');
  
  // 특정 항목 요청 분석
  const specificItem = extractSpecificItem(query);
  
  // 통계 요청 분석
  const statsType = extractStatsType(query);
  
  // 원인 분석 요청
  const isCauseAnalysis = query.includes('원인') || query.includes('이유') || query.includes('왜');
  
  // 재무 관련 질문
  if (query.includes('재무') || query.includes('매출') || query.includes('수익') || query.includes('손익') || query.includes('이익')) {
    return handleFinancialQuery(query, period, isComparison, specificItem, statsType);
  }
  
  // 생산 관련 질문
  if (query.includes('생산') || query.includes('제품') || query.includes('생산량') || query.includes('공장')) {
    return handleProductionQuery(query, period, isComparison, specificItem, statsType);
  }
  
  // 구매 관련 질문
  if (query.includes('구매') || query.includes('발주') || query.includes('자재') || query.includes('공급')) {
    return handlePurchaseQuery(query, period, isComparison, specificItem, statsType);
  }
  
  // 품질 관련 질문
  if (query.includes('품질') || query.includes('불량') || query.includes('검사') || query.includes('합격')) {
    return handleQualityQuery(query, period, isComparison, specificItem, statsType, isCauseAnalysis);
  }
  
  // 인사 관련 질문
  if (query.includes('인사') || query.includes('직원') || query.includes('사원') || query.includes('근태') || query.includes('부서')) {
    return handleHRQuery(query, period, isComparison, specificItem, statsType);
  }
  
  // 복합 질문 (여러 카테고리)
  if (query.includes('전체') || query.includes('모든') || query.includes('종합')) {
    return handleComprehensiveQuery(query);
  }
  
  // 기본 응답
  return {
    type: 'text',
    data: null,
    message: '질문을 더 구체적으로 해주시면 정확한 데이터를 찾아드리겠습니다.\n\n💡 질문 예시:\n- "3월과 4월 매출 비교해줘"\n- "4월 생산량 알려줘"\n- "불량의 주요 원인은?"\n- "생산부 출근율 보여줘"\n- "A-100 모델 생산 현황"'
  };
}

// 기간 추출
function extractPeriod(query) {
  const months = ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월'];
  const foundMonths = months.filter(m => query.includes(m));
  
  if (query.includes('최근') || query.includes('이번주') || query.includes('이번달')) {
    return { type: 'recent', value: null };
  }
  if (query.includes('지난') || query.includes('전')) {
    return { type: 'past', value: null };
  }
  if (foundMonths.length > 0) {
    return { type: 'specific', value: foundMonths };
  }
  
  return { type: 'all', value: null };
}

// 특정 항목 추출
function extractSpecificItem(query) {
  // 제품명
  if (query.includes('a-100') || query.includes('a100')) return 'A-100 모델';
  if (query.includes('b-200') || query.includes('b200')) return 'B-200 모델';
  if (query.includes('c-300') || query.includes('c300')) return 'C-300 모델';
  if (query.includes('d-400') || query.includes('d400')) return 'D-400 모델';
  
  // 부서명
  if (query.includes('생산부')) return '생산부';
  if (query.includes('영업부')) return '영업부';
  if (query.includes('기술부')) return '기술부';
  if (query.includes('관리부')) return '관리부';
  if (query.includes('품질부')) return '품질부';
  
  // 불량 유형
  if (query.includes('외관')) return '외관 불량';
  if (query.includes('치수')) return '치수 불량';
  if (query.includes('기능')) return '기능 불량';
  if (query.includes('포장')) return '포장 불량';
  
  return null;
}

// 통계 유형 추출
function extractStatsType(query) {
  if (query.includes('평균')) return 'average';
  if (query.includes('최대') || query.includes('가장 높') || query.includes('제일 높') || query.includes('가장 많')) return 'max';
  if (query.includes('최소') || query.includes('가장 낮') || query.includes('제일 낮') || query.includes('가장 적')) return 'min';
  if (query.includes('합계') || query.includes('총')) return 'sum';
  if (query.includes('증가') || query.includes('상승')) return 'increase';
  if (query.includes('감소') || query.includes('하락')) return 'decrease';
  if (query.includes('추세') || query.includes('트렌드')) return 'trend';
  
  return null;
}

// 재무 질문 처리
function handleFinancialQuery(query, period, isComparison, specificItem, statsType) {
  const data = getFinancialData();
  let message = '';
  let processedData = JSON.parse(JSON.stringify(data)); // 깊은 복사
  
  // 기간 필터링
  if (period.type === 'specific' && period.value && period.value.length > 0) {
    processedData.monthly = data.monthly.filter(m => period.value.includes(m.month));
    message += `📅 ${period.value.join(', ')} 재무 데이터:\n\n`;
    
    processedData.monthly.forEach(m => {
      message += `[${m.month}]\n`;
      message += `💰 매출: ${formatNumber(m.revenue)}원\n`;
      message += `💸 비용: ${formatNumber(m.expense)}원\n`;
      message += `📈 이익: ${formatNumber(m.profit)}원\n`;
      message += `📊 수익률: ${((m.profit/m.revenue)*100).toFixed(1)}%\n\n`;
    });
  }
  
  // 비교 분석
  if (isComparison && processedData.monthly.length >= 2) {
    const first = processedData.monthly[0];
    const last = processedData.monthly[processedData.monthly.length - 1];
    const revenueDiff = last.revenue - first.revenue;
    const profitDiff = last.profit - first.profit;
    
    message += `\n📊 비교 분석 (${first.month} vs ${last.month}):\n`;
    message += `- 매출 변화: ${formatNumber(Math.abs(revenueDiff))}원 ${revenueDiff > 0 ? '📈 증가' : '📉 감소'} (${((revenueDiff/first.revenue)*100).toFixed(1)}%)\n`;
    message += `- 이익 변화: ${formatNumber(Math.abs(profitDiff))}원 ${profitDiff > 0 ? '📈 증가' : '📉 감소'} (${((profitDiff/first.profit)*100).toFixed(1)}%)\n`;
    
    processedData.comparison = {
      revenueDiff: revenueDiff,
      profitDiff: profitDiff,
      revenuePercent: ((revenueDiff / first.revenue) * 100).toFixed(2),
      profitPercent: ((profitDiff / first.profit) * 100).toFixed(2)
    };
  }
  
  // 통계 분석
  if (statsType) {
    const revenues = processedData.monthly.map(m => m.revenue);
    const profits = processedData.monthly.map(m => m.profit);
    
    switch(statsType) {
      case 'average':
        const avgRevenue = revenues.reduce((a,b) => a+b, 0) / revenues.length;
        const avgProfit = profits.reduce((a,b) => a+b, 0) / profits.length;
        message += `\n📈 평균 데이터:\n`;
        message += `- 평균 매출: ${formatNumber(Math.round(avgRevenue))}원\n`;
        message += `- 평균 이익: ${formatNumber(Math.round(avgProfit))}원\n`;
        processedData.stats = { avgRevenue, avgProfit };
        break;
        
      case 'max':
        const maxRevenue = Math.max(...revenues);
        const maxRevenueMonth = processedData.monthly.find(m => m.revenue === maxRevenue);
        message += `\n🔝 최대 매출:\n`;
        message += `- ${maxRevenueMonth.month}: ${formatNumber(maxRevenue)}원\n`;
        processedData.highlight = maxRevenueMonth;
        break;
        
      case 'min':
        const minRevenue = Math.min(...revenues);
        const minRevenueMonth = processedData.monthly.find(m => m.revenue === minRevenue);
        message += `\n📉 최소 매출:\n`;
        message += `- ${minRevenueMonth.month}: ${formatNumber(minRevenue)}원\n`;
        processedData.highlight = minRevenueMonth;
        break;
        
      case 'sum':
        const totalRevenue = revenues.reduce((a,b) => a+b, 0);
        const totalProfit = profits.reduce((a,b) => a+b, 0);
        message += `\n💰 총합:\n`;
        message += `- 총 매출: ${formatNumber(totalRevenue)}원\n`;
        message += `- 총 이익: ${formatNumber(totalProfit)}원\n`;
        break;
        
      case 'trend':
        const isIncreasing = revenues[revenues.length-1] > revenues[0];
        message += `\n📊 추세 분석:\n`;
        message += `- 전반적으로 ${isIncreasing ? '📈 증가' : '📉 감소'} 추세입니다.\n`;
        break;
    }
  }
  
  if (!message) {
    message = '재무 현황을 조회했습니다.';
  }
  
  return {
    type: 'financial',
    data: processedData,
    message: message,
    query: query
  };
}

// 생산 질문 처리 (월별 데이터 추가)
function handleProductionQuery(query, period, isComparison, specificItem, statsType) {
  const data = getProductionData();
  let message = '';
  let processedData = JSON.parse(JSON.stringify(data));
  
  // 월별 생산량 필터링
  if (period.type === 'specific' && period.value && period.value.length > 0) {
    processedData.monthly = data.monthly.filter(m => period.value.includes(m.month));
    message += `📅 ${period.value.join(', ')} 생산 데이터:\n\n`;
    
    processedData.monthly.forEach(m => {
      message += `[${m.month}]\n`;
      message += `🏭 총 생산량: ${formatNumber(m.totalProduction)}개\n`;
      message += `✅ 양품: ${formatNumber(m.goodProducts)}개\n`;
      message += `❌ 불량품: ${formatNumber(m.defectProducts)}개\n`;
      message += `📊 불량률: ${m.defectRate}%\n`;
      message += `⚡ 가동률: ${m.efficiency}%\n\n`;
    });
  }
  
  // 비교 분석
  if (isComparison && processedData.monthly && processedData.monthly.length >= 2) {
    const first = processedData.monthly[0];
    const last = processedData.monthly[processedData.monthly.length - 1];
    const prodDiff = last.totalProduction - first.totalProduction;
    const effDiff = last.efficiency - first.efficiency;
    
    message += `\n📊 비교 분석 (${first.month} vs ${last.month}):\n`;
    message += `- 생산량 변화: ${formatNumber(Math.abs(prodDiff))}개 ${prodDiff > 0 ? '📈 증가' : '📉 감소'} (${((prodDiff/first.totalProduction)*100).toFixed(1)}%)\n`;
    message += `- 가동률 변화: ${Math.abs(effDiff).toFixed(1)}% ${effDiff > 0 ? '📈 향상' : '📉 하락'}\n`;
    message += `- 불량률: ${first.defectRate}% → ${last.defectRate}% (${last.defectRate > first.defectRate ? '⚠️ 증가' : '✅ 감소'})\n`;
  }
  
  // 특정 제품 필터링
  if (specificItem) {
    processedData.products = data.products.filter(p => p.name === specificItem);
    if (processedData.products.length > 0) {
      const product = processedData.products[0];
      message += `\n🏷️ ${specificItem} 상세 정보:\n`;
      message += `- 생산량: ${formatNumber(product.quantity)}개\n`;
      message += `- 목표량: ${formatNumber(product.target)}개\n`;
      message += `- 달성률: ${product.rate}%\n`;
      message += `- 목표 달성까지: ${formatNumber(product.target - product.quantity)}개 남음\n`;
      
      if (product.rate >= 95) {
        message += `\n✅ 목표 달성률이 우수합니다!`;
      } else if (product.rate < 90) {
        message += `\n⚠️ 목표 달성률이 낮습니다. 생산 증대가 필요합니다.`;
      }
    }
  }
  
  // 통계 분석
  if (statsType && !specificItem) {
    const quantities = processedData.products.map(p => p.quantity);
    const rates = processedData.products.map(p => p.rate);
    
    switch(statsType) {
      case 'max':
        const maxQty = Math.max(...quantities);
        const maxProduct = processedData.products.find(p => p.quantity === maxQty);
        message += `\n🏆 최다 생산 제품:\n`;
        message += `- ${maxProduct.name}: ${formatNumber(maxProduct.quantity)}개\n`;
        message += `- 목표 달성률: ${maxProduct.rate}%\n`;
        processedData.highlight = maxProduct;
        break;
        
      case 'min':
        const minQty = Math.min(...quantities);
        const minProduct = processedData.products.find(p => p.quantity === minQty);
        message += `\n⚠️ 최소 생산 제품:\n`;
        message += `- ${minProduct.name}: ${formatNumber(minProduct.quantity)}개\n`;
        message += `- 목표 달성률: ${minProduct.rate}%\n`;
        message += `- 생산 증대가 필요합니다.\n`;
        processedData.highlight = minProduct;
        break;
        
      case 'average':
        const avgQty = quantities.reduce((a,b) => a+b, 0) / quantities.length;
        const avgRate = rates.reduce((a,b) => a+b, 0) / rates.length;
        message += `\n📊 평균 생산 데이터:\n`;
        message += `- 평균 생산량: ${formatNumber(Math.round(avgQty))}개\n`;
        message += `- 평균 달성률: ${avgRate.toFixed(1)}%\n`;
        break;
        
      case 'sum':
        const totalQty = quantities.reduce((a,b) => a+b, 0);
        message += `\n💰 총 생산량: ${formatNumber(totalQty)}개\n`;
        break;
    }
  }
  
  if (!message) {
    message = '생산 현황을 조회했습니다.';
  }
  
  return {
    type: 'production',
    data: processedData,
    message: message,
    query: query
  };
}

// 구매 질문 처리
function handlePurchaseQuery(query, period, isComparison, specificItem, statsType) {
  const data = getPurchaseData();
  let message = '';
  let processedData = JSON.parse(JSON.stringify(data));
  
  // 상태별 필터링
  if (query.includes('완료')) {
    processedData.orders = data.orders.filter(o => o.status === '완료');
    message += `✅ 완료된 발주: ${processedData.orders.length}건\n\n`;
  } else if (query.includes('진행') || query.includes('대기')) {
    processedData.orders = data.orders.filter(o => o.status !== '완료');
    message += `⏳ 진행중/대기 발주: ${processedData.orders.length}건\n\n`;
  }
  
  // 통계 분석
  if (statsType) {
    const amounts = processedData.orders.map(o => o.amount);
    
    switch(statsType) {
      case 'max':
        const maxAmount = Math.max(...amounts);
        const maxOrder = processedData.orders.find(o => o.amount === maxAmount);
        message += `\n💰 최대 발주:\n`;
        message += `- 공급업체: ${maxOrder.supplier}\n`;
        message += `- 품목: ${maxOrder.item}\n`;
        message += `- 금액: ${formatNumber(maxAmount)}원\n`;
        message += `- 상태: ${maxOrder.status}\n`;
        processedData.highlight = maxOrder;
        break;
        
      case 'sum':
        const totalAmount = amounts.reduce((a,b) => a+b, 0);
        message += `\n📊 총 발주 금액: ${formatNumber(totalAmount)}원\n`;
        message += `- 발주 건수: ${processedData.orders.length}건\n`;
        message += `- 평균 발주액: ${formatNumber(Math.round(totalAmount / processedData.orders.length))}원\n`;
        break;
        
      case 'average':
        const avgAmount = amounts.reduce((a,b) => a+b, 0) / amounts.length;
        message += `\n📊 평균 발주 금액: ${formatNumber(Math.round(avgAmount))}원\n`;
        break;
    }
  }
  
  if (!message) {
    message = '구매 현황을 조회했습니다.';
  }
  
  return {
    type: 'purchase',
    data: processedData,
    message: message,
    query: query
  };
}

// 품질 질문 처리 (원인 분석 추가)
function handleQualityQuery(query, period, isComparison, specificItem, statsType, isCauseAnalysis) {
  const data = getQualityData();
  let message = '';
  let processedData = JSON.parse(JSON.stringify(data));
  
  // 원인 분석 요청
  if (isCauseAnalysis) {
    message += `🔍 불량 원인 분석:\n\n`;
    
    // 가장 많은 불량 유형 찾기
    const maxDefect = data.defectTypes.reduce((max, d) => d.count > max.count ? d : max);
    
    message += `📊 주요 불량 유형: ${maxDefect.type} (${maxDefect.count}건, ${maxDefect.rate}%)\n\n`;
    
    // 불량 원인 데이터 추가
    processedData.causeAnalysis = {
      mainDefect: maxDefect.type,
      causes: []
    };
    
    // 불량 유형별 원인 분석
    if (maxDefect.type === '외관 불량') {
      message += `💡 외관 불량 주요 원인:\n`;
      message += `1. 작업자 숙련도 부족 (35%)\n`;
      message += `2. 원자재 품질 문제 (28%)\n`;
      message += `3. 설비 노후화 (22%)\n`;
      message += `4. 작업 환경 (15%)\n\n`;
      message += `✅ 개선 방안:\n`;
      message += `- 작업자 교육 강화\n`;
      message += `- 원자재 입고 검사 강화\n`;
      message += `- 설비 정기 점검 및 교체\n`;
      
      processedData.causeAnalysis.causes = [
        { cause: '작업자 숙련도 부족', percent: 35 },
        { cause: '원자재 품질 문제', percent: 28 },
        { cause: '설비 노후화', percent: 22 },
        { cause: '작업 환경', percent: 15 }
      ];
    } else if (maxDefect.type === '치수 불량') {
      message += `💡 치수 불량 주요 원인:\n`;
      message += `1. 설비 캘리브레이션 오차 (42%)\n`;
      message += `2. 온습도 변화 (28%)\n`;
      message += `3. 측정 기구 오차 (20%)\n`;
      message += `4. 원자재 변형 (10%)\n\n`;
      message += `✅ 개선 방안:\n`;
      message += `- 설비 정밀 캘리브레이션\n`;
      message += `- 작업장 온습도 관리\n`;
      message += `- 측정 기구 정기 교정\n`;
      
      processedData.causeAnalysis.causes = [
        { cause: '설비 캘리브레이션 오차', percent: 42 },
        { cause: '온습도 변화', percent: 28 },
        { cause: '측정 기구 오차', percent: 20 },
        { cause: '원자재 변형', percent: 10 }
      ];
    } else if (maxDefect.type === '기능 불량') {
      message += `💡 기능 불량 주요 원인:\n`;
      message += `1. 부품 조립 불량 (38%)\n`;
      message += `2. 전기적 결함 (32%)\n`;
      message += `3. 소프트웨어 오류 (20%)\n`;
      message += `4. 부품 호환성 (10%)\n\n`;
      message += `✅ 개선 방안:\n`;
      message += `- 조립 공정 표준화\n`;
      message += `- 전기 검사 강화\n`;
      message += `- 소프트웨어 테스트 강화\n`;
      
      processedData.causeAnalysis.causes = [
        { cause: '부품 조립 불량', percent: 38 },
        { cause: '전기적 결함', percent: 32 },
        { cause: '소프트웨어 오류', percent: 20 },
        { cause: '부품 호환성', percent: 10 }
      ];
    } else {
      message += `💡 포장 불량 주요 원인:\n`;
      message += `1. 포장 작업 미숙 (45%)\n`;
      message += `2. 포장재 품질 (30%)\n`;
      message += `3. 물류 과정 손상 (15%)\n`;
      message += `4. 포장 설비 문제 (10%)\n\n`;
      message += `✅ 개선 방안:\n`;
      message += `- 포장 작업 교육\n`;
      message += `- 고품질 포장재 사용\n`;
      message += `- 물류 프로세스 개선\n`;
      
      processedData.causeAnalysis.causes = [
        { cause: '포장 작업 미숙', percent: 45 },
        { cause: '포장재 품질', percent: 30 },
        { cause: '물류 과정 손상', percent: 15 },
        { cause: '포장 설비 문제', percent: 10 }
      ];
    }
    
    return {
      type: 'quality_cause',
      data: processedData,
      message: message,
      query: query
    };
  }
  
  // 특정 불량 유형 필터링
  if (specificItem) {
    processedData.defectTypes = data.defectTypes.filter(d => d.type === specificItem);
    if (processedData.defectTypes.length > 0) {
      const defect = processedData.defectTypes[0];
      message += `📋 ${specificItem} 분석:\n`;
      message += `- 발생 건수: ${defect.count}건\n`;
      message += `- 전체 불량 중 비율: ${defect.rate}%\n`;
      message += `- 총 검사 대비: ${((defect.count / data.summary.totalInspections) * 100).toFixed(2)}%\n`;
    }
  }
  
  // 통계 분석
  if (statsType && !specificItem) {
    const counts = processedData.defectTypes.map(d => d.count);
    
    switch(statsType) {
      case 'max':
        const maxCount = Math.max(...counts);
        const maxDefect = processedData.defectTypes.find(d => d.count === maxCount);
        message += `\n⚠️ 가장 많은 불량 유형:\n`;
        message += `- ${maxDefect.type}: ${maxDefect.count}건 (${maxDefect.rate}%)\n`;
        message += `- ⚡ 우선 개선이 필요합니다!\n`;
        processedData.highlight = maxDefect;
        break;
        
      case 'min':
        const minCount = Math.min(...counts);
        const minDefect = processedData.defectTypes.find(d => d.count === minCount);
        message += `\n✅ 가장 적은 불량 유형:\n`;
        message += `- ${minDefect.type}: ${minDefect.count}건 (${minDefect.rate}%)\n`;
        message += `- 관리가 잘 되고 있습니다.\n`;
        processedData.highlight = minDefect;
        break;
        
      case 'sum':
        const totalDefects = counts.reduce((a,b) => a+b, 0);
        message += `\n📊 총 불량 건수: ${totalDefects}건\n`;
        message += `- 전체 검사 대비: ${((totalDefects / data.summary.totalInspections) * 100).toFixed(2)}%\n`;
        break;
    }
  }
  
  // 합격률 분석
  if (query.includes('합격률') || query.includes('불량률')) {
    message += `\n📊 품질 지표:\n`;
    message += `- ✅ 합격률: ${data.summary.passRate}%\n`;
    message += `- ❌ 불량률: ${(100 - data.summary.passRate).toFixed(1)}%\n`;
    message += `- 📋 총 검사: ${formatNumber(data.summary.totalInspections)}건\n`;
    message += `- ⚠️ 총 불량: ${data.summary.defectCount}건\n`;
  }
  
  if (!message) {
    message = '품질 현황을 조회했습니다.';
  }
  
  return {
    type: 'quality',
    data: processedData,
    message: message,
    query: query
  };
}

// 인사 질문 처리
function handleHRQuery(query, period, isComparison, specificItem, statsType) {
  const data = getHRData();
  let message = '';
  let processedData = JSON.parse(JSON.stringify(data));
  
  // 특정 부서 필터링
  if (specificItem) {
    processedData.departments = data.departments.filter(d => d.name === specificItem);
    if (processedData.departments.length > 0) {
      const dept = processedData.departments[0];
      message += `👥 ${specificItem} 상세 정보:\n`;
      message += `- 인원: ${dept.employees}명\n`;
      message += `- 출근율: ${dept.attendance}%\n`;
      message += `- 전체 직원 대비: ${((dept.employees / data.summary.totalEmployees) * 100).toFixed(1)}%\n`;
      
      if (dept.attendance >= 97) {
        message += `\n✅ 출근율이 우수합니다!`;
      } else if (dept.attendance < 96) {
        message += `\n⚠️ 출근율 관리가 필요합니다.`;
      }
    }
  }
  
  // 통계 분석
  if (statsType && !specificItem) {
    const employees = processedData.departments.map(d => d.employees);
    const attendances = processedData.departments.map(d => d.attendance);
    
    switch(statsType) {
      case 'max':
        if (query.includes('인원')) {
          const maxEmp = Math.max(...employees);
          const maxDept = processedData.departments.find(d => d.employees === maxEmp);
          message += `\n👥 최대 인원 부서:\n`;
          message += `- ${maxDept.name}: ${maxDept.employees}명\n`;
          message += `- 전체의 ${((maxDept.employees / data.summary.totalEmployees) * 100).toFixed(1)}%\n`;
          processedData.highlight = maxDept;
        } else {
          const maxAtt = Math.max(...attendances);
          const maxDept = processedData.departments.find(d => d.attendance === maxAtt);
          message += `\n⭐ 최고 출근율 부서:\n`;
          message += `- ${maxDept.name}: ${maxDept.attendance}%\n`;
          message += `- 인원: ${maxDept.employees}명\n`;
          processedData.highlight = maxDept;
        }
        break;
        
      case 'min':
        if (query.includes('인원')) {
          const minEmp = Math.min(...employees);
          const minDept = processedData.departments.find(d => d.employees === minEmp);
          message += `\n👥 최소 인원 부서:\n`;
          message += `- ${minDept.name}: ${minDept.employees}명\n`;
          processedData.highlight = minDept;
        } else {
          const minAtt = Math.min(...attendances);
          const minDept = processedData.departments.find(d => d.attendance === minAtt);
          message += `\n⚠️ 최저 출근율 부서:\n`;
          message += `- ${minDept.name}: ${minDept.attendance}%\n`;
          message += `- 관리가 필요합니다.\n`;
          processedData.highlight = minDept;
        }
        break;
        
      case 'average':
        const avgEmp = employees.reduce((a,b) => a+b, 0) / employees.length;
        const avgAtt = attendances.reduce((a,b) => a+b, 0) / attendances.length;
        message += `\n📊 부서별 평균:\n`;
        message += `- 평균 인원: ${Math.round(avgEmp)}명\n`;
        message += `- 평균 출근율: ${avgAtt.toFixed(1)}%\n`;
        break;
        
      case 'sum':
        const totalEmp = employees.reduce((a,b) => a+b, 0);
        message += `\n👥 총 직원 수: ${totalEmp}명\n`;
        break;
    }
  }
  
  // 신규입사/퇴사 분석
  if (query.includes('입사') || query.includes('퇴사') || query.includes('이직')) {
    message += `\n📋 인력 변동 현황:\n`;
    message += `- 신규 입사: ${data.summary.newHires}명\n`;
    message += `- 퇴사자: ${data.summary.resignations}명\n`;
    const netChange = data.summary.newHires - data.summary.resignations;
    message += `- 순증감: ${netChange > 0 ? '+' : ''}${netChange}명\n`;
    message += `- 이직률: ${((data.summary.resignations / data.summary.totalEmployees) * 100).toFixed(2)}%\n`;
  }
  
  if (!message) {
    message = '인사 현황을 조회했습니다.';
  }
  
  return {
    type: 'hr',
    data: processedData,
    message: message,
    query: query
  };
}

// 종합 질문 처리
function handleComprehensiveQuery(query) {
  return {
    type: 'comprehensive',
    data: {
      financial: getFinancialData().summary,
      production: getProductionData().summary,
      purchase: getPurchaseData().summary,
      quality: getQualityData().summary,
      hr: getHRData().summary
    },
    message: '전체 경영 현황을 조회했습니다.',
    query: query
  };
}

// 숫자 포맷팅
function formatNumber(num) {
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// 재무 데이터
function getFinancialData() {
  return {
    summary: {
      totalRevenue: 15800000000,
      totalExpense: 12300000000,
      netProfit: 3500000000,
      profitRate: 22.15
    },
    monthly: [
      { month: '1월', revenue: 1200000000, expense: 950000000, profit: 250000000 },
      { month: '2월', revenue: 1350000000, expense: 1050000000, profit: 300000000 },
      { month: '3월', revenue: 1280000000, expense: 1020000000, profit: 260000000 },
      { month: '4월', revenue: 1420000000, expense: 1100000000, profit: 320000000 },
      { month: '5월', revenue: 1380000000, expense: 1080000000, profit: 300000000 },
      { month: '6월', revenue: 1470000000, expense: 1150000000, profit: 320000000 }
    ]
  };
}

// 생산 데이터 (월별 추가)
function getProductionData() {
  return {
    summary: {
      totalProduction: 125000,
      defectRate: 1.8,
      efficiency: 94.5
    },
    monthly: [
      { month: '1월', totalProduction: 19500, goodProducts: 19140, defectProducts: 360, defectRate: 1.85, efficiency: 93.2 },
      { month: '2월', totalProduction: 20200, goodProducts: 19838, defectProducts: 362, defectRate: 1.79, efficiency: 94.1 },
      { month: '3월', totalProduction: 20800, goodProducts: 20426, defectProducts: 374, defectRate: 1.80, efficiency: 94.8 },
      { month: '4월', totalProduction: 21500, goodProducts: 21115, defectProducts: 385, defectRate: 1.79, efficiency: 95.2 },
      { month: '5월', totalProduction: 21200, goodProducts: 20828, defectProducts: 372, defectRate: 1.75, efficiency: 94.6 },
      { month: '6월', totalProduction: 21800, goodProducts: 21404, defectProducts: 396, defectRate: 1.82, efficiency: 95.4 }
    ],
    products: [
      { name: 'A-100 모델', quantity: 35000, target: 40000, rate: 87.5 },
      { name: 'B-200 모델', quantity: 42000, target: 45000, rate: 93.3 },
      { name: 'C-300 모델', quantity: 28000, target: 30000, rate: 93.3 },
      { name: 'D-400 모델', quantity: 20000, target: 22000, rate: 90.9 }
    ],
    daily: [
      { date: '2026-07-10', production: 2100, defect: 38 },
      { date: '2026-07-11', production: 2250, defect: 41 },
      { date: '2026-07-12', production: 2180, defect: 35 },
      { date: '2026-07-13', production: 2300, defect: 42 },
      { date: '2026-07-14', production: 2150, defect: 39 }
    ]
  };
}

// 구매 데이터
function getPurchaseData() {
  return {
    summary: {
      totalOrders: 245,
      totalAmount: 4800000000,
      pendingOrders: 18
    },
    orders: [
      { supplier: '(주)대한소재', item: '철강 원자재', amount: 850000000, status: '완료' },
      { supplier: '글로벌부품', item: '전자부품 세트', amount: 620000000, status: '진행중' },
      { supplier: '한국화학', item: '산업용 화학제', amount: 450000000, status: '완료' },
      { supplier: '프리미엄자재', item: '특수 합금', amount: 720000000, status: '대기' },
      { supplier: '스마트부품상사', item: 'PCB 기판', amount: 380000000, status: '완료' }
    ]
  };
}

// 품질 데이터
function getQualityData() {
  return {
    summary: {
      totalInspections: 8500,
      passRate: 98.2,
      defectCount: 153
    },
    defectTypes: [
      { type: '외관 불량', count: 62, rate: 40.5 },
      { type: '치수 불량', count: 38, rate: 24.8 },
      { type: '기능 불량', count: 28, rate: 18.3 },
      { type: '포장 불량', count: 25, rate: 16.4 }
    ],
    inspections: [
      { date: '2026-07-10', total: 1700, pass: 1668, fail: 32 },
      { date: '2026-07-11', total: 1750, pass: 1719, fail: 31 },
      { date: '2026-07-12', total: 1680, pass: 1651, fail: 29 },
      { date: '2026-07-13', total: 1800, pass: 1767, fail: 33 },
      { date: '2026-07-14', total: 1570, pass: 1542, fail: 28 }
    ]
  };
}

// 인사 데이터
function getHRData() {
  return {
    summary: {
      totalEmployees: 485,
      newHires: 12,
      resignations: 5,
      avgAttendance: 96.8
    },
    departments: [
      { name: '생산부', employees: 180, attendance: 97.2 },
      { name: '영업부', employees: 85, attendance: 95.8 },
      { name: '기술부', employees: 95, attendance: 96.5 },
      { name: '관리부', employees: 65, attendance: 97.8 },
      { name: '품질부', employees: 60, attendance: 98.1 }
    ],
    attendance: [
      { date: '2026-07-10', present: 472, absent: 8, leave: 5 },
      { date: '2026-07-11', present: 468, absent: 10, leave: 7 },
      { date: '2026-07-12', present: 475, absent: 6, leave: 4 },
      { date: '2026-07-13', present: 470, absent: 9, leave: 6 },
      { date: '2026-07-14', present: 473, absent: 7, leave: 5 }
    ]
  };
}

// 카테고리별 데이터 조회
function getCategoryData(category) {
  switch(category) {
    case 'financial':
      return { type: 'financial', data: getFinancialData(), message: '재무 현황입니다.' };
    case 'production':
      return { type: 'production', data: getProductionData(), message: '생산 현황입니다.' };
    case 'purchase':
      return { type: 'purchase', data: getPurchaseData(), message: '구매 현황입니다.' };
    case 'quality':
      return { type: 'quality', data: getQualityData(), message: '품질 현황입니다.' };
    case 'hr':
      return { type: 'hr', data: getHRData(), message: '인사 현황입니다.' };
    default:
      return { type: 'text', data: null, message: '데이터를 찾을 수 없습니다.' };
  }
}
