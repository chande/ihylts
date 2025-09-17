import React, { useState, useEffect, useMemo } from 'react';
import { Search, Calendar, ExternalLink, Loader, Filter } from 'lucide-react';
import './index.css';

const exactSearch = (items, query, options = {}) => {
  const {
    searchIn = ['title', 'text'],
    caseSensitive = false,
    wholeWord = false,
    limit = 20
  } = options;

  if (!query || !query.trim()) return [];

  const searchTerm = caseSensitive ? query.trim() : query.trim().toLowerCase();
  
  const wordBoundaryRegex = wholeWord 
    ? new RegExp(`\\b${searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, caseSensitive ? 'g' : 'gi')
    : null;

  const results = items
    .map(item => {
      let score = 0;
      let matchedFields = [];
      let matchContext = {};

      searchIn.forEach(field => {
        const fieldValue = item[field] || '';
        const searchValue = caseSensitive ? fieldValue : fieldValue.toLowerCase();
        
        let hasMatch = false;
        if (wholeWord && wordBoundaryRegex) {
          hasMatch = wordBoundaryRegex.test(fieldValue);
          wordBoundaryRegex.lastIndex = 0; // Reset regex
        } else {
          hasMatch = searchValue.includes(searchTerm);
        }

        if (hasMatch) {
          matchedFields.push(field);
          
          if (field === 'title') {
            score += 10;
            if (searchValue.startsWith(searchTerm)) score += 5;
          } else {
            score += 1;
          }

          if (field === 'text') {
            const index = searchValue.indexOf(searchTerm);
            const start = Math.max(0, index - 40);
            const end = Math.min(fieldValue.length, index + searchTerm.length + 40);
            matchContext[field] = {
              before: fieldValue.slice(start, index),
              match: fieldValue.slice(index, index + searchTerm.length),
              after: fieldValue.slice(index + searchTerm.length, end)
            };
          }
        }
      });

      return {
        item,
        score,
        matchedFields,
        matchContext
      };
    })
    .filter(result => result.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);

  return results;
};

function App() {
  const [comics, setComics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [searchOptions, setSearchOptions] = useState({
    searchInTitle: true,
    searchInText: true,
    caseSensitive: false,
    wholeWord: false
  });
  const [showOptions, setShowOptions] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);

  useEffect(() => {
    const loadComics = async () => {
      try {
        const response = await fetch('http://localhost:5000/api/comics/searchable');
        const data = await response.json();
        
        setComics(data);
        console.log(`Loaded ${data.length} comics (${(JSON.stringify(data).length / 1024).toFixed(1)} KB)`);
      } catch (error) {
        console.error('Failed to load comics:', error);
      } finally {
        setLoading(false);
      }
    };

    loadComics();
  }, []);

  const searchResults = useMemo(() => {
    if (!query.trim()) return [];
    
    const searchIn = [];
    if (searchOptions.searchInTitle) searchIn.push('title');
    if (searchOptions.searchInText) searchIn.push('text');
    
    if (searchIn.length === 0) return [];

    const startTime = performance.now();
    const results = exactSearch(comics, query, {
      searchIn,
      caseSensitive: searchOptions.caseSensitive,
      wholeWord: searchOptions.wholeWord,
      limit: 25
    });
    const searchTime = performance.now() - startTime;
    
    console.log(`Search for "${query}" took ${searchTime.toFixed(2)}ms, found ${results.length} results`);
    
    return results;
  }, [comics, query, searchOptions]);

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setFocusedIndex(prev => Math.min(prev + 1, searchResults.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setFocusedIndex(prev => Math.max(prev - 1, -1));
    } else if (e.key === 'Enter' && focusedIndex >= 0) {
      window.open(searchResults[focusedIndex].item.url, '_blank');
    } else if (e.key === 'Escape') {
      setQuery('');
      setFocusedIndex(-1);
    }
  };

  useEffect(() => {
    setFocusedIndex(-1);
  }, [searchResults]);

  const highlightMatch = (text, searchTerm, caseSensitive = false) => {
    if (!searchTerm) return text;
    
    const parts = text.split(new RegExp(`(${searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, caseSensitive ? 'g' : 'gi'));
    
    return parts.map((part, index) => {
      const isMatch = caseSensitive 
        ? part === searchTerm 
        : part.toLowerCase() === searchTerm.toLowerCase();
      
      return isMatch ? (
        <mark key={index} className="bg-yellow-200 font-semibold">{part}</mark>
      ) : (
        part
      );
    });
  };

  return (
    <div className="max-w-3xl mx-auto p-6">
      <div className="mb-8 text-center">
        <div className="flex items-baseline justify-center space-x-2">
          <div className="text-2xl font-bold text-gray-900">I Hope You Like Text</div>
          <div style={{ fontSize: '12px', fontWeight: 'bold' }}>(Search)</div>
        </div>
        <p className="text-gray-600">
          {loading ? 'Loading comics...' : ``}
        </p>
      </div>

      <div className="relative">
        {/* Search Input with Options */}
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            {loading ? (
              <Loader className="h-5 w-5 text-gray-400 animate-spin" />
            ) : (
              <Search className="h-5 w-5 text-gray-400" />
            )}
          </div>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={loading ? "Loading comics..." : "Search for exact text..."}
            disabled={loading}
            className="block w-full pl-10 pr-20 py-3 border border-gray-300 rounded-lg leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-lg"
          />
          <div className="absolute inset-y-0 right-0 flex items-center pr-2">
            {query && (
              <button
                onClick={() => setQuery('')}
                className="p-1 text-gray-400 hover:text-gray-600 mr-1"
              >
                ✕
              </button>
            )}
            <button
              onClick={() => setShowOptions(!showOptions)}
              className={`p-2 rounded ${showOptions ? 'bg-blue-100 text-blue-600' : 'text-gray-400 hover:text-gray-600'}`}
              title="Search options"
            >
              <Filter className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Search Options Panel */}
        {showOptions && (
          <div className="mt-2 p-3 bg-gray-50 border border-gray-200 rounded-lg">
            <div className="grid grid-cols-2 gap-3">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={searchOptions.searchInTitle}
                  onChange={(e) => setSearchOptions(prev => ({ ...prev, searchInTitle: e.target.checked }))}
                  className="mr-2"
                />
                <span className="text-sm">Search in titles</span>
              </label>
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={searchOptions.searchInText}
                  onChange={(e) => setSearchOptions(prev => ({ ...prev, searchInText: e.target.checked }))}
                  className="mr-2"
                />
                <span className="text-sm">Search in text</span>
              </label>
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={searchOptions.caseSensitive}
                  onChange={(e) => setSearchOptions(prev => ({ ...prev, caseSensitive: e.target.checked }))}
                  className="mr-2"
                />
                <span className="text-sm">Case sensitive</span>
              </label>
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={searchOptions.wholeWord}
                  onChange={(e) => setSearchOptions(prev => ({ ...prev, wholeWord: e.target.checked }))}
                  className="mr-2"
                />
                <span className="text-sm">Whole words only</span>
              </label>
            </div>
          </div>
        )}

        {/* Search Results */}
        {query && searchResults.length > 0 && (
          <div className="absolute z-10 mt-2 w-full bg-white shadow-lg rounded-lg border border-gray-200 max-h-96 overflow-auto search-results">
            <div className="sticky top-0 bg-gray-50 px-4 py-2 border-b border-gray-200">
              <span className="text-sm text-gray-600">
                Found {searchResults.length} result{searchResults.length !== 1 ? 's' : ''} for "{query}"
              </span>
            </div>
            {searchResults.map((result, index) => (
              <a
                key={result.item.id}
                href={result.item.url}
                target="_blank"
                rel="noopener noreferrer"
                className={`block px-4 py-3 hover:bg-gray-50 border-b border-gray-100 last:border-b-0 ${
                  index === focusedIndex ? 'bg-blue-50' : ''
                }`}
                onMouseEnter={() => setFocusedIndex(index)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900">
                      {result.matchedFields.includes('title') 
                        ? highlightMatch(result.item.title, query, searchOptions.caseSensitive)
                        : result.item.title}
                    </p>
                    {result.matchedFields.includes('text') && (
                      <p className="text-sm text-gray-600 mt-1">
                        {result.matchContext.text ? (
                          <>
                            {result.matchContext.text.before && '...'}
                            {result.matchContext.text.before}
                            <mark className="bg-yellow-200 font-semibold">
                              {result.matchContext.text.match}
                            </mark>
                            {result.matchContext.text.after}
                            {result.matchContext.text.after && '...'}
                          </>
                        ) : (
                          highlightMatch(result.item.text, query, searchOptions.caseSensitive)
                        )}
                      </p>
                    )}
                    <div className="flex items-center mt-2 text-xs text-gray-500">
                      <Calendar className="h-3 w-3 mr-1" />
                      {new Date(result.item.date).toLocaleDateString()}
                      <span className="ml-3 text-blue-600">
                        Matched in: {result.matchedFields.join(', ')}
                      </span>
                    </div>
                  </div>
                  <ExternalLink className="h-4 w-4 text-gray-400 ml-2 flex-shrink-0 mt-1" />
                </div>
              </a>
            ))}
          </div>
        )}

        {/* No Results */}
        {query && searchResults.length === 0 && !loading && (
          <div className="absolute z-10 mt-2 w-full bg-white shadow-lg rounded-lg border border-gray-200 p-4">
            <p className="text-gray-500 text-center">
              No comics found containing "{query}"
              {searchOptions.wholeWord && <span className="block text-xs mt-1">(whole word search enabled)</span>}
              {searchOptions.caseSensitive && <span className="block text-xs mt-1">(case sensitive search enabled)</span>}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
