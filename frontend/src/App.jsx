import { useEffect, useState } from 'react';
import axios from 'axios';

import InputForm from './components/InputForm';
import Loader from './components/Loader';
import PresentationViewer from './components/PresentationViewer';
import StreamingViewer from './components/StreamingViewer';
import { getDeck, setDeck } from './lib/cache';
import { computeDeckKey } from './lib/hash';
import HistoryPanel from './components/HistoryPanel';

function App() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [presentation, setPresentation] = useState(null);
  const [streamParams, setStreamParams] = useState(null); // { topic, quality, ordered, cacheKey }
  const [templateSig, setTemplateSig] = useState('');
  const [qualityModels, setQualityModels] = useState(null);
  const [showHistory, setShowHistory] = useState(false);

  // Fetch meta to build a cache signature that changes when templates change
  useEffect(() => {
    const fetchMeta = async () => {
      try {
        const [meta, templates] = await Promise.all([
          axios.get('/api/v1/meta'),
          axios.get('/api/v1/templates'),
        ]);
        const names = (templates.data?.templates || []).join('|');
        setTemplateSig(`${names}#${templates.data?.templates?.length || 0}`);
        setQualityModels(meta.data?.quality_tiers || null);
      } catch (e) {
        setTemplateSig('');
        setQualityModels(null);
      }
    };
    fetchMeta();
  }, []);

  const handleGenerate = async (topic, quality, ordered) => {
    setError(null);
    setPresentation(null);
    // Try cache first
    const model = qualityModels?.[quality]?.model;
    const cacheKey = computeDeckKey({ topic, quality, templateSig, model });
    try {
      const cached = await getDeck(cacheKey);
      if (cached?.deck) {
        setPresentation(cached.deck);
        return;
      }
    } catch {}
    // Fallback to streaming generation
    setStreamParams({ topic, quality, ordered, cacheKey });
  };

  const handleReset = () => {
    setPresentation(null);
    setError(null);
    setStreamParams(null);
  };

  const renderContent = () => {
    // While streaming, show the streaming viewer
    if (streamParams && !presentation) {
      return (
        <StreamingViewer
          topic={streamParams.topic}
          quality={streamParams.quality}
          ordered={streamParams.ordered}
          onCompleted={(finalDeck) => {
            setPresentation(finalDeck);
            if (streamParams.cacheKey) {
              setDeck(streamParams.cacheKey, finalDeck, {
                topic: streamParams.topic,
                quality: streamParams.quality,
                ordered: streamParams.ordered,
                savedAt: Date.now(),
              });
            }
            setStreamParams(null);
          }}
          onReset={handleReset}
        />
      );
    }

    if (isLoading) return <Loader />;
    if (presentation) {
      return (
        <PresentationViewer
          presentation={presentation}
          onReset={handleReset}
          onUpdate={(next) => setPresentation(next)}
        />
      );
    }
    return <InputForm onSubmit={handleGenerate} isLoading={isLoading} />;
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white flex flex-col items-stretch p-4">
      <div className="w-full flex items-center justify-between mb-4">
        <h1 className="text-2xl sm:text-3xl font-bold">Presto - AI Presentation Generator</h1>
        <div className="flex items-center gap-2">
          <button
            className="px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded text-sm"
            onClick={() => setShowHistory(true)}
          >
            작업 히스토리
          </button>
        </div>
      </div>
      {error && <p className="text-red-500 mb-4">{error}</p>}
      <div className="flex-1 w-full flex items-stretch justify-center">
        {renderContent()}
      </div>
      <HistoryPanel
        visible={showHistory}
        onClose={() => setShowHistory(false)}
        onSelect={(deck) => { setPresentation(deck); setStreamParams(null); setShowHistory(false); }}
      />
    </div>
  );
}

export default App;
