function doGet(e) {
  return HtmlService.createTemplateFromFile('Index')
    .evaluate()
    .setTitle('SB AI - ERP Assistant')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1')
    .setFaviconUrl('https://www.gstatic.com/script/images/favicon.ico')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}

/**
 * DB가 아직 연동되지 않아, 응답 형식(텍스트/이미지/그래프)을 보여주기 위한 목업 생성기.
 * 실제 DB 연동 시 이 함수의 내부만 교체하면 됨 — 클라이언트 계약(type/text/...)은 유지.
 */
function generateReply(userMessage) {
  var msg = (userMessage || '').toLowerCase();

  if (/이미지|사진|그림|비주얼/.test(msg)) {
    return {
      type: 'image',
      text: '요청하신 이미지 응답 형식의 예시입니다. DB 연동 후 실제 첨부/생성 이미지가 이 자리에 표시됩니다.',
      images: [
        { caption: '자재 입고 사진 (예시)' },
        { caption: '설비 점검 사진 (예시)' }
      ]
    };
  }

  if (/그래프|차트|통계|추이|매출|재고|데이터/.test(msg)) {
    return {
      type: 'chart',
      text: '요청하신 그래프 응답 형식의 예시입니다. 아래 수치는 DB 연동 전 임의 데이터입니다.',
      chart: {
        title: '월별 생산량 (예시 데이터)',
        unit: '단위: 톤',
        categories: ['1월', '2월', '3월', '4월', '5월', '6월'],
        values: [42, 58, 51, 67, 73, 61]
      }
    };
  }

  var textReplies = [
    '현재 데이터베이스가 연동되지 않아 실제 답변 대신 예시 응답을 보여드리고 있습니다. "그래프"나 "이미지"라는 단어를 포함해 질문하시면 해당 형식의 응답 예시도 확인하실 수 있습니다.',
    '무엇을 도와드릴까요? 아직은 실제 데이터에 연결되어 있지 않지만, 채팅 화면과 응답 형식은 이렇게 구성될 예정입니다.',
    '질문을 입력해 주시면 답변을 생성합니다. (현재는 DB 연동 전 미리보기 단계입니다.)'
  ];
  return {
    type: 'text',
    text: textReplies[Math.floor(Math.random() * textReplies.length)]
  };
}
