import React, { useEffect, useRef, useState } from 'react';

// Very small SSE parser for fetch streaming
function parseSSE(buffer, onEvent) {
  // Split by double newlines to get complete events
  const events = buffer.split('\n\n');
  // Keep last fragment (possibly incomplete)
  const remainder = events.pop();

  for (const evt of events) {
    const lines = evt.split('\n');
    let type = 'message';
    const dataLines = [];
    for (const line of lines) {
      if (line.startsWith('event:')) {
        type = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trim());
      }
    }
    const dataStr = dataLines.join('\n');
    try {
      const data = dataStr ? JSON.parse(dataStr) : null;
      onEvent(type, data);
    } catch {
      onEvent(type, { raw: dataStr });
    }
  }

  return remainder || '';
}

const StreamingViewer = ({ topic, quality = 'default', ordered = false, onCompleted, onReset }) => {
  // Keep both sequences so we can toggle view ordering live
  const [arrivalSlides, setArrivalSlides] = useState([]); // completed slides in arrival order
  const [deckSlides, setDeckSlides] = useState([]); // array sized to total, may contain null placeholders
  const slidesRef = useRef({ arrival: [], deck: [] });
  const [deckPlan, setDeckPlan] = useState(null);
  const [progress, setProgress] = useState({ completed: 0, total: 0 });
  const [error, setError] = useState(null);
  const [started, setStarted] = useState(false);
  const [displayMode, setDisplayMode] = useState(ordered ? 'deck' : 'arrival'); // 'arrival' | 'deck'

  const controllerRef = useRef(null);
  const bufferRef = useRef('');

  useEffect(() => {
    const controller = new AbortController();
    controllerRef.current = controller;

    const run = async () => {
      try {
        const resp = await fetch('/api/v1/generate-stream', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream'
          },
          signal: controller.signal,
          body: JSON.stringify({
            user_request: topic,
            quality,
            ordered
          })
        });

        if (!resp.ok || !resp.body) {
          throw new Error('Streaming request failed');
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder('utf-8');

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          bufferRef.current += chunk;
          bufferRef.current = parseSSE(bufferRef.current, (type, data) => {
            if (type === 'started') {
              setStarted(true);
              const totalSlides = data?.total_slides || 0;
              setProgress((p) => ({ ...p, total: totalSlides }));
              if (totalSlides > 0) {
                const placeholders = new Array(totalSlides).fill(null);
                setDeckSlides(placeholders);
                slidesRef.current.deck = placeholders.slice();
              }
            } else if (type === 'deck_plan') {
              setDeckPlan(data);
            } else if (type === 'slide_rendered') {
              const slideObj = { slide_id: data.slide_id, template_name: data.template_name, html: data.html, index: data.index };
              // Update arrival order list
              setArrivalSlides((prev) => {
                const next = [...prev, slideObj];
                slidesRef.current.arrival = next;
                return next;
              });
              // Update deck order list at its index
              setDeckSlides((prev) => {
                const next = prev.length ? prev.slice() : [];
                if (typeof data.index === 'number') {
                  next[data.index] = slideObj;
                } else {
                  // Fallback: push if index missing
                  next.push(slideObj);
                }
                slidesRef.current.deck = next;
                return next;
              });
            } else if (type === 'progress') {
              setProgress({ completed: data?.completed || 0, total: data?.total || 0 });
            } else if (type === 'error') {
              setError((e) => e || data?.message || 'Slide render error');
            } else if (type === 'completed') {
              // Assemble final deck in deck order for the viewer
              let finalSlides = slidesRef.current.deck;
              if (deckPlan && Array.isArray(deckPlan.slides)) {
                const byId = new Map((finalSlides || []).filter(Boolean).map(s => [s.slide_id, s]));
                finalSlides = deckPlan.slides.map(spec => byId.get(spec.slide_id)).filter(Boolean);
              } else {
                finalSlides = (finalSlides || []).filter(Boolean);
              }
              const final = { ...(deckPlan || {}), slides: finalSlides };
              onCompleted && onCompleted(final);
            }
          });
        }
      } catch (e) {
        if (e.name !== 'AbortError') {
          setError('Stream interrupted');
        }
      }
    };

    run();
    return () => controller.abort();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topic, quality]);

  const total = progress.total || (deckPlan?.slides?.length ?? 0);
  const completed = progress.completed || arrivalSlides.length;
  const pct = total ? Math.round((completed / total) * 100) : 0;

  const displaySlides = displayMode === 'deck' ? deckSlides : arrivalSlides;

  return (
    <div className="w-full h-full flex flex-col items-center justify-start p-4 overflow-auto">
      <div className="w-full max-w-6xl mb-4">
        <h2 className="text-2xl font-bold">Generating...</h2>
        <div className="text-xs text-gray-400 mt-1 flex items-center gap-2">
          <span>Order:</span>
          <div className="inline-flex bg-gray-800 rounded overflow-hidden">
            <button
              className={`px-2 py-1 text-xs ${displayMode === 'arrival' ? 'bg-blue-600' : ''}`}
              onClick={() => setDisplayMode('arrival')}
            >
              Fastest-first
            </button>
            <button
              className={`px-2 py-1 text-xs ${displayMode === 'deck' ? 'bg-blue-600' : ''}`}
              onClick={() => setDisplayMode('deck')}
            >
              Deck-order
            </button>
          </div>
        </div>
        <p className="text-sm text-gray-300 mt-1">{topic}</p>
        <div className="w-full bg-gray-700 rounded h-2 mt-3">
          <div className="bg-blue-500 h-2 rounded" style={{ width: `${pct}%` }} />
        </div>
        <div className="text-xs text-gray-400 mt-1">{completed} / {total} slides</div>
        {error && <div className="text-red-400 mt-2">{error}</div>}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6 w-full max-w-7xl">
        {displaySlides.map((slide, idx) => (
          <div key={slide?.slide_id ?? `ph-${idx}`} className="aspect-video bg-black rounded-lg shadow-lg relative">
            {slide ? (
              <iframe
                srcDoc={slide.html}
                title={`Slide ${slide.slide_id}`}
                className="w-full h-full border-0 rounded-md bg-white"
                sandbox="allow-scripts"
              />
            ) : (
              <div className="w-full h-full border-0 rounded-md bg-gray-200 animate-pulse" />
            )}
          </div>
        ))}
      </div>

      <div className="mt-6 flex gap-3">
        <button
          onClick={onReset}
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-md text-sm font-medium"
        >
          Cancel
        </button>
      </div>
    </div>
  );
};

export default StreamingViewer;
