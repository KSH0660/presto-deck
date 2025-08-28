// frontend/app.js

document.addEventListener('DOMContentLoaded', () => {
    const promptForm = document.getElementById('prompt-form');
    const userPromptInput = document.getElementById('user-prompt');
    const generateBtn = document.getElementById('generate-btn');
    const statusText = document.getElementById('status-text');
    const progressBarContainer = document.getElementById('progress-bar-container');
    const progressBar = document.getElementById('progress-bar');
    const slidesArea = document.getElementById('slides-area');

    // Modal elements
    const slideModal = document.getElementById('slide-modal');
    const closeModalBtn = slideModal.querySelector('.close-button');
    const modalSlideViewer = document.getElementById('modal-slide-viewer');

    const editSlideId = document.getElementById('edit-slide-id');
    const editSlidePrompt = document.getElementById('edit-slide-prompt');

    const exportHtmlBtn = document.getElementById('export-html-btn');

    const API = 'http://127.0.0.1:8000/api/v1';
    const generatedSlides = new Map(); // slide_id -> { title, html }
    let selectedId = null;

    // Centralized event listeners for custom events
    document.addEventListener('started', (event) => {
        const data = event.detail;
        console.log('Started event:', data);
        statusText.textContent = `Generation started (model: ${data.model})...`;
    });

    document.addEventListener('deck_plan', (event) => {
        const data = event.detail;
        console.log('Deck Plan event:', data);
        statusText.textContent = `Deck plan ready. Generating ${data.slides.length} slides.`;
        slidesArea.innerHTML = ''; // Clear any previous placeholders

        data.slides.forEach(slide => {
            generatedSlides.set(slide.slide_id, { title: slide.title || 'Untitled Slide', html: null });
            const slideCard = document.createElement('div');
            slideCard.id = `slide-${slide.slide_id}`;
            slideCard.classList.add('slide-card');
            slideCard.innerHTML = `
                <h2 style="display:flex;justify-content:space-between;align-items:center;margin:0;background:#059669;color:white;padding:8px 12px;font-size:1.1em;">
                    <span>${slide.title || 'Untitled Slide'}</span>
                    <span style="font-size:12px;opacity:0.9;">#${slide.slide_id}</span>
                </h2>
                <div class="slide-content loading"></div>
                <div class="card-footer">
                    <button class="btn-preview">Preview</button>
                    <button class="btn-delete danger">Delete</button>
                </div>
            `;
            slidesArea.appendChild(slideCard);

            // Click selects card; double-click previews
            slideCard.addEventListener('click', (e) => selectCard(slide.slide_id));
            slideCard.addEventListener('dblclick', () => {
                const iframe = slideCard.querySelector('iframe');
                if (iframe && iframe.srcdoc) openModalWithSlide(iframe.srcdoc);
            });
            // Footer buttons
            slideCard.querySelector('.btn-preview').addEventListener('click', (e) => {
                e.stopPropagation();
                const iframe = slideCard.querySelector('iframe');
                if (iframe && iframe.srcdoc) openModalWithSlide(iframe.srcdoc);
            });
            slideCard.querySelector('.btn-delete').addEventListener('click', async (e) => {
                e.stopPropagation();
                await deleteSlide(slide.slide_id);
            });
        });
    });

    document.addEventListener('slide_rendered', (event) => {
        const data = event.detail;
        console.log('Slide Rendered event:', data);
        const slideCard = document.getElementById(`slide-${data.slide_id}`);
        if (slideCard) {
            const slideContentDiv = slideCard.querySelector('.slide-content');
            slideContentDiv.classList.remove('loading');

            const iframe = document.createElement('iframe');
            iframe.scrolling = 'no'; // Disable scrolling on the preview iframe

            // It's crucial to have a proper HTML structure for srcdoc
            const iframeContent = `
                <!DOCTYPE html>
                <html>
                <head>
                    <style>
                        /* Basic styles for consistent preview */
                        body { margin: 0; padding: 20px; font-family: 'Segoe UI', sans-serif; color: #333; transform: scale(0.9); transform-origin: top left; }
                        img { max-width: 100%; height: auto; }
                        table { width: 100%; border-collapse: collapse; }
                        th, td { border: 1px solid #ddd; padding: 8px; }
                    </style>
                </head>
                <body>
                    ${data.html}
                </body>
                </html>
            `;
            iframe.srcdoc = iframeContent;
            slideContentDiv.innerHTML = '';
            slideContentDiv.appendChild(iframe);
        }
        // Cache HTML for save/select workflow
        const meta = generatedSlides.get(data.slide_id);
        if (meta) meta.html = data.html;
    });

    document.addEventListener('progress', (event) => {
        const data = event.detail;
        console.log('Progress event:', data);
        if (data.total > 0) {
            const percentage = (data.completed / data.total) * 100;
            progressBar.style.width = `${percentage}%`;
            statusText.textContent = `Generating slides: ${data.completed}/${data.total} (${data.stage})...`;
        }
    });

    document.addEventListener('completed', (event) => {
        const data = event.detail;
        console.log('Completed event:', data);
        statusText.textContent = `Generation complete! Total time: ${(data.duration_ms / 1000).toFixed(2)}s`;
        generateBtn.disabled = false;
        progressBarContainer.classList.add('hidden');
    });

    document.addEventListener('error', (event) => {
        const data = event.detail;
        console.error('Error event:', data);
        statusText.textContent = `Error: ${data.message || 'An unknown error occurred.'}`;
        generateBtn.disabled = false;
        progressBarContainer.classList.add('hidden');
    });

    // --- Modal Logic ---
    function openModalWithSlide(slideHtml) {
        modalSlideViewer.innerHTML = ''; // Clear previous content
        const modalIframe = document.createElement('iframe');
        modalIframe.srcdoc = slideHtml; // Use the same srcdoc from the card
        modalSlideViewer.appendChild(modalIframe);
        slideModal.classList.add('visible');
    }

    function closeModal() {
        slideModal.classList.remove('visible');
        modalSlideViewer.innerHTML = ''; // Clear content for performance
    }

    // Modal close listeners
    closeModalBtn.addEventListener('click', closeModal);

    slideModal.addEventListener('click', (e) => {
        // Close if clicking on the dark overlay itself, not the content
        if (e.target === slideModal) {
            closeModal();
        }
    });

    // Allow closing the modal with the Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && slideModal.classList.contains('visible')) {
            closeModal();
        }
    });

    exportHtmlBtn?.addEventListener('click', () => {
        window.open(`${API}/export/html`, '_blank');
    });

    function selectCard(id) {
        // Visual selection
        if (selectedId !== null) {
            const prev = document.getElementById(`slide-${selectedId}`);
            prev?.classList.remove('selected');
        }
        selectedId = id;
        document.getElementById(`slide-${id}`)?.classList.add('selected');
        // Fill edit ID
        editSlideId.value = String(id);
        // Update Alpine label if present
        document.dispatchEvent(new CustomEvent('presto:selected', { detail: { id } }));
    }

    async function deleteSlide(id) {
        try {
            const res = await fetch(`${API}/slides/${id}/delete`, { method: 'DELETE' });
            // Remove card regardless of 404 (not saved yet)
            const el = document.getElementById(`slide-${id}`);
            el?.remove();
            generatedSlides.delete(id);
            if (selectedId === id) {
                selectedId = null;
                editSlideId.value = '';
                document.dispatchEvent(new CustomEvent('presto:selected', { detail: { id: null } }));
            }
        } catch (e) {
            // noop
        }
    }
});

