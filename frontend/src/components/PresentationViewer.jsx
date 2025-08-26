import React, { useState } from 'react';

const PresentationViewer = ({ presentation, onReset }) => {
  const [currentSlide, setCurrentSlide] = useState(0);

  const goToNext = () => {
    setCurrentSlide((prev) => Math.min(prev + 1, presentation.slides.length - 1));
  };

  const goToPrevious = () => {
    setCurrentSlide((prev) => Math.max(prev - 1, 0));
  };

  const slide = presentation.slides[currentSlide];

  return (
    <div className="w-full h-full flex flex-col items-center justify-center p-4">
      {/* Slide container with 16:9 aspect ratio */}
      <div className="w-full max-w-6xl aspect-video bg-black rounded-lg shadow-lg mb-4">
        <iframe
          srcDoc={slide.html}
          title={`Slide ${slide.slide_id}`}
          className="w-full h-full border-0 rounded-md bg-white"
          sandbox="allow-scripts"
        />
      </div>

      {/* Controls container */}
      <div className="w-full max-w-6xl flex items-center justify-between text-white">
        <button
          onClick={onReset}
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-md text-sm font-medium transition-colors"
        >
          New Presentation
        </button>
        <div className="flex items-center space-x-4">
          <button
            onClick={goToPrevious}
            disabled={currentSlide === 0}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-md disabled:bg-gray-500 disabled:cursor-not-allowed transition-colors"
          >
            Previous
          </button>
          <span className="text-sm font-mono">
            {currentSlide + 1} / {presentation.slides.length}
          </span>
          <button
            onClick={goToNext}
            disabled={currentSlide === presentation.slides.length - 1}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-md disabled:bg-gray-500 disabled:cursor-not-allowed transition-colors"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
};

export default PresentationViewer;
