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
    open(slideHtml, opts = {}) {
      if (!this.els.modalSlideViewer || !this.els.slideModal) return
      this.els.modalSlideViewer.innerHTML = ''
      // Layout: preview on top, editor on right below
      const wrapper = document.createElement('div')
      wrapper.style.display = 'flex'
      wrapper.style.flexDirection = 'row'
      wrapper.style.gap = '12px'
      wrapper.style.height = '100%'

      const preview = document.createElement('div')
      preview.style.flex = '1'
      const modalIframe = document.createElement('iframe')
      modalIframe.srcdoc = slideHtml
      preview.appendChild(modalIframe)

      const editor = document.createElement('div')
      editor.style.width = '360px'
      editor.style.background = '#111827'
      editor.style.color = '#e5e7eb'
      editor.style.borderRadius = '6px'
      editor.style.padding = '8px'

      const title = document.createElement('div')
      title.textContent = 'AI Edit'
      title.style.fontWeight = '600'
      title.style.marginBottom = '6px'
      editor.appendChild(title)

      const form = document.createElement('form')
      const deckId = opts?.deckId
      const slideId = opts?.slideId
      if (slideId) {
        form.setAttribute(
          'hx-post',
          deckId
            ? `/api/v1/ui/decks/${deckId}/slides/${slideId}/edit`
            : `/api/v1/ui/slides/${slideId}/edit`
        )
        form.setAttribute('hx-target', `#slide-${slideId}`)
        form.setAttribute('hx-swap', 'outerHTML')
      }
      const ta = document.createElement('textarea')
      ta.name = 'edit_prompt'
      ta.placeholder = 'Describe your change'
      ta.style.width = '100%'
      ta.style.minHeight = '120px'
      ta.style.padding = '8px'
      ta.style.borderRadius = '6px'
      ta.style.border = '1px solid #374151'
      ta.style.background = '#0b1220'
      ta.style.color = '#e5e7eb'
      form.appendChild(ta)

      const row = document.createElement('div')
      row.style.display = 'flex'
      row.style.justifyContent = 'flex-end'
      row.style.marginTop = '6px'
      const btn = document.createElement('button')
      btn.type = 'submit'
      btn.textContent = 'Apply'
      btn.style.background = '#2563eb'
      btn.style.color = '#fff'
      btn.style.border = 'none'
      btn.style.padding = '6px 10px'
      btn.style.borderRadius = '6px'
      row.appendChild(btn)
      form.appendChild(row)
      editor.appendChild(form)

      wrapper.appendChild(preview)
      wrapper.appendChild(editor)
      this.els.modalSlideViewer.appendChild(wrapper)
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
