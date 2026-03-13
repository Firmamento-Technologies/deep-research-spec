import React, { useState } from 'react';
import { Download } from '../lib/icons';
import { Modal } from './ui/Modal';
import { Button } from './ui/Button';
import { api } from '../lib/api';

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  runId: string;
  runTitle: string;
}

type ExportFormat = 'pdf' | 'docx' | 'markdown';
type CitationStyle = 'APA' | 'MLA' | 'Chicago';

const selectClass =
  'w-full px-3 py-2 bg-drs-s1 border border-drs-border rounded-lg text-drs-text focus:ring-2 focus:ring-drs-accent outline-none';

export const ExportModal: React.FC<ExportModalProps> = ({
  isOpen,
  onClose,
  runId,
  runTitle,
}) => {
  const [format, setFormat] = useState<ExportFormat>('pdf');
  const [citationStyle, setCitationStyle] = useState<CitationStyle>('APA');
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleExport = async () => {
    setIsExporting(true);
    setError(null);

    try {
      // Construct URL
      const url = `/api/runs/${runId}/export/${format}`;
      const params = format !== 'markdown' ? { citation_style: citationStyle } : {};

      // Fetch file
      const response = await api.get(url, {
        params,
        responseType: 'blob',
      });

      // Trigger download
      const blob = new Blob([response.data]);
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = `${runTitle.replace(/\s+/g, '_')}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(downloadUrl);

      // Close modal
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Export failed. Please try again.');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Export Document">
      <div className="space-y-4">
        {/* Format selector */}
        <div>
          <label className="block text-sm font-medium text-drs-muted mb-2">
            Export Format
          </label>
          <select
            value={format}
            onChange={(e) => setFormat(e.target.value as ExportFormat)}
            className={selectClass}
          >
            <option value="pdf">PDF (.pdf)</option>
            <option value="docx">Microsoft Word (.docx)</option>
            <option value="markdown">Markdown (.md)</option>
          </select>
          <p className="mt-1 text-xs text-drs-faint">
            {format === 'pdf' && 'Professional PDF with formatting and citations'}
            {format === 'docx' && 'Editable Word document'}
            {format === 'markdown' && 'Plain text with Markdown formatting'}
          </p>
        </div>

        {/* Citation style (only for PDF/DOCX) */}
        {format !== 'markdown' && (
          <div>
            <label className="block text-sm font-medium text-drs-muted mb-2">
              Citation Style
            </label>
            <select
              value={citationStyle}
              onChange={(e) => setCitationStyle(e.target.value as CitationStyle)}
              className={selectClass}
            >
              <option value="APA">APA (7th edition)</option>
              <option value="MLA">MLA (9th edition)</option>
              <option value="Chicago">Chicago (17th edition)</option>
            </select>
          </div>
        )}

        {/* Error message */}
        {error && (
          <div className="p-3 bg-drs-red/15 border border-drs-red/30 rounded-lg text-sm text-drs-red">
            {error}
          </div>
        )}

        {/* Export button */}
        <div className="flex gap-3 justify-end pt-4">
          <Button variant="ghost" onClick={onClose} disabled={isExporting}>
            Cancel
          </Button>
          <Button
            onClick={handleExport}
            disabled={isExporting}
            className="flex items-center gap-2"
          >
            {isExporting ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                Exporting...
              </>
            ) : (
              <>
                <Download className="w-4 h-4" />
                Export as {format.toUpperCase()}
              </>
            )}
          </Button>
        </div>
      </div>
    </Modal>
  );
};
