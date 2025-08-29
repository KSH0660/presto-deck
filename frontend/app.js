// frontend/app.js (리팩토링 부트스트랩)
//
// 한국어 설명: 분리된 모듈들을 초기화합니다.

;(function () {
  document.addEventListener('DOMContentLoaded', () => {
    window.Presto?.modal?.init()
    window.Presto?.events?.init()
  })
})()
