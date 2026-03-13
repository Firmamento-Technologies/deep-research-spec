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
    if (score >= 0.8) return 'bg-drs-green/20 text-drs-green';
    if (score >= 0.6) return 'bg-drs-yellow/20 text-drs-yellow';
    return 'bg-drs-red/20 text-drs-red';
  };

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-drs-text mb-4">
          Semantic Search
        </h1>

        {/* Search Input */}
        <div className="relative">
          <Search className="absolute left-4 top-3.5 w-5 h-5 text-drs-faint" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search your knowledge base..."
            className="w-full pl-12 pr-4 py-3 bg-drs-s1 border border-drs-border rounded-lg text-drs-text placeholder-drs-faint focus:ring-2 focus:ring-drs-accent focus:border-drs-accent outline-none text-lg"
            autoFocus
          />
        </div>
      </div>

      {/* Results */}
      <div>
        {isLoading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-drs-accent" />
          </div>
        ) : results && results.length > 0 ? (
          <div className="space-y-4">
            {results.map((result) => (
              <Card key={result.chunk_id} className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <FileText className="w-5 h-5 text-drs-faint" />
                    <div>
                      <h3 className="font-medium text-drs-text">
                        {result.filename}
                      </h3>
                      {result.page_number && (
                        <p className="text-sm text-drs-muted">
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
                <p className="text-drs-muted leading-relaxed">
                  {result.content}
                </p>
              </Card>
            ))}
          </div>
        ) : debouncedQuery ? (
          <div className="text-center py-16">
            <Search className="w-16 h-16 text-drs-faint mx-auto mb-4" />
            <h3 className="text-lg font-medium text-drs-text mb-2">
              No results found
            </h3>
            <p className="text-drs-muted">
              Try adjusting your search query
            </p>
          </div>
        ) : (
          <div className="text-center py-16">
            <Search className="w-16 h-16 text-drs-faint mx-auto mb-4" />
            <h3 className="text-lg font-medium text-drs-text mb-2">
              Start searching
            </h3>
            <p className="text-drs-muted">
              Enter a query to search your knowledge base
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
