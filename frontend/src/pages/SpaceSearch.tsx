import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '../lib/query';
import { Search, FileText } from '../lib/icons';
import { Card } from '../components/ui/Card';
import { api } from '../lib/api';
import { useDebounce } from '../hooks/useDebounce';

interface SearchResult {
  chunk_id: string;
  content: string;
  similarity: number;
  source_id: string;
  filename: string;
  page_number?: number;
}

export const SpaceSearch: React.FC = () => {
  const { spaceId } = useParams() as { spaceId?: string };
  const [query, setQuery] = useState('');
  const debouncedQuery = useDebounce(query, 500);

  // Search query
  const { data: results, isLoading } = useQuery<SearchResult[]>({
    queryKey: ['search', spaceId, debouncedQuery],
    queryFn: async () => {
      if (!debouncedQuery.trim()) return [];
      const res = await api.post(`/api/spaces/${spaceId}/search`, {
        query: debouncedQuery,
        top_k: 10,
      });
      return res.data;
    },
    enabled: !!debouncedQuery.trim(),
  });

  const getSimilarityColor = (score: number) => {
    if (score >= 0.8) return 'bg-green-100 text-green-800';
    if (score >= 0.6) return 'bg-yellow-100 text-yellow-800';
    return 'bg-red-100 text-red-800';
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-4">
          Semantic Search
        </h1>

        {/* Search Input */}
        <div className="relative">
          <Search className="absolute left-4 top-3.5 w-5 h-5 text-gray-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search your knowledge base..."
            className="w-full pl-12 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-lg"
            autoFocus
          />
        </div>
      </div>

      {/* Results */}
      <div>
        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
          </div>
        ) : results && results.length > 0 ? (
          <div className="space-y-4">
            {results.map((result) => (
              <Card key={result.chunk_id} className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <FileText className="w-5 h-5 text-gray-400" />
                    <div>
                      <h3 className="font-medium text-gray-900 dark:text-white">
                        {result.filename}
                      </h3>
                      {result.page_number && (
                        <p className="text-sm text-gray-500">
                          Page {result.page_number}
                        </p>
                      )}
                    </div>
                  </div>
                  <span
                    className={`px-3 py-1 rounded-full text-sm font-medium ${
                      getSimilarityColor(result.similarity)
                    }`}
                  >
                    {(result.similarity * 100).toFixed(0)}% match
                  </span>
                </div>
                <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                  {result.content}
                </p>
              </Card>
            ))}
          </div>
        ) : debouncedQuery ? (
          <div className="text-center py-16">
            <Search className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
              No results found
            </h3>
            <p className="text-gray-600 dark:text-gray-400">
              Try adjusting your search query
            </p>
          </div>
        ) : (
          <div className="text-center py-16">
            <Search className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
              Start searching
            </h3>
            <p className="text-gray-600 dark:text-gray-400">
              Enter a query to search your knowledge base
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
