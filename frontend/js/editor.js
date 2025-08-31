;(function () {
  function qs(sel, root) { return (root || document).querySelector(sel) }
  function getParam(name) { return new URLSearchParams(location.search).get(name) }
  function setStatus(msg) { const el = qs('#status'); if (el) el.textContent = msg }

  const API = `${location.origin}/api/v1`

  let editor
  let deckId = null
  let slideId = null
  let initialHtml = ''
  let initialTitle = ''

  function buildPreviewDoc(html, extraCss) {
    const baseCss = `body{margin:0;padding:20px;font-family:'Segoe UI',sans-serif;color:#333}img{max-width:100%;height:auto}table{width:100%;border-collapse:collapse}th,td{border:1px solid #ddd;padding:8px}`
    const style = `<style>${baseCss}\n${extraCss || ''}</style>`
    return `<!DOCTYPE html><html><head>${style}</head><body>${html || ''}</body></html>`
  }

  function refreshPreview() {
    const html = editor.getHtml()
    const css = editor.getCss()
    const iframe = qs('#preview-frame')
    if (iframe) iframe.srcdoc = buildPreviewDoc(html, css)
  }

  async function loadSlide() {
    setStatus('Loading slide...')
    let slide
    if (deckId) {
      const resp = await fetch(`${API}/decks/${deckId}/slides/${slideId}`)
      if (!resp.ok) throw new Error(await resp.text())
      slide = await resp.json()
    } else {
      const resp = await fetch(`/api/v1/ui/slides/${slideId}/json`)
      if (!resp.ok) throw new Error(await resp.text())
      slide = await resp.json()
    }
    initialHtml = slide.html_content || ''
    initialTitle = slide.title || ''
    qs('#slide-title').value = initialTitle

    // Init editor
    editor = grapesjs.init({
      container: '#gjs',
      height: '100%',
      fromElement: false,
      storageManager: { type: null },
      plugins: ['gjs-preset-webpage'],
      pluginsOpts: { 'gjs-preset-webpage': {} },
    })
    editor.setComponents(initialHtml)
    refreshPreview()

    // Update preview on content changes
    editor.on('update', refreshPreview)
    setStatus(deckId ? `Editing deck ${deckId} · slide #${slideId}` : `Editing slide #${slideId}`)
  }

  async function saveSlide() {
    const btn = qs('#save-btn')
    if (btn) btn.disabled = true
    setStatus('Saving...')
    try {
      const html = editor.getHtml()
      const css = editor.getCss()
      const title = qs('#slide-title').value.trim()
      const payload = {
        html_content: (css ? `<style>${css}</style>` : '') + html,
        title: title || undefined,
        commit_message: 'grapesjs_editor',
      }
      const url = deckId ? `${API}/decks/${deckId}/slides/${slideId}` : `/api/v1/ui/slides/${slideId}/json`
      const resp = await fetch(url, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      if (!resp.ok) throw new Error(await resp.text())
      setStatus('Saved ✓')
      // After save, keep preview in sync
      refreshPreview()
      setTimeout(() => setStatus(deckId ? `Editing deck ${deckId} · slide #${slideId}` : `Editing slide #${slideId}`), 1200)
    } catch (e) {
      console.error(e)
      setStatus('Save failed')
    } finally {
      if (btn) btn.disabled = false
    }
  }

  function init() {
    deckId = getParam('deck_id')
    slideId = getParam('slide_id')
    if (!slideId) {
      setStatus('Missing slide_id in URL')
      return
    }
    qs('#back-link').href = '/'
    qs('#save-btn').addEventListener('click', saveSlide)
    loadSlide().catch((e) => {
      console.error(e)
      setStatus('Failed to load slide')
    })
  }

  document.addEventListener('DOMContentLoaded', init)
})()
