import React, { useEffect, useState } from 'react';
import { listEntries, clearAll } from '../lib/cache';

const formatTime = (ts) => {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return '';
  }
};

const HistoryPanel = ({ visible, onSelect, onClose }) => {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [quality, setQuality] = useState('all'); // all | draft | default | premium

  const load = async () => {
    setLoading(true);
    try {
      const entries = await listEntries();
      // newest first (listEntries returns arbitrary order)
      entries.sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
      setItems(entries);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (visible) load();
  }, [visible]);

  if (!visible) return null;

  const filtered = items.filter((e) => {
    const q = query.trim().toLowerCase();
    const matchText = [
      e.meta?.topic,
      e.deck?.topic,
      e.deck?.audience,
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();
    const passQuery = !q || matchText.includes(q);
    const passQuality = quality === 'all' || (e.meta?.quality || 'default') === quality;
    return passQuery && passQuality;
  });

  return (
    <div className="fixed inset-0 z-40 flex">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black bg-opacity-50" onClick={onClose} />

      {/* Panel */}
      <div className="relative ml-auto w-full max-w-md h-full bg-gray-900 shadow-xl z-50 flex flex-col">
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <h3 className="text-lg font-semibold">작업 히스토리</h3>
          <button onClick={onClose} className="text-gray-300 hover:text-white">✕</button>
        </div>
        <div className="px-4 pt-3 pb-2 flex items-center gap-2 border-b border-gray-800">
          <input
            type="text"
            placeholder="주제/청중 검색"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 px-3 py-2 rounded bg-gray-800 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <select
            value={quality}
            onChange={(e) => setQuality(e.target.value)}
            className="px-2 py-2 rounded bg-gray-800 text-sm"
          >
            <option value="all">All</option>
            <option value="draft">Draft</option>
            <option value="default">Default</option>
            <option value="premium">Premium</option>
          </select>
        </div>
        <div className="p-4 flex-1 overflow-auto">
          {loading ? (
            <div className="text-gray-400">불러오는 중...</div>
          ) : filtered.length === 0 ? (
            <div className="text-gray-400">히스토리가 없습니다.</div>
          ) : (
            <ul className="space-y-3">
              {filtered.map((e) => {
                const first = e.deck?.slides?.[0];
                return (
                  <li key={e.key} className="p-3 bg-gray-800 rounded-md hover:bg-gray-700 transition-colors">
                    <div className="flex items-start gap-3">
                      <div className="w-24 h-16 bg-black rounded overflow-hidden flex-shrink-0">
                        {first ? (
                          <iframe
                            title={`thumb-${e.key}`}
                            className="w-full h-full border-0 bg-white"
                            srcDoc={first.html}
                            sandbox="allow-scripts"
                          />
                        ) : (
                          <div className="w-full h-full bg-gray-700" />
                        )}
                      </div>
                      <div className="flex-1">
                        <div className="font-medium truncate" title={e.meta?.topic || e.deck?.topic || 'Untitled'}>
                          {e.meta?.topic || e.deck?.topic || 'Untitled'}
                        </div>
                        <div className="text-xs text-gray-400 mt-1">
                          {(e.meta?.quality || 'default')} • {formatTime(e.updatedAt)}
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          {e.deck?.slides?.length || 0} slides
                        </div>
                      </div>
                      <div>
                        <button
                          className="px-3 py-1 text-sm bg-blue-600 hover:bg-blue-700 rounded"
                          onClick={() => onSelect && onSelect(e.deck)}
                        >
                          열기
                        </button>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        {items.length > 0 && (
          <div className="p-3 border-t border-gray-800 flex justify-end">
            <button
              className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 rounded"
              onClick={async () => { await clearAll(); load(); }}
            >
              모두 지우기
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default HistoryPanel;
