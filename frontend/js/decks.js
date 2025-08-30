// frontend/js/decks.js
// Multi-deck UI: list, open, edit plan, render

;(function () {
  const API = (window.Presto && window.Presto.API) || `${location.origin}/api/v1`

  function $(id) { return document.getElementById(id) }

  function setStatus(msg) {
    const el = $('deck-status')
    if (el) el.textContent = msg || ''
  }

  function showPlanEditor(deck) {
    const sec = $('plan-editor')
    if (!sec) return
    $('plan-topic').value = deck.topic || ''
    $('plan-audience').value = deck.audience || ''
    $('plan-theme').value = deck.theme || ''
    $('plan-color').value = deck.color_preference || ''

    const slideWrap = $('plan-editor-slides')
    slideWrap.innerHTML = ''
    ;(deck.slides || []).forEach((s, i) => {
      const div = document.createElement('div')
      div.className = 'card'
      div.innerHTML = `
        <h4 class="font-semibold">#${s.slide_id} ${s.title || 'Untitled'}</h4>
        <label class="text-xs text-slate-500">Title</label>
        <input class="w-full p-2 border rounded" data-k="title" value="${(s.title || '').replace(/"/g, '&quot;')}" />
        <label class="text-xs text-slate-500">Key Points (one per line)</label>
        <textarea class="w-full p-2 border rounded" data-k="key_points">${(s.key_points || []).join('\n')}</textarea>
        <label class="text-xs text-slate-500">Numbers (JSON)</label>
        <textarea class="w-full p-2 border rounded" data-k="numbers">${s.numbers ? JSON.stringify(s.numbers, null, 2) : ''}</textarea>
        <label class="text-xs text-slate-500">Notes</label>
        <textarea class="w-full p-2 border rounded" data-k="notes">${s.notes || ''}</textarea>
        <label class="text-xs text-slate-500">Section</label>
        <input class="w-full p-2 border rounded" data-k="section" value="${s.section || ''}" />
        <label class="text-xs text-slate-500">Layout Candidates (comma-separated)</label>
        <input class="w-full p-2 border rounded" data-k="layout_candidates" value="${(s.layout_candidates || []).join(', ')}" />
      `
      div.dataset.index = String(i)
      div.dataset.slideId = String(s.slide_id)
      slideWrap.appendChild(div)
    })

    sec.classList.remove('hidden')
  }

  function collectDeckPlanFromEditor() {
    const topic = $('plan-topic').value.trim()
    const audience = $('plan-audience').value.trim()
    const theme = $('plan-theme').value.trim() || null
    const color = $('plan-color').value.trim() || null
    const slideWrap = $('plan-editor-slides')
    const slides = []
    ;[...slideWrap.children].forEach((div) => {
      const idx = Number(div.dataset.index)
      const slideId = Number(div.dataset.slideId)
      const inputs = div.querySelectorAll('[data-k]')
      const s = {}
      inputs.forEach((el) => {
        const k = el.getAttribute('data-k')
        if (k === 'key_points') s[k] = el.value.split('\n').map((x) => x.trim()).filter(Boolean)
        else if (k === 'numbers') { try { s[k] = el.value ? JSON.parse(el.value) : null } catch { s[k] = null } }
        else if (k === 'layout_candidates') { s[k] = el.value.split(',').map((x) => x.trim()).filter(Boolean) }
        else { s[k] = el.value }
      })
      slides.push({
        slide_id: slideId || idx + 1,
        title: (s.title || '').trim(),
        key_points: s.key_points || null,
        numbers: s.numbers || null,
        notes: s.notes || null,
        section: s.section || null,
        layout_candidates: s.layout_candidates || [],
      })
    })
    return { topic, audience, theme, color_preference: color, slides }
  }

  async function fetchJSON(url, options) {
    const res = await fetch(url, options)
    if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
    return await res.json()
  }

  async function loadDecks() {
    try {
      const data = await fetchJSON(`${API}/decks`)
      const list = $('deck-list')
      list.innerHTML = ''
      data.decks.forEach((d) => {
        const card = document.createElement('div')
        card.className = 'card'
        const slidesText = `${d.slides || 0} slide${(d.slides || 0) === 1 ? '' : 's'}`
        card.innerHTML = `
          <div class="text-sm text-slate-500">${new Date((d.updated_at || 0) * 1000).toLocaleString()}</div>
          <h3 class="font-semibold">${d.topic || 'Untitled'}</h3>
          <div class="text-sm">Audience: ${d.audience || '-'}</div>
          <div class="text-sm">${slidesText}</div>
          <div class="mt-2 flex gap-2 justify-end">
            <button class="open-deck bg-emerald-600 text-white px-2 py-1 rounded" data-id="${d.id}">Open</button>
          </div>
        `
        list.appendChild(card)
      })
    } catch (e) {
      console.error('Failed to load decks', e)
    }
  }

  async function openDeck(deckId) {
    try {
      setStatus('Loading deck...')
      const data = await fetchJSON(`${API}/decks/${deckId}`)
      if (!window.Presto) window.Presto = {}
      window.Presto.currentDeckId = deckId
      $('current-deck-label').textContent = `Deck ${deckId} · ${data.deck_plan.topic}`
      showPlanEditor(data.deck_plan)
      setStatus('Deck loaded. You can edit and save the plan.')

      // Wire htmx to deck-scoped endpoints
      const area = $('slides-area')
      if (area) {
        area.setAttribute('hx-sse', `connect:/api/v1/ui/decks/${deckId}/events`)
        area.setAttribute('hx-get', `/api/v1/ui/decks/${deckId}/slides`)
        area.setAttribute('hx-trigger', 'load, sse:slide_rendered, sse:completed')
        // Re-scan for new attributes and ensure SSE connects
        if (window.htmx && window.htmx.process) {
          window.htmx.process(area)
        }
        // Initial fetch
        if (window.htmx && window.htmx.ajax) {
          window.htmx.ajax('GET', `/api/v1/ui/decks/${deckId}/slides`, { target: '#slides-area', swap: 'innerHTML' })
        } else {
          // fallback
          await window.PrestoStream?.refreshSlidesDeck(deckId)
        }
      }
    } catch (e) {
      setStatus('Error: ' + (e.message || 'unknown'))
    }
  }

  async function createDeck(e) {
    e.preventDefault()
    const btn = e.submitter || $('new-deck-form').querySelector('button[type="submit"]')
    if (btn) btn.disabled = true
    setStatus('Creating deck...')
    try {
      const payload = {
        user_prompt: $('new-user-prompt').value,
        theme: $('new-theme').value || null,
        color_preference: $('new-color').value || null,
        config: { quality: 'default' },
      }
      const res = await fetch(`${API}/decks`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      await loadDecks()
      await openDeck(data.deck_id)
      setStatus('Deck created. Review the plan and render when ready.')
    } catch (err) {
      console.error(err)
      setStatus('Error: ' + (err.message || 'unknown'))
    } finally {
      if (btn) btn.disabled = false
    }
  }

  async function savePlan() {
    const deckId = (window.Presto || {}).currentDeckId
    if (!deckId) return
    const btn = $('plan-save')
    btn.disabled = true
    setStatus('Saving plan...')
    try {
      const plan = collectDeckPlanFromEditor()
      const res = await fetch(`${API}/decks/${deckId}/plan`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(plan) })
      if (!res.ok) throw new Error(await res.text())
      setStatus('Plan saved.')
    } catch (e) {
      console.error(e)
      setStatus('Error: ' + (e.message || 'unknown'))
    } finally { btn.disabled = false }
  }

  async function renderDeck() {
    const deckId = (window.Presto || {}).currentDeckId
    if (!deckId) return
    await savePlan() // save first for consistency
    await window.PrestoStream?.renderDeck(deckId)
  }

  function init() {
    $('refresh-decks')?.addEventListener('click', loadDecks)
    $('new-deck-form')?.addEventListener('submit', createDeck)
    $('plan-save')?.addEventListener('click', savePlan)
    $('plan-render')?.addEventListener('click', renderDeck)
    document.body.addEventListener('click', (e) => {
      const btn = e.target.closest('button.open-deck')
      if (!btn) return
      const id = btn.getAttribute('data-id')
      if (id) openDeck(id)
    })
    loadDecks()
  }

  if (!window.Presto) window.Presto = {}
  window.Presto.decks = { init, openDeck, loadDecks }
  document.addEventListener('DOMContentLoaded', init)
})()
