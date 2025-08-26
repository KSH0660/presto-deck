import React, { useState } from 'react';

const InputForm = ({ onSubmit, isLoading }) => {
  const [topic, setTopic] = useState('');
  const [quality, setQuality] = useState('default');
  const [ordered, setOrdered] = useState(false); // false: fastest-first, true: deck-order

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!topic.trim()) {
      alert('Please enter a topic.');
      return;
    }
    onSubmit(topic, quality, ordered);
  };

  return (
    <div className="w-full max-w-2xl mx-auto p-8 bg-gray-800 rounded-lg shadow-lg">
      <form onSubmit={handleSubmit}>
        <div className="mb-6">
          <label htmlFor="topic" className="block mb-2 text-sm font-medium text-gray-300">
            What topic would you like to create a presentation about?
          </label>
          <textarea
            id="topic"
            rows="4"
            className="block p-2.5 w-full text-sm text-gray-900 bg-gray-50 rounded-lg border border-gray-300 focus:ring-blue-500 focus:border-blue-500"
            placeholder="e.g., 'The history of artificial intelligence'"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            disabled={isLoading}
          />
        </div>

        <div className="mb-6">
          <label className="block mb-2 text-sm font-medium text-gray-300">Streaming Order</label>
          <div className="flex justify-center space-x-2 p-1 bg-gray-700 rounded-lg">
            <button
              type="button"
              onClick={() => setOrdered(false)}
              className={`w-full px-4 py-2 text-sm font-medium rounded-md transition-colors ${!ordered ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}
              disabled={isLoading}
            >
              Fastest-first
            </button>
            <button
              type="button"
              onClick={() => setOrdered(true)}
              className={`w-full px-4 py-2 text-sm font-medium rounded-md transition-colors ${ordered ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}
              disabled={isLoading}
            >
              Deck-order
            </button>
          </div>
        </div>

        <div className="mb-6">
          <label className="block mb-2 text-sm font-medium text-gray-300">Quality Tier</label>
          <div className="flex justify-center space-x-2 p-1 bg-gray-700 rounded-lg">
            {['draft', 'default', 'premium'].map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => setQuality(q)}
                className={`w-full px-4 py-2 text-sm font-medium rounded-md transition-colors ${quality === q ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'}`}
                disabled={isLoading}
              >
                {q.charAt(0).toUpperCase() + q.slice(1)}
              </button>
            ))}
          </div>
        </div>

        <button
          type="submit"
          className="w-full text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:ring-blue-300 font-medium rounded-lg text-sm px-5 py-2.5 text-center disabled:bg-gray-500 disabled:cursor-not-allowed"
          disabled={isLoading}
        >
          {isLoading ? 'Generating...' : 'Generate Presentation'}
        </button>
      </form>
    </div>
  );
};

export default InputForm;
