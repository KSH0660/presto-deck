// frontend/js/alpine.js
//
// 한국어 설명: Alpine 컴포넌트 정의(생성, 편집)를 담당합니다.

;(function () {
  const API = (window.Presto && window.Presto.API) || `${location.origin}/api/v1`

  function prestoApp() {
    return {
      selectedLabel: 'No slide selected',
      _editing: false,
      _editAbort: null,
      init() {
        document.addEventListener('presto:selected', (e) => {
          const id = e.detail?.id
          this.selectedLabel = id ? `Selected #${id}` : 'No slide selected'
        })
      },
      async submitEdit() {
        const applyBtn = document.querySelector('#edit-slide-form button[type="submit"]')
        const generateBtn = document.getElementById('generate-btn')
        const exportBtn = document.getElementById('export-html-btn')

        // 이미 편집 중이면 취소로 동작
        if (this._editing) {
          try {
            this._editAbort?.abort()
          } catch {}
          this._editing = false
          this._editAbort = null
          if (applyBtn) {
            applyBtn.disabled = false
            applyBtn.textContent = 'Apply Edit'
          }
          if (generateBtn) generateBtn.disabled = false
          if (exportBtn) exportBtn.disabled = false
          await window.Presto?.slides?.fetchAndRenderSlides()
          return
        }

        const id = Number(document.getElementById('edit-slide-id').value)
        const prompt = document.getElementById('edit-slide-prompt').value.trim()
        if (!id || !prompt) {
          alert('Select a slide and enter an instruction.')
          return
        }
        const card = document.getElementById(`slide-${id}`)
        if (!card) {
          alert('Could not find the selected slide card.')
          return
        }

        const originalApplyText = applyBtn ? applyBtn.textContent : null
        this._editing = true
        if (applyBtn) {
          applyBtn.disabled = false
          applyBtn.textContent = 'Cancel'
        }
        if (generateBtn) generateBtn.disabled = true
        if (exportBtn) exportBtn.disabled = true

        card.classList.add('editing')
        const slideContentDiv = card.querySelector('.slide-content')
        slideContentDiv.innerHTML = '<div class="spinner"></div><p>Editing...</p>'

        const payload = { edit_prompt: prompt }
        const controller = new AbortController()
        this._editAbort = controller

        try {
          const res = await fetch(`${API}/slides/${id}/edit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            signal: controller.signal,
          })
          if (!res.ok) {
            const err = await res.text()
            alert(`Edit failed: ${err}`)
            return
          }
          const updated = await res.json()
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
                ${updated.html_content}
              </body>
            </html>`
          iframe.srcdoc = iframeContent
          slideContentDiv.innerHTML = ''
          slideContentDiv.appendChild(iframe)
          const codeElement = card.querySelector('.code-view code')
          if (codeElement) codeElement.textContent = updated.html_content
        } catch (error) {
          console.error('Error submitting edit:', error)
          if (error?.name === 'AbortError') {
            await window.Presto?.slides?.fetchAndRenderSlides()
          } else {
            alert('An error occurred while editing the slide.')
          }
        } finally {
          card.classList.remove('editing')
          if (applyBtn) {
            applyBtn.disabled = false
            if (originalApplyText !== null) applyBtn.textContent = originalApplyText
          }
          if (generateBtn) generateBtn.disabled = false
          if (exportBtn) exportBtn.disabled = false
          this._editing = false
          this._editAbort = null
        }
      },
      async generate() {
        const userPromptInput = document.getElementById('user-prompt')
        const generateBtn = document.getElementById('generate-btn')
        const statusText = document.getElementById('status-text')
        const progressBarContainer = document.getElementById('progress-bar-container')
        const progressBar = document.getElementById('progress-bar')
        const slidesArea = document.getElementById('slides-area')

        const userPrompt = userPromptInput.value.trim()
        if (!userPrompt) {
          alert('Please enter a topic for your presentation.')
          return
        }
        generateBtn.disabled = true
        statusText.textContent = 'Generating presentation...'
        progressBarContainer.classList.remove('hidden')
        progressBar.style.width = '0%'
        slidesArea.innerHTML = ''

        try {
          const response = await fetch(`${API}/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_prompt: userPrompt, config: { quality: 'default', ordered: false } }),
          })
          if (!response.ok) {
            const err = await response.json()
            throw new Error(err.detail || 'Failed to start generation.')
          }
          if (!response.headers.get('content-type').includes('text/event-stream')) {
            throw new Error('Expected text/event-stream, but received ' + response.headers.get('content-type'))
          }
          const reader = response.body.getReader()
          const decoder = new TextDecoder('utf-8')
          let buffer = ''
          statusText.textContent = 'Connection established. Receiving events...'
          while (true) {
            const { value, done } = await reader.read()
            if (done) break
            buffer += decoder.decode(value, { stream: true })
            let eventEndIndex
            while ((eventEndIndex = buffer.indexOf('\n\n')) !== -1) {
              const eventString = buffer.substring(0, eventEndIndex)
              buffer = buffer.substring(eventEndIndex + 2)
              let eventName = 'message'
              let eventData = ''
              eventString.split('\n').forEach((line) => {
                if (line.startsWith('event:')) eventName = line.substring(6).trim()
                else if (line.startsWith('data:')) eventData = line.substring(5).trim()
              })
              try {
                const parsed = JSON.parse(eventData)
                document.dispatchEvent(new CustomEvent(eventName, { detail: parsed }))
              } catch {}
            }
          }
        } catch (error) {
          console.error('Error during generation:', error)
          statusText.textContent = `Error: ${error.message}`
        } finally {
          generateBtn.disabled = false
          progressBarContainer.classList.add('hidden')
        }
      },
    }
  }

  // 전역 공개 (Alpine에서 x-data="prestoApp()" 로 접근)
  window.prestoApp = prestoApp
})()
