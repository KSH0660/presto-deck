import React, { useState, useEffect } from 'react';

const PresentationViewer = ({ presentation, onReset }) => {
  const [selectedSlideIndex, setSelectedSlideIndex] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleThumbnailClick = (index) => {
    setIsLoading(true);
    setSelectedSlideIndex(index);
  };

  const handleBackToThumbnails = () => {
    setSelectedSlideIndex(null);
  };

  useEffect(() => {
    if (selectedSlideIndex !== null) {
      const timer = setTimeout(() => {
        setIsLoading(false);
      }, 500); // Adjust delay as needed
      return () => clearTimeout(timer);
    }
  }, [selectedSlideIndex]);

  if (selectedSlideIndex !== null) {
    const slide = presentation.slides[selectedSlideIndex];
    const totalSlides = presentation.slides.length;

    const handlePreviousSlide = () => {
      setIsLoading(true);
      setSelectedSlideIndex((prevIndex) => Math.max(0, prevIndex - 1));
    };

    const handleNextSlide = () => {
      setIsLoading(true);
      setSelectedSlideIndex((prevIndex) => Math.min(totalSlides - 1, prevIndex + 1));
    };

    return (
      <div className="w-full h-full flex flex-col items-center justify-center p-4">
        <div className="relative w-full max-w-6xl aspect-video bg-black rounded-lg shadow-lg mb-4">
          <iframe
            srcDoc={slide.html}
            title={`Slide ${slide.slide_id}`}
            className="w-full h-full border-0 rounded-md bg-white"
            sandbox="allow-scripts"
          />
          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-900 bg-opacity-75 rounded-lg z-10">
              <div className="animate-spin rounded-full h-12 w-12 border-4 border-t-4 border-blue-500 border-opacity-75"></div>
            </div>
          )}
          {/* Navigation Arrows */}
          <button
            onClick={handlePreviousSlide}
            disabled={selectedSlideIndex === 0}
            className="absolute left-2 top-1/2 -translate-y-1/2 bg-gray-800 bg-opacity-50 text-white p-2 rounded-full hover:bg-opacity-75 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
          >
            &lt;
          </button>
          <button
            onClick={handleNextSlide}
            disabled={selectedSlideIndex === totalSlides - 1}
            className="absolute right-2 top-1/2 -translate-y-1/2 bg-gray-800 bg-opacity-50 text-white p-2 rounded-full hover:bg-opacity-75 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
          >
            &gt;
          </button>
        </div>

        {/* Control Buttons */}
        <div className="w-full max-w-6xl flex items-center justify-between text-white mb-4">
          <button
            onClick={handleBackToThumbnails}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-md text-sm font-medium transition-colors"
          >
            Back to Thumbnails
          </button>
          <button
            onClick={onReset}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-md text-sm font-medium transition-colors"
          >
            New Presentation
          </button>
        </div>

        {/* Slide Number Navigation */}
        <div className="w-full max-w-6xl flex flex-wrap justify-center gap-2 p-2 bg-gray-800 rounded-lg overflow-x-auto">
          {presentation.slides.map((_, index) => (
            <button
              key={index}
              onClick={() => setSelectedSlideIndex(index)}
              className={`px-3 py-1 rounded-md text-sm font-medium transition-colors
                ${selectedSlideIndex === index ? 'bg-blue-600 text-white' : 'bg-gray-600 text-gray-200 hover:bg-gray-500'}`}
            >
              {index + 1}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="w-full h-full flex flex-col items-center justify-start p-4 overflow-auto">
      <h2 className="text-2xl font-bold text-white mb-6">Presentation Overview</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6 w-full max-w-7xl">
        {presentation.slides.map((slide, index) => (
          <div
            key={slide.slide_id}
            className="aspect-video bg-black rounded-lg shadow-lg cursor-pointer hover:scale-105 transition-transform duration-200 relative"
            onClick={() => handleThumbnailClick(index)}
          >
            <iframe
              srcDoc={slide.html}
              title={`Slide Thumbnail ${slide.slide_id}`}
              className="w-full h-full border-0 rounded-md bg-white pointer-events-none"
              sandbox="allow-scripts"
            />
            <div className="absolute inset-0 flex items-center justify-center text-white text-lg font-bold bg-black bg-opacity-50 opacity-0 hover:opacity-100 transition-opacity duration-200">
              Slide {index + 1}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-8">
        <button
          onClick={onReset}
          className="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-md text-lg font-medium text-white transition-colors"
        >
          New Presentation
        </button>
      </div>
    </div>
  );
};

export default PresentationViewer;
