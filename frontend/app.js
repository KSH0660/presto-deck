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

    // New controls
    const refreshSlidesBtn = document.getElementById('refresh-slides-btn');
    const exportHtmlBtn = document.getElementById('export-html-btn');
    const serverSlides = document.getElementById('server-slides');

    const newSlideForm = document.getElementById('new-slide-form');
    const newSlideTitle = document.getElementById('new-slide-title');
    const newSlideHtml = document.getElementById('new-slide-html');

    const editSlideForm = document.getElementById('edit-slide-form');
    const editSlideId = document.getElementById('edit-slide-id');
    const editSlideVersion = document.getElementById('edit-slide-version');
    const editSlidePrompt = document.getElementById('edit-slide-prompt');

    const loadMetaBtn = document.getElementById('load-meta-btn');
    const loadTemplatesBtn = document.getElementById('load-templates-btn');
    const progressDemoBtn = document.getElementById('progress-demo-btn');
    const systemOutput = document.getElementById('system-output');

    const API = 'http://127.0.0.1:8000/api/v1';
    const generatedSlides = new Map(); // slide_id -> { title, html, serverId }

    // HTMX is used for fetching slides and creating slides now.

    async function editSlide(id, prompt, version) {
        const payload = { edit_prompt: prompt };
        if (version) payload.client_version = Number(version);
        const res = await fetch(`${API}/slides/${id}/edit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error(`Failed to edit slide #${id}`);
        const html = await res.text();
        serverSlides.innerHTML = html;
    }

    async function loadMeta() {
        const res = await fetch(`${API}/meta`);
        if (!res.ok) throw new Error('Failed to load meta');
        return res.json();
    }

    async function loadTemplates() {
        const res = await fetch(`${API}/templates`);
        if (!res.ok) throw new Error('Failed to load templates');
        return res.json();
    }

    // Progress demo is handled via HTMX SSE in the HTML.

    // Wire up new controls
    // refreshSlides handled by HTMX
    exportHtmlBtn?.addEventListener('click', () => {
        window.open(`${API}/export/html`, '_blank');
    });

    // new-slide-form handled by HTMX

    // edit slide handled by Alpine (prestoApp.submitEdit)

    // Clicking on a server slide selects its ID for edit
    serverSlides?.addEventListener('click', (e) => {
        const el = e.target.closest('[id^="slide-"]');
        if (!el) return;
        const idStr = el.id.replace('slide-', '');
        if (editSlideId) editSlideId.value = idStr;
    });

    loadMetaBtn?.addEventListener('click', async () => {
        systemOutput.textContent = 'Loading meta...\n';
        try {
            const meta = await loadMeta();
            systemOutput.textContent += JSON.stringify(meta, null, 2);
        } catch (err) {
            systemOutput.textContent += err.message;
        }
    });

    loadTemplatesBtn?.addEventListener('click', async () => {
        systemOutput.textContent = 'Loading templates...\n';
        try {
            const t = await loadTemplates();
            systemOutput.textContent += JSON.stringify(t, null, 2);
        } catch (err) {
            systemOutput.textContent += err.message;
        }
    });

    // progress demo handled by Alpine toggle + HTMX SSE


    // prompt submit handled by Alpine (prestoApp.generate)

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
            generatedSlides.set(slide.slide_id, { title: slide.title || 'Untitled Slide', html: null, serverId: null });
            const slideCard = document.createElement('div');
            slideCard.id = `slide-${slide.slide_id}`;
            slideCard.classList.add('slide-card');
            slideCard.innerHTML = `
                <h2>${slide.title || 'Untitled Slide'}</h2>
                <div class="slide-content loading"></div>
                <div class="slide-actions" data-slide-id="${slide.slide_id}" style="display:flex;gap:8px;align-items:center;justify-content:flex-end;padding:6px 8px;border-top:1px solid #e5e7eb;">
                    <button class="btn-save" title="Save this generated slide to server">Save</button>
                    <button class="btn-select" title="Select this slide for editing">Select</button>
                </div>
            `;
            slidesArea.appendChild(slideCard);

            // Add click listener to open modal
            slideCard.addEventListener('click', () => {
                const iframe = slideCard.querySelector('iframe');
                if (iframe && iframe.srcdoc) { // Ensure iframe is rendered and has content
                    openModalWithSlide(iframe.srcdoc);
                }
            });

            // Action buttons (use event delegation on the card)
            slideCard.querySelector('.slide-actions').addEventListener('click', async (e) => {
                e.stopPropagation();
                const container = e.currentTarget;
                const slideId = Number(container.dataset.slideId);
                const meta = generatedSlides.get(slideId);
                if (!meta) return;
                if (e.target.classList.contains('btn-save')) {
                    if (!meta.html) { alert('Slide not rendered yet.'); return; }
                    const serverId = await saveGeneratedSlideToServer(meta.title, meta.html);
                    if (serverId) {
                        meta.serverId = serverId;
                        // Auto-fill edit ID
                        editSlideId.value = String(serverId);
                        // Visual feedback
                        e.target.textContent = 'Saved';
                        e.target.disabled = true;
                    }
                } else if (e.target.classList.contains('btn-select')) {
                    if (meta.serverId) {
                        editSlideId.value = String(meta.serverId);
                    } else {
                        if (!meta.html) { alert('Slide not rendered yet.'); return; }
                        if (confirm('This slide is not saved on the server. Save now and select for edit?')) {
                            const serverId = await saveGeneratedSlideToServer(meta.title, meta.html);
                            if (serverId) {
                                meta.serverId = serverId;
                                editSlideId.value = String(serverId);
                                const saveBtn = container.querySelector('.btn-save');
                                if (saveBtn) { saveBtn.textContent = 'Saved'; saveBtn.disabled = true; }
                            }
                        }
                    }
                }
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

    // After HTMX swaps server slides (creating a new slide), auto-fill Edit Slide ID
    document.body.addEventListener('htmx:afterSwap', (evt) => {
        try {
            const path = evt.detail?.requestConfig?.path || '';
            const target = evt.detail?.target;
            if (target && target.id === 'server-slides' && path.endsWith('/slides/new')) {
                const html = target.innerHTML;
                const ids = Array.from(html.matchAll(/id=\"slide-(\d+)\"/g)).map(m => Number(m[1]));
                if (ids.length) {
                    const maxId = Math.max(...ids);
                    editSlideId.value = String(maxId);
                }
            }
        } catch {}
    });

    async function saveGeneratedSlideToServer(title, htmlContent) {
        try {
            const form = new FormData();
            form.append('title', title);
            form.append('html_content', htmlContent);
            const res = await fetch(`${API}/slides/new`, { method: 'POST', body: form });
            if (!res.ok) throw new Error('Failed to save slide');
            const html = await res.text();
            // Update server slides panel
            serverSlides.innerHTML = html;
            // Extract highest slide id as the newly created one
            const ids = Array.from(html.matchAll(/id=\"slide-(\d+)\"/g)).map(m => Number(m[1]));
            if (ids.length) return Math.max(...ids);
            return null;
        } catch (e) {
            alert(e.message);
            return null;
        }
    }
});

// Alpine component providing methods used in the template
function prestoApp() {
    const API = 'http://127.0.0.1:8000/api/v1';
    return {
        showProgress: false,
        toggleProgress() { this.showProgress = !this.showProgress; },
        async submitEdit() {
            const id = Number(document.getElementById('edit-slide-id').value);
            const version = document.getElementById('edit-slide-version').value;
            const prompt = document.getElementById('edit-slide-prompt').value.trim();
            if (!id || !prompt) return;
            const payload = { edit_prompt: prompt };
            if (version) payload.client_version = Number(version);
            const res = await fetch(`${API}/slides/${id}/edit`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
            });
            if (!res.ok) { alert(`Failed to edit slide #${id}`); return; }
            const html = await res.text();
            document.getElementById('server-slides').innerHTML = html;
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
