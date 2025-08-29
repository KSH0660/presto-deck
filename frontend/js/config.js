// frontend/js/config.js
//
// 한국어 설명: 전역 네임스페이스와 기본 설정을 초기화합니다.

;(function () {
  if (!window.Presto) window.Presto = {}
  // 같은 오리진 API 기본 경로
  window.Presto.API = `${location.origin}/api/v1`
})()
