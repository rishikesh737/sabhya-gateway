import React, { useEffect, useState } from 'react';
import { api } from '../lib/api';

const KnowledgeBase: React.FC = () => {
  const [documents, setDocuments] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDocuments = async () => {
    try {
      const data = await api.getDocuments();
      setDocuments(data.documents || []);
    } catch (err) {
      console.error("Failed to load documents", err);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];

    try {
      setUploading(true);
      setError(null);
      await api.uploadDocument(file);
      await fetchDocuments(); // Refresh list
    } catch (err) {
      setError("Upload failed. Check console for details.");
      console.error(err);
    } finally {
      setUploading(false);
      // Reset input
      e.target.value = '';
    }
  };

  const handleDelete = async (filename: string) => {
    if (!confirm(`Are you sure you want to delete ${filename}?`)) return;
    try {
      await api.deleteDocument(filename);
      await fetchDocuments(); // Refresh list
    } catch (_err) {
      alert("Failed to delete document");
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#0d1117] text-gray-300 p-6">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-xl font-semibold text-emerald-400">
          📂 Knowledge Base <span className="text-xs bg-gray-800 px-2 py-1 rounded-full text-gray-400 ml-2">{documents.length} Files</span>
        </h2>

        <label className="cursor-pointer bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2">
          {uploading ? 'Uploading...' : '⬆ Upload PDF'}
          <input
            type="file"
            className="hidden"
            accept=".pdf"
            onChange={handleFileUpload}
            disabled={uploading}
          />
        </label>
      </div>

      {error && <div className="text-red-400 mb-4 text-sm bg-red-900/20 p-3 rounded">{error}</div>}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {documents.length === 0 ? (
          <div className="col-span-full text-center p-12 border-2 border-dashed border-gray-800 rounded-lg text-gray-500">
            <div className="text-4xl mb-2">📄</div>
            <p>No documents uploaded yet.</p>
            <p className="text-xs mt-1">Upload a PDF to start chatting with your data.</p>
          </div>
        ) : (
          documents.map((doc) => (
            <div key={doc} className="bg-gray-800/40 border border-gray-700 p-4 rounded-lg flex justify-between items-center group hover:border-emerald-500/50 transition-all">
              <div className="flex items-center gap-3 overflow-hidden">
                <span className="text-2xl">📄</span>
                <span className="text-sm font-mono truncate max-w-[180px]" title={doc}>{doc}</span>
              </div>
              <button
                onClick={() => handleDelete(doc)}
                className="text-gray-500 hover:text-red-400 p-2 opacity-0 group-hover:opacity-100 transition-opacity"
                title="Delete Document"
              >
                🗑
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default KnowledgeBase;
