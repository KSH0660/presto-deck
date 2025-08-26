import { useState } from 'react';
import axios from 'axios';

import InputForm from './components/InputForm';
import Loader from './components/Loader';
import PresentationViewer from './components/PresentationViewer';
import StreamingViewer from './components/StreamingViewer';

function App() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [presentation, setPresentation] = useState(null);
  const [streamParams, setStreamParams] = useState(null); // { topic, quality, ordered }

  const handleGenerate = async (topic, quality, ordered) => {
    // Switch to streaming mode: render slides as they are ready
    setError(null);
    setPresentation(null);
    setStreamParams({ topic, quality, ordered });
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
            setStreamParams(null);
          }}
          onReset={handleReset}
        />
      );
    }

    if (isLoading) return <Loader />;
    if (presentation) {
      return <PresentationViewer presentation={presentation} onReset={handleReset} />;
    }
    return <InputForm onSubmit={handleGenerate} isLoading={isLoading} />;
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white flex flex-col items-center justify-center p-4">
      <div className="w-full h-full flex flex-col items-center">
        {!presentation && (
            <h1 className="text-4xl font-bold mb-8">Presto - AI Presentation Generator</h1>
        )}
        {error && <p className="text-red-500 mb-4">{error}</p>}
        <div className="w-full h-full flex items-center justify-center">
            {renderContent()}
        </div>
      </div>
    </div>
  );
}

export default App;
