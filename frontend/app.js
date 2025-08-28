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


    promptForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const userPrompt = userPromptInput.value.trim();
        if (!userPrompt) {
            alert('Please enter a topic for your presentation.');
            return;
        }

        // Disable button and clear previous results
        generateBtn.disabled = true;
        statusText.textContent = 'Generating presentation...';
        progressBarContainer.classList.remove('hidden');
        progressBar.style.width = '0%';
        slidesArea.innerHTML = '';

        try {
            const response = await fetch('http://127.0.0.1:8000/api/v1/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_prompt: userPrompt,
                    config: {
                        quality: 'default',
                        ordered: false // Stream slides as they are ready
                    }
                }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to start generation.');
            }

            if (!response.headers.get('content-type').includes('text/event-stream')) {
                throw new Error('Expected text/event-stream, but received ' + response.headers.get('content-type'));
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';

            statusText.textContent = 'Connection established. Receiving events...';

            while (true) {
                const { value, done } = await reader.read();
                if (done) {
                    console.log('Stream complete.');
                    break;
                }

                buffer += decoder.decode(value, { stream: true });

                let eventEndIndex;
                while ((eventEndIndex = buffer.indexOf('\n\n')) !== -1) {
                    const eventString = buffer.substring(0, eventEndIndex);
                    buffer = buffer.substring(eventEndIndex + 2);
                    let eventName = 'message';
                    let eventData = '';

                    eventString.split('\n').forEach(line => {
                        if (line.startsWith('event:')) {
                            eventName = line.substring(6).trim();
                        } else if (line.startsWith('data:')) {
                            eventData = line.substring(5).trim();
                        }
                    });

                    try {
                        const parsedData = JSON.parse(eventData);
                        const customEvent = new CustomEvent(eventName, { detail: parsedData });
                        document.dispatchEvent(customEvent);
                    } catch (err) {
                        console.error('Failed to parse event data:', eventData, err);
                    }
                }
            }

        } catch (error) {
            console.error('Error during generation:', error);
            statusText.textContent = `Error: ${error.message}`;
        } finally {
            generateBtn.disabled = false;
            progressBarContainer.classList.add('hidden');
        }
    });

    // Centralized event listeners for custom events
    document.addEventListener('started', (event) => {
        const data = event.detail;
        console.log('Started event:', data);
        statusText.textContent = `Generating ${data.total_slides || '...'} slides...`;
    });

    document.addEventListener('deck_plan', (event) => {
        const data = event.detail;
        console.log('Deck Plan event:', data);
        statusText.textContent = `Deck plan ready. Generating ${data.slides.length} slides.`;
        slidesArea.innerHTML = ''; // Clear any previous placeholders

        data.slides.forEach(slide => {
            const slideCard = document.createElement('div');
            slideCard.id = `slide-${slide.slide_id}`;
            slideCard.classList.add('slide-card');
            slideCard.innerHTML = `
                <h2>${slide.title || 'Untitled Slide'}</h2>
                <div class="slide-content loading"></div>
            `;
            slidesArea.appendChild(slideCard);

            // Add click listener to open modal
            slideCard.addEventListener('click', () => {
                const iframe = slideCard.querySelector('iframe');
                if (iframe && iframe.srcdoc) { // Ensure iframe is rendered and has content
                    openModalWithSlide(iframe.srcdoc);
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
});
