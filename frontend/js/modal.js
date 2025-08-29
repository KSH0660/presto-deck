// frontend/js/modal.js
//
// 한국어 설명: 모달 열기/닫기 및 이벤트 바인딩을 담당합니다.

;(function () {
  const Modal = {
    els: {
      slideModal: null,
      closeModalBtn: null,
      modalSlideViewer: null,
    },
    init() {
      this.els.slideModal = document.getElementById('slide-modal')
      this.els.closeModalBtn = this.els.slideModal?.querySelector('.close-button')
      this.els.modalSlideViewer = document.getElementById('modal-slide-viewer')

      if (!this.els.slideModal || !this.els.closeModalBtn || !this.els.modalSlideViewer) return

      this.els.closeModalBtn.addEventListener('click', () => this.close())
      this.els.slideModal.addEventListener('click', (e) => {
        if (e.target === this.els.slideModal) this.close()
      })
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && this.els.slideModal.classList.contains('visible')) this.close()
      })
    },
    open(slideHtml) {
      if (!this.els.modalSlideViewer || !this.els.slideModal) return
      this.els.modalSlideViewer.innerHTML = ''
      const modalIframe = document.createElement('iframe')
      modalIframe.srcdoc = slideHtml
      this.els.modalSlideViewer.appendChild(modalIframe)
      this.els.slideModal.classList.add('visible')
    },
    close() {
      if (!this.els.modalSlideViewer || !this.els.slideModal) return
      this.els.slideModal.classList.remove('visible')
      this.els.modalSlideViewer.innerHTML = ''
    },
  }

  // 전역 공개
  if (!window.Presto) window.Presto = {}
  window.Presto.modal = Modal
})()
