import { useState } from 'react';
import axios from 'axios';

import InputForm from './components/InputForm';
import Loader from './components/Loader';
import PresentationViewer from './components/PresentationViewer';

function App() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [presentation, setPresentation] = useState(null);

  const handleGenerate = async (topic, quality) => {
    setIsLoading(true);
    setError(null);
    setPresentation(null);

    try {
      const response = await axios.post('/api/v1/generate', {
        user_request: topic,
        quality: quality,
      });
      setPresentation(response.data);
    } catch (err) {
      setError('Failed to generate presentation. Please try again.');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = () => {
    setPresentation(null);
    setError(null);
  };

  const renderContent = () => {
    if (isLoading) {
      return <Loader />;
    }
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
