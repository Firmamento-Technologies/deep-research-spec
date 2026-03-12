import React, { useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '../lib/query';
import { Upload, FileText, Trash2, Search } from '../lib/icons';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { api } from '../lib/api';

interface Source {
  id: string;
  filename: string;
  file_type: string;
  status: 'processing' | 'ready' | 'failed';
  chunk_count: number;
  created_at: string;
}

interface Space {
  id: string;
  name: string;
  description?: string;
  source_count: number;
}

export const SpaceDetail: React.FC = () => {
  const { spaceId } = useParams() as { spaceId?: string };
  const navigate = useNavigate();
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<Map<string, number>>(new Map());
  const queryClient = useQueryClient();

  // Fetch space details
  const { data: space } = useQuery<Space>({
    queryKey: ['space', spaceId],
    queryFn: async () => {
      const res = await api.get(`/api/spaces/${spaceId}`);
      return res.data;
    },
  });

  // Fetch sources (poll every 5s during processing)
  const { data: sources } = useQuery<Source[]>({
    queryKey: ['sources', spaceId],
    queryFn: async () => {
      const res = await api.get(`/api/spaces/${spaceId}/sources`);
      return res.data;
    },
    refetchInterval: (data) => {
      return data?.some(s => s.status === 'processing') ? 5000 : false;
    },
  });

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: async (files: FileList) => {
      const promises = Array.from(files).map(async (file) => {
        const formData = new FormData();
        formData.append('file', file);

        return api.post(`/api/spaces/${spaceId}/sources`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: (event: { loaded: number; total?: number }) => {
            if (event.total) {
              const progress = (event.loaded / event.total) * 100;
              setUploadProgress(prev => new Map(prev).set(file.name, progress));
            }
          },
        });
      });

      return Promise.all(promises);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources', spaceId] });
      queryClient.invalidateQueries({ queryKey: ['space', spaceId] });
      setUploadProgress(new Map());
    },
  });

  // Delete source mutation
  const deleteMutation = useMutation({
    mutationFn: async (sourceId: string) => {
      await api.delete(`/api/spaces/${spaceId}/sources/${sourceId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sources', spaceId] });
    },
  });

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files.length > 0) {
      uploadMutation.mutate(e.dataTransfer.files);
    }
  }, [uploadMutation]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      uploadMutation.mutate(e.target.files);
    }
  };

  const getStatusBadge = (status: Source['status']) => {
    const styles = {
      processing: 'bg-drs-yellow/20 text-drs-yellow',
      ready: 'bg-drs-green/20 text-drs-green',
      failed: 'bg-drs-red/20 text-drs-red',
    };
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${styles[status]}`}>
        {status}
      </span>
    );
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-drs-text">
          {space?.name || 'Loading...'}
        </h1>
        {space?.description && (
          <p className="mt-2 text-drs-muted">
            {space.description}
          </p>
        )}
        <div className="mt-4 flex gap-4">
          <Button
            onClick={() => navigate(`/spaces/${spaceId}/search`)}
            className="flex items-center gap-2"
          >
            <Search className="w-4 h-4" />
            Search
          </Button>
        </div>
      </div>

      {/* Upload Zone */}
      <Card className="mb-8">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragOver(true);
          }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-lg p-12 text-center transition ${
            isDragOver ? 'border-drs-accent bg-drs-accent/10' : 'border-drs-border'
          }`}
        >
          <Upload className="w-12 h-12 text-drs-faint mx-auto mb-4" />
          <h3 className="text-lg font-medium text-drs-text mb-2">
            Upload Documents
          </h3>
          <p className="text-drs-muted mb-4">
            Drag and drop files here, or click to browse
          </p>
          <input
            type="file"
            multiple
            accept=".pdf,.docx,.txt,.md,.html"
            onChange={handleFileSelect}
            className="hidden"
            id="file-upload"
          />
          <label htmlFor="file-upload">
            <Button as="span" className="cursor-pointer">
              Select Files
            </Button>
          </label>
          <p className="text-xs text-drs-faint mt-4">
            Supported: PDF, DOCX, TXT, MD, HTML (max 50MB)
          </p>
        </div>

        {/* Upload Progress */}
        {uploadProgress.size > 0 && (
          <div className="mt-4 space-y-2">
            {Array.from(uploadProgress.entries()).map(([filename, progress]) => (
              <div key={filename}>
                <div className="flex justify-between text-sm mb-1 text-drs-text">
                  <span>{filename}</span>
                  <span>{Math.round(progress)}%</span>
                </div>
                <div className="w-full bg-drs-s3 rounded-full h-2">
                  <div
                    className="bg-drs-accent h-2 rounded-full transition-all"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Sources List */}
      <div>
        <h2 className="text-xl font-semibold text-drs-text mb-4">
          Sources ({sources?.length || 0})
        </h2>
        {sources && sources.length > 0 ? (
          <div className="grid grid-cols-1 gap-4">
            {sources.map((source) => (
              <Card key={source.id} className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <FileText className="w-8 h-8 text-drs-faint" />
                  <div>
                    <h3 className="font-medium text-drs-text">
                      {source.filename}
                    </h3>
                    <div className="flex items-center gap-2 mt-1">
                      {getStatusBadge(source.status)}
                      <span className="text-sm text-drs-muted">
                        {source.chunk_count} chunks
                      </span>
                      <span className="text-xs text-drs-faint">
                        {new Date(source.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => deleteMutation.mutate(source.id)}
                  className="p-2 text-drs-faint hover:text-drs-red transition"
                  aria-label="Delete source"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </Card>
            ))}
          </div>
        ) : (
          <p className="text-drs-muted text-center py-8">
            No sources uploaded yet. Upload documents to get started.
          </p>
        )}
      </div>
    </div>
  );
};
