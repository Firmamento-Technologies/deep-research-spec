import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '../lib/query';
import { Plus, Folder, Trash2 } from 'lucide-react';
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
  const queryClient = useQueryClient();

  // Fetch spaces
  const { data: spaces, isLoading } = useQuery<KnowledgeSpace[]>({
    queryKey: ['spaces'],
    queryFn: async () => {
      const res = await api.get('/api/spaces');
      return res.data;
    },
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

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            Knowledge Spaces
          </h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            Upload documents to create semantic knowledge bases for your research
          </p>
        </div>
        <Button
          onClick={() => setIsCreateModalOpen(true)}
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
              className="hover:shadow-lg transition-shadow cursor-pointer"
              onClick={() => (window.location.href = `/spaces/${space.id}`)}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-blue-100 dark:bg-blue-900 rounded-lg">
                    <Folder className="w-6 h-6 text-blue-600 dark:text-blue-300" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900 dark:text-white">
                      {space.name}
                    </h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                      {space.source_count} sources
                    </p>
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteSpace(space.id);
                  }}
                  className="p-2 text-gray-400 hover:text-red-600 transition"
                  aria-label="Delete space"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
              {space.description && (
                <p className="mt-3 text-sm text-gray-600 dark:text-gray-400">
                  {space.description}
                </p>
              )}
              <div className="mt-4 text-xs text-gray-400">
                Created {new Date(space.created_at).toLocaleDateString()}
              </div>
            </Card>
          ))}
        </div>
      ) : (
        // Empty state
        <div className="text-center py-16">
          <Folder className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            No knowledge spaces yet
          </h3>
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            Create your first space to start uploading documents
          </p>
          <Button onClick={() => setIsCreateModalOpen(true)}>
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
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Space Name
            </label>
            <input
              type="text"
              value={newSpaceName}
              onChange={(e) => setNewSpaceName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="e.g., AI Research Papers"
              autoFocus
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Description (optional)
            </label>
            <textarea
              value={newSpaceDesc}
              onChange={(e) => setNewSpaceDesc(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              placeholder="What will this space contain?"
              rows={3}
            />
          </div>
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
