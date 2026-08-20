import { useEffect, useState } from "react";
import { Upload, FileText, X, CheckCircle2, XCircle } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { uploadDocument, getCurrentDocuments, deleteDocument } from "../api/client";

export default function UploadPanel({ onUploaded }) {
  const { getToken } = useAuth();
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [dragActive, setDragActive] = useState(false);

  const refreshDocuments = async () => {
    const token = await getToken();
    const docs = await getCurrentDocuments(token);
    setDocuments(docs);
  };

  useEffect(() => {
    refreshDocuments();
  }, []);

  const uploadFiles = async (files) => {
    setUploading(true);
    setStatus(null);
    const results = [];
    for (const file of files) {
      try {
        const token = await getToken();
        const result = await uploadDocument(file, token);
        results.push(result);
      } catch (err) {
        results.push({ filename: file.name, status: "failed", error: err.message });
      }
    }
    setStatus(results);
    setUploading(false);
    await refreshDocuments();
    if (onUploaded) onUploaded(results);
  };

  const handleFileChange = async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length) await uploadFiles(files);
    e.target.value = "";
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    setDragActive(false);
    const files = Array.from(e.dataTransfer.files || []);
    if (files.length) await uploadFiles(files);
  };

  const handleDelete = async (filename) => {
    const token = await getToken();
    await deleteDocument(filename, token);
    await refreshDocuments();
  };

  return (
    <div className="upload-panel">
      <div
        className={`dropzone ${dragActive ? "active" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
      >
        <label className="upload-button">
          <Upload size={15} />
          {uploading ? "Uploading" : "Upload documents"}
          <input
            type="file"
            accept=".pdf,.docx,.md,.txt"
            multiple
            onChange={handleFileChange}
            disabled={uploading}
            hidden
          />
        </label>
      </div>

      {status && (
        <ul className="upload-results">
          {status.map((r, i) => (
            <li key={i} className={r.status === "success" ? "status success" : "status failed"}>
              {r.status === "success" ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
              {r.filename} — {r.status === "success" ? `${r.chunk_count} chunks` : "failed"}
            </li>
          ))}
        </ul>
      )}

      <div className="document-list">
        <div className="sidebar-section-label">Your files</div>
        {documents.length === 0 && <p className="empty">Nothing uploaded yet</p>}
        <ul>
          {documents.map((doc) => (
            <li key={doc.filename}>
              <FileText size={14} />
              <span className="doc-name">{doc.filename}</span>
              <span className="chunk-count">{doc.chunk_count}</span>
              <button className="delete-btn" onClick={() => handleDelete(doc.filename)} title="Delete">
                <X size={14} />
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
