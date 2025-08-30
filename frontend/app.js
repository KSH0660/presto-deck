// frontend/app.js (리팩토링 부트스트랩)
//
// 한국어 설명: 분리된 모듈들을 초기화합니다.

;(function () {
  document.addEventListener('DOMContentLoaded', () => {
    window.Presto?.modal?.init()
    window.Presto?.events?.init()

    // Delegated handlers for htmx-injected slide cards
    document.body.addEventListener('click', (e) => {
      const btn = e.target.closest('button')
      if (!btn) return
      const card = e.target.closest('.slide-card')
      if (!card) return
      if (btn.classList.contains('btn-toggle-code')) {
        const codeView = card.querySelector('.code-view')
        if (!codeView) return
        const shown = codeView.style.display !== 'none'
        codeView.style.display = shown ? 'none' : 'block'
        btn.textContent = shown ? 'Code' : 'Hide'
      }
      if (btn.classList.contains('btn-preview')) {
        const iframe = card.querySelector('iframe')
        if (iframe && iframe.srcdoc) window.Presto?.modal?.open(iframe.srcdoc)
      }
    })
  })
})()
