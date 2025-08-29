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

    // Use same-origin API base to avoid CORS and host mismatches
    const API = `${location.origin}/api/v1`;
    const generatedSlides = new Map(); // slide_id -> { title, html }
    let selectedId = null;
    let pollInterval = null; // For polling slide status

    // Function to fetch and render all slides
    async function fetchAndRenderSlides() {
        try {
            const response = await fetch(`${API}/slides`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const slides = await response.json();
            slidesArea.innerHTML = ''; // Clear current slides
            generatedSlides.clear(); // Clear map to resync

            slides.forEach(slide => {
                generatedSlides.set(slide.id, { title: slide.title, html: slide.html_content, status: slide.status });
                const slideCard = document.createElement('div');
                slideCard.id = `slide-${slide.id}`;
                slideCard.classList.add('slide-card');
                if (slide.status === 'editing') {
                    slideCard.classList.add('editing');
                }
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
                `;
                slidesArea.appendChild(slideCard);

                const slideContentDiv = slideCard.querySelector('.slide-content');
                if (slide.html_content) {
                    const iframe = document.createElement('iframe');
                    iframe.scrolling = 'no';
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
                    `;
                    iframe.srcdoc = iframeContent;
                    slideContentDiv.innerHTML = '';
                    slideContentDiv.appendChild(iframe);

                    const codeElement = slideCard.querySelector('.code-view code');
                    if (codeElement) {
                        codeElement.textContent = slide.html_content;
                    }
                } else if (slide.status === 'editing') {
                    slideContentDiv.innerHTML = '<div class="spinner"></div><p>Editing...</p>';
                } else {
                    slideContentDiv.innerHTML = '<p>No content yet.</p>';
                }

                // Re-attach event listeners for dynamically created cards
                slideCard.querySelector('.btn-toggle-code').addEventListener('click', (e) => {
                    e.stopPropagation();
                    const codeView = slideCard.querySelector('.code-view');
                    const button = e.target;
                    if (codeView.style.display === 'none') {
                        codeView.style.display = 'block';
                        button.textContent = 'Hide';
                    } else {
                        codeView.style.display = 'none';
                        button.textContent = 'Code';
                    }
                });

                slideCard.addEventListener('click', (e) => selectCard(slide.id));
                slideCard.addEventListener('dblclick', () => {
                    const iframe = slideCard.querySelector('iframe');
                    if (iframe && iframe.srcdoc) openModalWithSlide(iframe.srcdoc);
                });
                slideCard.querySelector('.btn-preview').addEventListener('click', (e) => {
                    e.stopPropagation();
                    const iframe = slideCard.querySelector('iframe');
                    if (iframe && iframe.srcdoc) openModalWithSlide(iframe.srcdoc);
                });
                slideCard.querySelector('.btn-delete').addEventListener('click', async (e) => {
                    e.stopPropagation();
                    await deleteSlide(slide.id);
                });
            });
        } catch (error) {
            console.error('Error fetching slides:', error);
        }
    }

    // Initial fetch of slides when the page loads
    fetchAndRenderSlides();

    // Periodically fetch slides if there are any in editing state
    // This will be started/stopped by submitEdit
    function startPollingSlides() {
        if (pollInterval) clearInterval(pollInterval);
        pollInterval = setInterval(fetchAndRenderSlides, 2000); // Poll every 2 seconds
    }

    function stopPollingSlides() {
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
    }

    // Expose helpers to global so Alpine component can call them
    window.fetchAndRenderSlides = fetchAndRenderSlides;
    window.startPollingSlides = startPollingSlides;
    window.stopPollingSlides = stopPollingSlides;

    // Centralized event listeners for custom events
    document.addEventListener('started', (event) => {
        const data = event.detail;
        console.log('Started event:', data);
        statusText.textContent = `Generation started (model: ${data.model})...`;
    });

    document.addEventListener('deck_plan', async (event) => {
        const data = event.detail;
        console.log('Deck Plan event:', data);
        statusText.textContent = `Deck plan ready. Generating ${data.slides.length} slides.`;
        // Fetch and render slides based on the new deck plan
        await fetchAndRenderSlides();
    });

    document.addEventListener('slide_rendered', async (event) => {
        const data = event.detail;
        console.log('Slide Rendered event:', data);
        // Re-fetch and render all slides to update the specific slide
        await fetchAndRenderSlides();
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
    const API = `${location.origin}/api/v1`;
    return {
        selectedLabel: 'No slide selected',
        init() {
            document.addEventListener('presto:selected', (e) => {
                const id = e.detail?.id;
                this.selectedLabel = id ? `Selected #${id}` : 'No slide selected';
            });
        },
        async submitEdit() {
            console.log("submitEdit called");
            const id = Number(document.getElementById('edit-slide-id').value);
            const prompt = document.getElementById('edit-slide-prompt').value.trim();
            if (!id || !prompt) {
                alert('Select a slide and enter an instruction.');
                return;
            }
            const card = document.getElementById(`slide-${id}`);
            if (!card) {
                alert('Could not find the selected slide card.');
                return;
            }

            // Visual feedback: Add editing class and spinner
            card.classList.add('editing');
            const slideContentDiv = card.querySelector('.slide-content');
            slideContentDiv.innerHTML = '<div class="spinner"></div><p>Editing...</p>';

            const payload = { edit_prompt: prompt };

            // Start polling for status updates
            window.startPollingSlides?.();

            try {
                const res = await fetch(`${API}/slides/${id}/edit`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (!res.ok) {
                    const err = await res.text();
                    alert(`Edit failed: ${err}`);
                    return;
                }

                // After successful edit, stop polling and re-render all slides
                window.stopPollingSlides?.();
                await window.fetchAndRenderSlides?.();

            } catch (error) {
                console.error('Error submitting edit:', error);
                alert('An error occurred while editing the slide.');
            } finally {
                // Ensure editing class is removed even if an error occurs
                card.classList.remove('editing');
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
