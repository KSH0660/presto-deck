// frontend/js/planflow.js
// Plan → Edit → Render flow (session upload, deck planning, render)

;(function () {
  const API = (window.Presto && window.Presto.API) || `${location.origin}/api/v1`

  function $(id) {
    return document.getElementById(id)
  }

  function setSessionStatus(msg) {
    const el = $('session-status')
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
      // attach index for serialization
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
        else if (k === 'numbers') {
          try { s[k] = el.value ? JSON.parse(el.value) : null } catch { s[k] = null }
        } else if (k === 'layout_candidates') {
          s[k] = el.value.split(',').map((x) => x.trim()).filter(Boolean)
        } else {
          s[k] = el.value
        }
      })
      // inject required fields
      const title = (s.title || '').trim()
      slides.push({
        slide_id: slideId || idx + 1,
        title,
        key_points: s.key_points || null,
        numbers: s.numbers || null,
        notes: s.notes || null,
        section: s.section || null,
        layout_candidates: s.layout_candidates || [],
      })
    })
    return { topic, audience, theme, color_preference: color, slides }
  }

  async function createSessionAndPlan() {
    const btn = $('session-submit')
    btn.disabled = true
    setSessionStatus('Creating session...')
    try {
      const fd = new FormData()
      fd.append('user_prompt', $('session-user-prompt').value)
      if ($('session-theme').value) fd.append('theme', $('session-theme').value)
      if ($('session-color').value) fd.append('color_preference', $('session-color').value)
      const files = $('session-files').files
      for (let i = 0; i < files.length; i++) fd.append('files', files[i])

      const sres = await fetch(`${API}/session`, { method: 'POST', body: fd })
      if (!sres.ok) throw new Error(`Session failed: ${await sres.text()}`)
      const sdata = await sres.json()
      window.Presto = window.Presto || {}
      window.Presto.sessionId = sdata.session_id
      setSessionStatus(`Session created: ${sdata.session_id}. Planning deck...`)

      // Call plan
      const planPayload = {
        user_prompt: $('session-user-prompt').value,
        theme: $('session-theme').value || null,
        color_preference: $('session-color').value || null,
        config: { quality: 'default' },
      }
      const pres = await fetch(`${API}/plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(planPayload),
      })
      if (!pres.ok) throw new Error(`Plan failed: ${await pres.text()}`)
      const deck = await pres.json()
      setSessionStatus('Deck plan ready. Review and edit below.')
      showPlanEditor(deck)
      // Also show simple overview
      document.dispatchEvent(new CustomEvent('deck_plan', { detail: deck }))
    } catch (e) {
      console.error(e)
      setSessionStatus('Error: ' + (e.message || 'unknown'))
    } finally {
      btn.disabled = false
    }
  }

  async function renderFromEditor() {
    const btn = $('plan-render')
    btn.disabled = true
    setSessionStatus('Rendering slides from DeckPlan...')
    try {
      const deck_plan = collectDeckPlanFromEditor()
      const payload = {
        user_prompt: $('session-user-prompt').value,
        theme: deck_plan.theme,
        color_preference: deck_plan.color_preference,
        deck_plan,
        config: { quality: 'default' },
      }
      const r = await fetch(`${API}/slides/render`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!r.ok) throw new Error(await r.text())
      await window.Presto?.slides?.fetchAndRenderSlides()
      setSessionStatus('Render complete. You can AI-edit slides below.')
    } catch (e) {
      console.error(e)
      setSessionStatus('Error: ' + (e.message || 'unknown'))
    } finally {
      btn.disabled = false
    }
  }

  function init() {
    $('session-submit')?.addEventListener('click', createSessionAndPlan)
    $('plan-render')?.addEventListener('click', renderFromEditor)
  }

  if (!window.Presto) window.Presto = {}
  window.Presto.planflow = { init }

  document.addEventListener('DOMContentLoaded', init)
})()