// Alpine component providing methods used in the template
function prestoApp() {
    const API = 'http://127.0.0.1:8000/api/v1';
    return {
        selectedLabel: 'No slide selected',
        init() {
            document.addEventListener('presto:selected', (e) => {
                const id = e.detail?.id;
                this.selectedLabel = id ? `Selected #${id}` : 'No slide selected';
            });
        },
        async submitEdit() {
            const id = Number(document.getElementById('edit-slide-id').value);
            const prompt = document.getElementById('edit-slide-prompt').value.trim();
            if (!id || !prompt) { alert('Select a slide and enter an instruction.'); return; }
            // Get current HTML shown in the card (client hint)
            const card = document.getElementById(`slide-${id}`);
            const iframe = card?.querySelector('iframe');
            const hintHtml = iframe?.srcdoc ? extractBodyFromSrcdoc(iframe.srcdoc) : '';
            const payload = { edit_prompt: prompt, client_html_hint: hintHtml };
            const res = await fetch(`${API}/slides/${id}/edit`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
            });
            if (!res.ok) { const err = await res.text(); alert(`Edit failed: ${err}`); return; }
            const combined = await res.text();
            const updated = extractSlideFromCombined(combined, id);
            if (updated) {
                // Replace card content
                const iframeContent = `<!DOCTYPE html><html><head><style>body{margin:0;padding:20px;font-family:'Segoe UI',sans-serif;color:#333;transform:scale(0.9);transform-origin:top left;}img{max-width:100%;height:auto;}table{width:100%;border-collapse:collapse;}th,td{border:1px solid #ddd;padding:8px;}</style></head><body>${updated}</body></html>`;
                const targetIframe = card.querySelector('iframe') || document.createElement('iframe');
                targetIframe.srcdoc = iframeContent;
                const contentDiv = card.querySelector('.slide-content');
                contentDiv.innerHTML = '';
                contentDiv.appendChild(targetIframe);
            } else {
                alert('Could not parse edited slide.');
            }
        },
        async generate() {
            const userPromptInput = document.getElementById('user-prompt');
            const generateBtn = document.getElementById('generate-btn');
            const statusText = document.getElementById('status-text');
            const progressBarContainer = document.getElementById('progress-bar-container');
            const progressBar = document.getElementById('progress-bar');
            const slidesArea = document.getElementById('slides-area');

            const userPrompt = userPromptInput.value.trim();
            if (!userPrompt) { alert('Please enter a topic for your presentation.'); return; }

            generateBtn.disabled = true;
            statusText.textContent = 'Generating presentation...';
            progressBarContainer.classList.remove('hidden');
            progressBar.style.width = '0%';
            slidesArea.innerHTML = '';

            try {
                const response = await fetch(`${API}/generate`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_prompt: userPrompt, config: { quality: 'default', ordered: false } }),
                });
                if (!response.ok) { const err = await response.json(); throw new Error(err.detail || 'Failed to start generation.'); }
                if (!response.headers.get('content-type').includes('text/event-stream')) {
                    throw new Error('Expected text/event-stream, but received ' + response.headers.get('content-type'));
                }
                const reader = response.body.getReader();
                const decoder = new TextDecoder('utf-8');
                let buffer = '';
                statusText.textContent = 'Connection established. Receiving events...';
                while (true) {
                    const { value, done } = await reader.read();
                    if (done) break;
                    buffer += decoder.decode(value, { stream: true });
                    let eventEndIndex;
                    while ((eventEndIndex = buffer.indexOf('\n\n')) !== -1) {
                        const eventString = buffer.substring(0, eventEndIndex);
                        buffer = buffer.substring(eventEndIndex + 2);
                        let eventName = 'message'; let eventData = '';
                        eventString.split('\n').forEach(line => {
                            if (line.startsWith('event:')) eventName = line.substring(6).trim();
                            else if (line.startsWith('data:')) eventData = line.substring(5).trim();
                        });
                        try { const parsed = JSON.parse(eventData); document.dispatchEvent(new CustomEvent(eventName, { detail: parsed })); } catch {}
                    }
                }
            } catch (error) {
                console.error('Error during generation:', error);
                document.getElementById('status-text').textContent = `Error: ${error.message}`;
            } finally {
                document.getElementById('generate-btn').disabled = false;
                document.getElementById('progress-bar-container').classList.add('hidden');
            }
        }
    };
}

function extractSlideFromCombined(htmlText, slideId) {
    try {
        const wrapper = document.createElement('div');
        wrapper.innerHTML = htmlText;
        const node = wrapper.querySelector(`#slide-${slideId} > div`);
        return node ? node.innerHTML : null;
    } catch { return null; }
}

function extractBodyFromSrcdoc(srcdoc) {
    try {
        const start = srcdoc.indexOf('<body>');
        const end = srcdoc.indexOf('</body>');
        if (start !== -1 && end !== -1) return srcdoc.slice(start + 6, end);
        return srcdoc;
    } catch { return ''; }
}
