// frontend/js/slides.js
//
// 한국어 설명: 슬라이드 목록 렌더링, 선택/삭제, 폴링 등을 담당합니다.

;(function () {
  const API = (window.Presto && window.Presto.API) || `${location.origin}/api/v1`

  const state = {
    sortActive: false,
    sortAsc: true,
    pollInterval: null,
    selectedId: null,
    generatedSlides: new Map(), // id -> { title, html, status }
  }

  function $(id) {
    return document.getElementById(id)
  }

  async function fetchSlides() {
    const response = await fetch(`${API}/slides`)
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    return await response.json()
  }

  function renderSlideCard(slide) {
    const slideCard = document.createElement('div')
    slideCard.id = `slide-${slide.id}`
    slideCard.classList.add('slide-card')
    if (slide.status === 'editing') slideCard.classList.add('editing')

    slideCard.innerHTML = `
      <h2 style="display:flex;justify-content:space-between;align-items:center;margin:0;background:#059669;color:white;padding:8px 12px;font-size:1.1em;overflow:hidden;">
        <span style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${slide.title || 'Untitled Slide'}</span>
        <span style="font-size:12px;opacity:0.9;padding-left:8px;">#${slide.id}</span>
      </h2>
      <div class="slide-content"></div>
      <div class="card-footer">
        <button class="btn-toggle-code">Code</button>
        <button class="btn-preview">Preview</button>
        <button class="btn-delete danger">Delete</button>
      </div>
      <div class="code-view" style="display: none; max-height: 200px; overflow: auto; background: #2d2d2d; color: #f1f1f1; padding: 8px; border-top: 1px solid #444;">
        <pre style="margin: 0; white-space: pre-wrap; word-break: break-all; font-family: 'Courier New', Courier, monospace; font-size: 13px;"><code></code></pre>
      </div>
    `

    const slideContentDiv = slideCard.querySelector('.slide-content')
    if (slide.html_content) {
      const iframe = document.createElement('iframe')
      iframe.scrolling = 'no'
      const iframeContent = `
        <!DOCTYPE html>
        <html>
        <head>
          <style>
            body { margin: 0; padding: 20px; font-family: 'Segoe UI', sans-serif; color: #333; transform: scale(0.9); transform-origin: top left; }
            img { max-width: 100%; height: auto; }
            table { width: 100%; border-collapse: collapse; }
            th, td { border: 1px solid #ddd; padding: 8px; }
          </style>
        </head>
        <body>
          ${slide.html_content}
        </body>
        </html>
      `
      iframe.srcdoc = iframeContent
      slideContentDiv.innerHTML = ''
      slideContentDiv.appendChild(iframe)

      const codeElement = slideCard.querySelector('.code-view code')
      if (codeElement) codeElement.textContent = slide.html_content
    } else if (slide.status === 'editing') {
      slideContentDiv.innerHTML = '<div class="spinner"></div><p>Editing...</p>'
    } else {
      slideContentDiv.innerHTML = '<p>No content yet.</p>'
    }

    // 카드 이벤트
    slideCard.querySelector('.btn-toggle-code').addEventListener('click', (e) => {
      e.stopPropagation()
      const codeView = slideCard.querySelector('.code-view')
      const button = e.target
      if (codeView.style.display === 'none') {
        codeView.style.display = 'block'
        button.textContent = 'Hide'
      } else {
        codeView.style.display = 'none'
        button.textContent = 'Code'
      }
    })

    slideCard.addEventListener('click', () => selectCard(slide.id))
    slideCard.addEventListener('dblclick', () => {
      const iframe = slideCard.querySelector('iframe')
      if (iframe && iframe.srcdoc) window.Presto?.modal?.open(iframe.srcdoc)
    })
    slideCard.querySelector('.btn-preview').addEventListener('click', (e) => {
      e.stopPropagation()
      const iframe = slideCard.querySelector('iframe')
      if (iframe && iframe.srcdoc) window.Presto?.modal?.open(iframe.srcdoc)
    })
    slideCard.querySelector('.btn-delete').addEventListener('click', async (e) => {
      e.stopPropagation()
      await deleteSlide(slide.id)
    })

    return slideCard
  }

  async function fetchAndRenderSlides() {
    try {
      let slides = await fetchSlides()
      if (state.sortActive) {
        slides = slides.slice().sort((a, b) => (state.sortAsc ? a.id - b.id : b.id - a.id))
      }
      const slidesArea = $('slides-area')
      if (!slidesArea) return
      slidesArea.innerHTML = ''
      state.generatedSlides.clear()
      slides.forEach((slide) => {
        state.generatedSlides.set(slide.id, { title: slide.title, html: slide.html_content, status: slide.status })
        slidesArea.appendChild(renderSlideCard(slide))
      })
    } catch (e) {
      console.error('Error fetching slides:', e)
    }
  }

  function selectCard(id) {
    if (state.selectedId !== null) {
      const prev = document.getElementById(`slide-${state.selectedId}`)
      prev?.classList.remove('selected')
    }
    state.selectedId = id
    document.getElementById(`slide-${id}`)?.classList.add('selected')
    const editSlideId = $('edit-slide-id')
    if (editSlideId) editSlideId.value = String(id)
    document.dispatchEvent(new CustomEvent('presto:selected', { detail: { id } }))
  }

  async function deleteSlide(id) {
    try {
      await fetch(`${API}/slides/${id}/delete`, { method: 'DELETE' })
    } catch (_) {}
    const el = document.getElementById(`slide-${id}`)
    el?.remove()
    state.generatedSlides.delete(id)
    if (state.selectedId === id) {
      state.selectedId = null
      const editSlideId = $('edit-slide-id')
      if (editSlideId) editSlideId.value = ''
      document.dispatchEvent(new CustomEvent('presto:selected', { detail: { id: null } }))
    }
  }

  function startPollingSlides() {
    if (state.pollInterval) clearInterval(state.pollInterval)
    state.pollInterval = setInterval(fetchAndRenderSlides, 2000)
  }
  function stopPollingSlides() {
    if (state.pollInterval) {
      clearInterval(state.pollInterval)
      state.pollInterval = null
    }
  }

  // 전역 공개
  if (!window.Presto) window.Presto = {}
  window.Presto.slides = {
    state,
    fetchAndRenderSlides,
    selectCard,
    deleteSlide,
    startPollingSlides,
    stopPollingSlides,
  }
  // 기존 접근 호환성
  window.fetchAndRenderSlides = fetchAndRenderSlides
  window.startPollingSlides = startPollingSlides
  window.stopPollingSlides = stopPollingSlides
})()
