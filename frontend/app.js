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

            // Check if the response is a stream
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

                // Process events from the buffer
                let eventEndIndex;
                while ((eventEndIndex = buffer.indexOf('\n\n')) !== -1) {
                    const eventString = buffer.substring(0, eventEndIndex);
                    buffer = buffer.substring(eventEndIndex + 2); // +2 for \n\n
                    let eventName = 'message'; // Default event name
                    let eventData = '';

                    eventString.split('\n').forEach(line => {
                        if (line.startsWith('event:')) {
                            eventName = line.substring(6).trim();
                        } else if (line.startsWith('data:')) {
                            eventData = line.substring(5).trim();
                        }
                    });

                    // Dispatch custom event for handling
                    const customEvent = new CustomEvent(eventName, { detail: JSON.parse(eventData) });
                    document.dispatchEvent(customEvent);
                }
            }

        } catch (error) {
            console.error('Error during generation:', error);
            statusText.textContent = `Error: ${error.message}`;
            generateBtn.disabled = false;
            progressBarContainer.classList.add('hidden');
            return;
        } finally {
            // Ensure button is re-enabled and progress bar hidden on completion or error
            generateBtn.disabled = false;
            progressBarContainer.classList.add('hidden');
        }
    });

    // Centralized event listeners for custom events dispatched from the stream reader
    document.addEventListener('started', (event) => {
        const data = event.detail;
        console.log('Started event:', data);
        statusText.textContent = `Generating ${data.total_slides || '...'} slides...`;
    });

    document.addEventListener('deck_plan', (event) => {
        const data = event.detail;
        console.log('Deck Plan event:', data);
        statusText.textContent = `Deck plan ready. Generating ${data.slides.length} slides.`;
        // Create placeholders for slides
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
                    modalSlideViewer.innerHTML = ''; // Clear previous content
                    const modalIframe = document.createElement('iframe');
                    modalIframe.style.width = '100%';
                    modalIframe.style.height = '100%';
                    modalIframe.style.border = 'none';
                    modalIframe.style.backgroundColor = 'transparent';
                    modalIframe.srcdoc = iframe.srcdoc; // Copy srcdoc
                    modalSlideViewer.appendChild(modalIframe);
                    slideModal.classList.add('visible');
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
            slideContentDiv.classList.remove('loading'); // Remove loading indicator

            const iframe = document.createElement('iframe');
            iframe.style.width = '100%';
            iframe.style.height = '100%';
            iframe.style.border = 'none';
            iframe.style.backgroundColor = 'transparent'; // Ensure background is transparent

            // Set the srcdoc with the received HTML
            // It's good practice to include basic HTML structure for srcdoc
            iframe.srcdoc = `
                <!DOCTYPE html>
                <html>
                <head>
                    <style>
                        body { margin: 0; padding: 15px; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; }
                        /* Basic styling for common elements within slides */
                        h1, h2, h3, h4, h5, h6 { color: #4CAF50; margin-top: 0; }
                        p { margin-bottom: 1em; }
                        ul, ol { margin-left: 20px; }
                        li { margin-bottom: 0.5em; }
                        img { max-width: 100%; height: auto; display: block; margin: 0 auto; }
                        table { width: 100%; border-collapse: collapse; margin-bottom: 1em; }
                        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                        th { background-color: #f2f2f2; }
                        blockquote { border-left: 4px solid #ccc; margin: 0; padding: 0 1em; color: #666; }
                        pre { background-color: #f4f4f4; padding: 10px; border-radius: 4px; overflow-x: auto; }
                        code { font-family: 'Courier New', Courier, monospace; }
                    </style>
                </head>
                <body>
                    ${data.html}
                </body>
                </html>
            `;
            slideContentDiv.innerHTML = ''; // Clear previous content
            slideContentDiv.appendChild(iframe);
        }
    });

    document.addEventListener('progress', (event) => {
        const data = event.detail;
        console.log('Progress event:', data);
        if (data.total > 0) {
            const percentage = (data.completed / data.total) * 100;
            progressBar.style.width = `${percentage}%`;
            statusText.textContent = `Generating slides: ${data.completed}/${data.total} (${data.stage})...
`;
        }
    });

    document.addEventListener('completed', (event) => {
        const data = event.detail;
        console.log('Completed event:', data);
        statusText.textContent = `Generation complete! Total time: ${data.duration_ms / 1000}s`;
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

    // Modal close listeners
    closeModalBtn.addEventListener('click', () => {
        slideModal.classList.remove('visible');
        modalSlideViewer.innerHTML = ''; // Clear content when closing
    });

    slideModal.addEventListener('click', (e) => {
        if (e.target === slideModal) { // Only close if clicking on the overlay itself
            slideModal.classList.remove('visible');
            modalSlideViewer.innerHTML = ''; // Clear content when closing
        }
    });
});
