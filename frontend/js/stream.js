// frontend/js/stream.js
;(function () {
  function $(id) { return document.getElementById(id) }

  function collectDeckPlan() {
    const form = $('deck-plan-form')
    const fd = new FormData(form)
    const topic = fd.get('topic') || ''
    const audience = fd.get('audience') || ''
    const theme = fd.get('theme') || null
    const color = fd.get('color_preference') || null
    const slides = []
    const idxs = new Set()
    for (const [k] of fd.entries()) {
      const m = k.match(/^slides\[(\d+)\]/)
      if (m) idxs.add(parseInt(m[1], 10))
    }
    Array.from(idxs).sort((a,b)=>a-b).forEach((i) => {
      const get = (name) => fd.get(`slides[${i}][${name}]`) || ''
      const slide_id = parseInt(get('slide_id') || `${i+1}`, 10)
      const title = get('title')
      const key_points_raw = get('key_points')
      const numbers_raw = get('numbers')
      const notes = get('notes') || null
      const section = get('section') || null
      const layout_raw = get('layout_candidates')
      let numbers = null
      try { numbers = numbers_raw ? JSON.parse(numbers_raw) : null } catch {}
      const key_points = (key_points_raw || '').split('\n').map(s=>s.trim()).filter(Boolean)
      const layout_candidates = (layout_raw || '').split(',').map(s=>s.trim()).filter(Boolean)
      slides.push({ slide_id, title, key_points: key_points.length?key_points:null, numbers, notes, section, layout_candidates: layout_candidates.length?layout_candidates:null })
    })
    return { topic, audience, theme, color_preference: color, slides }
  }

  async function refreshSlides() {
    try {
      const res = await fetch('/api/v1/ui/slides')
      if (!res.ok) return
      const html = await res.text()
      const area = $('slides-area')
      if (area) area.innerHTML = html
    } catch {}
  }

  async function renderFromEditor() {
    const deck_plan = collectDeckPlan()
    const payload = { user_prompt: '', deck_plan, config: { quality: 'default', ordered: false } }
    const status = $('status-text')
    const btns = document.querySelectorAll('#deck-plan-form button')
    btns.forEach(b=>b.disabled=true)
    try {
      const res = await fetch('/api/v1/slides/render/stream', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      if (!res.ok || !res.body) throw new Error('stream failed')
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      if (status) status.textContent = 'Rendering (stream)...'
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let idx
        while ((idx = buffer.indexOf('\n\n')) !== -1) {
          const chunk = buffer.slice(0, idx)
          buffer = buffer.slice(idx + 2)
          let event = 'message', data='{}'
          chunk.split('\n').forEach(line=>{
            if (line.startsWith('event:')) event = line.slice(6).trim()
            else if (line.startsWith('data:')) data = line.slice(5).trim()
          })
          if (event === 'slide_rendered') {
            // htmx SSE will trigger slides refresh
          } else if (event === 'completed') {
            // htmx SSE will trigger final refresh
            try { const d = JSON.parse(data); if (status) status.textContent = `Completed in ${Math.round((d.duration_ms||0)/1000)}s` } catch {}
          }
        }
      }
    } catch (e) {
      if (status) status.textContent = 'Stream error'
    } finally {
      btns.forEach(b=>b.disabled=false)
    }
  }

  window.PrestoStream = { renderFromEditor }
})()
