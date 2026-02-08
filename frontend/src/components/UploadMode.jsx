import { useState, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../lib/api';
import toast from 'react-hot-toast';

const ACCEPTED_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif', 'image/bmp'];

export default function UploadMode({ onStartSolving, processing }) {
  const [files, setFiles] = useState([]);
  const [previews, setPreviews] = useState([]);
  const [solving, setSolving] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);

  const generatePreviews = useCallback((fileList) => {
    const urls = fileList.map((file) => URL.createObjectURL(file));
    setPreviews((prev) => { prev.forEach((url) => URL.revokeObjectURL(url)); return urls; });
  }, []);

  const handleFiles = useCallback((incoming) => {
    const valid = Array.from(incoming).filter((f) => ACCEPTED_TYPES.includes(f.type));
    if (valid.length === 0) { toast.error('Gecerli bir gorsel dosyasi secin (PNG, JPG, WebP)'); return; }
    setFiles((prev) => { const merged = [...prev, ...valid]; generatePreviews(merged); return merged; });
  }, [generatePreviews]);

  const handleDrop = useCallback((e) => {
    e.preventDefault(); setDragOver(false);
    if (e.dataTransfer.files?.length) handleFiles(e.dataTransfer.files);
  }, [handleFiles]);

  const removeFile = useCallback((index) => {
    setFiles((prev) => { const updated = prev.filter((_, i) => i !== index); generatePreviews(updated); return updated; });
  }, [generatePreviews]);

  const clearAll = useCallback(() => {
    previews.forEach((url) => URL.revokeObjectURL(url));
    setFiles([]); setPreviews([]);
  }, [previews]);

  const handleSolve = useCallback(async () => {
    if (files.length === 0) { toast.error('En az bir gorsel yukleyin'); return; }
    setSolving(true);
    try {
      const uploadResult = await api.uploadFiles(files);
      toast.success(`${uploadResult.file_count} dosya yuklendi`);
      await api.solveSession(uploadResult.session_id);
      onStartSolving(uploadResult.session_id);
      clearAll();
    } catch (err) {
      toast.error(err.message || 'Yukleme basarisiz');
    } finally {
      setSolving(false);
    }
  }, [files, onStartSolving, clearAll]);

  const isDisabled = processing || solving;
  const hasFiles = files.length > 0;

  return (
    <div>
      {/* Upload Zone */}
      <div
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={(e) => { e.preventDefault(); setDragOver(false); }}
        onClick={() => !isDisabled && inputRef.current?.click()}
        className={`upload-zone ${dragOver ? 'drag-over' : ''} ${hasFiles ? 'has-files' : ''} ${isDisabled ? 'disabled' : ''}`}
      >
        <input ref={inputRef} type="file" accept="image/*" multiple onChange={(e) => { if (e.target.files?.length) handleFiles(e.target.files); e.target.value = ''; }} style={{ display: 'none' }} />

        <div style={{ fontSize: '4rem', marginBottom: 20 }}>
          {hasFiles ? '\u2705' : '\uD83D\uDCF7'}
        </div>

        {hasFiles ? (
          <>
            <div style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: 8, color: 'var(--success)' }}>
              {files.length} dosya secildi
            </div>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
              Daha fazla eklemek icin tiklayin veya surukleyin
            </div>
          </>
        ) : (
          <>
            <div style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: 8 }}>
              Soru Fotograflarini Surukle & Birak
            </div>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
              veya tikla ve dosyalari sec (JPEG, PNG)
            </div>
          </>
        )}
      </div>

      {/* File Preview Grid */}
      <AnimatePresence>
        {hasFiles && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}>
            <div className="file-grid">
              <AnimatePresence>
                {files.map((file, index) => (
                  <motion.div
                    key={`${file.name}-${file.lastModified}-${index}`}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.9 }}
                    transition={{ duration: 0.2, delay: index * 0.03 }}
                    className="file-card"
                  >
                    <div style={{ position: 'relative' }}>
                      {previews[index] ? (
                        <img src={previews[index]} alt={file.name} style={{ width: '100%', height: 100, objectFit: 'cover', borderRadius: '10px 10px 0 0', pointerEvents: 'none' }} />
                      ) : (
                        <div style={{ width: '100%', height: 100, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '2rem', opacity: 0.3 }}>
                          {'\uD83D\uDDBC\uFE0F'}
                        </div>
                      )}
                      <div className="thumb-overlay" />
                      <button
                        onClick={(e) => { e.stopPropagation(); removeFile(index); }}
                        disabled={isDisabled}
                        style={{
                          position: 'absolute', right: 8, top: 8,
                          width: 28, height: 28,
                          background: 'rgba(248, 113, 113, 0.8)',
                          border: 'none', borderRadius: 6,
                          color: 'white', cursor: 'pointer',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: 14, opacity: 0,
                          transition: 'opacity 0.2s ease',
                        }}
                        onMouseEnter={(e) => e.target.style.opacity = 1}
                        onMouseLeave={(e) => e.target.style.opacity = 0}
                      >
                        {'\uD83D\uDDD1\uFE0F'}
                      </button>
                    </div>
                    <div style={{ padding: '8px 12px' }}>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {file.name}
                      </div>
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Actions */}
      <AnimatePresence>
        {hasFiles && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{ display: 'flex', gap: 16, justifyContent: 'center', marginBottom: 48 }}
          >
            <button onClick={clearAll} disabled={isDisabled} className="btn btn-secondary">
              {'\uD83D\uDDD1\uFE0F'} Temizle
            </button>
            <button onClick={handleSolve} disabled={isDisabled} className="btn btn-primary">
              {solving ? (
                <><span className="spinner-ring" style={{ display: 'inline-block', width: 20, height: 20 }} /> Yukleniyor...</>
              ) : (
                <>{'\uD83D\uDE80'} Sorulari Coz</>
              )}
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
