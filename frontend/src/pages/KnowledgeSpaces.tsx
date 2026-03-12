import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '../lib/query';
import { Plus, Folder, Trash2, Search } from '../lib/icons';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Modal } from '../components/ui/Modal';
import { api } from '../lib/api';

interface KnowledgeSpace {
  id: string;
  name: string;
  description?: string;
  source_count: number;
  created_at: string;
}

export const KnowledgeSpaces: React.FC = () => {
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [newSpaceName, setNewSpaceName] = useState('');
  const [newSpaceDesc, setNewSpaceDesc] = useState('');
  const [createError, setCreateError] = useState<string | null>(null);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Fetch spaces — queryFn must be stable to avoid infinite re-fetch
  const fetchSpaces = useCallback(async () => {
    const res = await api.get('/api/spaces');
    return res.data;
  }, []);

  const { data: spaces, isLoading, isError } = useQuery<KnowledgeSpace[]>({
    queryKey: ['spaces'],
    queryFn: fetchSpaces,
  });

  // Create space mutation
  const createMutation = useMutation({
    mutationFn: async (data: { name: string; description?: string }) => {
      const res = await api.post('/api/spaces', data);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['spaces'] });
      setIsCreateModalOpen(false);
      setNewSpaceName('');
      setNewSpaceDesc('');
      setCreateError(null);
    },
    onError: (err: any) => {
      setCreateError(err?.message || 'Failed to create space. Please try again.');
    },
  });

  // Delete space mutation
  const deleteMutation = useMutation({
    mutationFn: async (spaceId: string) => {
      await api.delete(`/api/spaces/${spaceId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['spaces'] });
    },
  });

  const handleCreateSpace = () => {
    if (!newSpaceName.trim()) return;
    setCreateError(null);
    createMutation.mutate({
      name: newSpaceName,
      description: newSpaceDesc || undefined,
    });
  };

  const handleDeleteSpace = (spaceId: string) => {
    if (confirm('Delete this knowledge space? All sources and chunks will be removed.')) {
      deleteMutation.mutate(spaceId);
    }
  };

  if (isLoading && !isError) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-drs-accent" />
      </div>
    );
  }

  const inputClass =
    'w-full px-3 py-2 bg-drs-s1 border border-drs-border rounded-lg text-drs-text placeholder-drs-faint focus:ring-2 focus:ring-drs-accent focus:border-drs-accent outline-none';

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-drs-text">
            Knowledge Spaces
          </h1>
          <p className="mt-2 text-drs-muted">
            Upload documents to create semantic knowledge bases for your research
          </p>
        </div>
        <Button
          onClick={() => { setCreateError(null); setIsCreateModalOpen(true); }}
          className="flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          New Space
        </Button>
      </div>

      {/* Spaces grid */}
      {spaces && spaces.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {spaces.map((space) => (
            <Card
              key={space.id}
              className="hover:border-drs-border-bright transition-colors cursor-pointer"
              onClick={() => navigate(`/spaces/${space.id}`)}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-drs-accent/15 rounded-lg">
                    <Folder className="w-6 h-6 text-drs-accent" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-drs-text">
                      {space.name}
                    </h3>
                    <p className="text-sm text-drs-muted mt-1">
                      {space.source_count} sources
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      navigate(`/spaces/${space.id}/search`);
                    }}
                    className="p-2 text-drs-faint hover:text-drs-accent transition"
                    aria-label="Search space"
                  >
                    <Search className="w-4 h-4" />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteSpace(space.id);
                    }}
                    className="p-2 text-drs-faint hover:text-drs-red transition"
                    aria-label="Delete space"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
              {space.description && (
                <p className="mt-3 text-sm text-drs-muted">
                  {space.description}
                </p>
              )}
              <div className="mt-4 text-xs text-drs-faint">
                Created {new Date(space.created_at).toLocaleDateString()}
              </div>
            </Card>
          ))}
        </div>
      ) : (
        // Empty state
        <div className="text-center py-16">
          <Folder className="w-16 h-16 text-drs-faint mx-auto mb-4" />
          <h3 className="text-lg font-medium text-drs-text mb-2">
            No knowledge spaces yet
          </h3>
          <p className="text-drs-muted mb-6">
            Create your first space to start uploading documents
          </p>
          <Button onClick={() => { setCreateError(null); setIsCreateModalOpen(true); }}>
            <Plus className="w-4 h-4 mr-2" />
            Create Space
          </Button>
        </div>
      )}

      {/* Create Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Create Knowledge Space"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-drs-muted mb-2">
              Space Name
            </label>
            <input
              type="text"
              value={newSpaceName}
              onChange={(e) => setNewSpaceName(e.target.value)}
              className={inputClass}
              placeholder="e.g., AI Research Papers"
              autoFocus
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-drs-muted mb-2">
              Description (optional)
            </label>
            <textarea
              value={newSpaceDesc}
              onChange={(e) => setNewSpaceDesc(e.target.value)}
              className={inputClass}
              placeholder="What will this space contain?"
              rows={3}
            />
          </div>
          {createError && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
              {createError}
            </div>
          )}
          <div className="flex gap-3 justify-end">
            <Button
              variant="ghost"
              onClick={() => setIsCreateModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateSpace}
              disabled={!newSpaceName.trim() || createMutation.isPending}
            >
              {createMutation.isPending ? 'Creating...' : 'Create Space'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
