// frontend/js/events.js
//
// 한국어 설명: SSE 커스텀 이벤트 처리와 UI 버튼/초기화 바인딩을 담당합니다.

;(function () {
  function $(id) {
    return document.getElementById(id)
  }

  function updateSortButton() {
    const btn = $('sort-id-btn')
    const s = window.Presto?.slides?.state
    if (!btn || !s) return
    btn.textContent = s.sortActive ? `Sort: ID ${s.sortAsc ? '↑' : '↓'}` : 'Sort: Arrival'
  }

  function initEventHandlers() {
    const statusText = $('status-text')
    const progressBarContainer = $('progress-bar-container')
    const progressBar = $('progress-bar')
    const generateBtn = $('generate-btn')
    const deckPlanSection = $('deck-plan-section')
    const deckPlanMeta = $('deck-plan-meta')
    const deckPlanTitles = $('deck-plan-titles')

    function clearDeckPlan() {
      if (deckPlanTitles) deckPlanTitles.innerHTML = ''
      if (deckPlanMeta) deckPlanMeta.textContent = ''
      deckPlanSection?.classList.add('hidden')
      if (!window.Presto) window.Presto = {}
      window.Presto.deckPlan = null
    }

    function renderDeckPlan(data) {
      try {
        const theme = data.theme || 'Not specified'
        const colors = data.color_preference || 'Not specified'
        if (deckPlanMeta) {
          deckPlanMeta.innerHTML = `
            <div><span class="font-semibold">Topic:</span> ${data.topic}</div>
            <div><span class="font-semibold">Audience:</span> ${data.audience}</div>
            <div><span class="font-semibold">Theme:</span> ${theme}</div>
            <div><span class="font-semibold">Colors:</span> ${colors}</div>
          `
        }
        if (deckPlanTitles) {
          deckPlanTitles.innerHTML = ''
          ;(data.slides || []).forEach((s) => {
            const li = document.createElement('li')
            li.textContent = s.title || 'Untitled'
            deckPlanTitles.appendChild(li)
          })
        }
        deckPlanSection?.classList.remove('hidden')
        if (!window.Presto) window.Presto = {}
        window.Presto.deckPlan = data
      } catch (e) {
        console.warn('Failed to render deck plan', e)
      }
    }

    document.addEventListener('started', (event) => {
      const data = event.detail
      if (statusText) statusText.textContent = `Generation started (model: ${data.model})...`
      clearDeckPlan()
    })

    document.addEventListener('deck_plan', async (event) => {
      const data = event.detail
      if (statusText) statusText.textContent = `Deck plan ready. Generating ${data.slides.length} slides.`
      renderDeckPlan(data)
      await window.Presto?.slides?.fetchAndRenderSlides()
    })

    document.addEventListener('slide_rendered', async () => {
      await window.Presto?.slides?.fetchAndRenderSlides()
    })

    document.addEventListener('progress', (event) => {
      const data = event.detail
      if (data.total > 0 && progressBar && statusText) {
        const percentage = (data.completed / data.total) * 100
        progressBar.style.width = `${percentage}%`
        statusText.textContent = `Generating slides: ${data.completed}/${data.total} (${data.stage})...`
      }
    })

    document.addEventListener('completed', (event) => {
      const data = event.detail
      if (statusText) statusText.textContent = `Generation complete! Total time: ${(data.duration_ms / 1000).toFixed(2)}s`
      if (generateBtn) generateBtn.disabled = false
      progressBarContainer?.classList.add('hidden')
    })

    document.addEventListener('error', (event) => {
      const data = event.detail
      if (statusText) statusText.textContent = `Error: ${data.message || 'An unknown error occurred.'}`
      if (generateBtn) generateBtn.disabled = false
      progressBarContainer?.classList.add('hidden')
    })
  }

  function initUIBindings() {
    const exportHtmlBtn = $('export-html-btn')
    const sortIdBtn = $('sort-id-btn')
    exportHtmlBtn?.addEventListener('click', () => {
      const API = window.Presto?.API || `${location.origin}/api/v1`
      window.open(`${API}/export/html`, '_blank')
    })
    sortIdBtn?.addEventListener('click', () => {
      const s = window.Presto?.slides?.state
      if (!s) return
      if (!s.sortActive) {
        s.sortActive = true
        s.sortAsc = true
      } else {
        s.sortAsc = !s.sortAsc
      }
      updateSortButton()
      window.Presto?.slides?.fetchAndRenderSlides()
    })
  }

  function init() {
    initEventHandlers()
    initUIBindings()
    // 초기 로딩 시 슬라이드 렌더링
    window.Presto?.slides?.fetchAndRenderSlides()
    updateSortButton()
  }

  if (!window.Presto) window.Presto = {}
  window.Presto.events = { init }
})()
