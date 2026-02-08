import { useState, useEffect, useCallback, useMemo } from 'react';
import { api } from '../lib/api';
import toast from 'react-hot-toast';

export default function FolderMode({ onStartSolving, processing, progressData }) {
  const [files, setFiles] = useState([]);
  const [topicFolders, setTopicFolders] = useState([]);
  const [selectedFiles, setSelectedFiles] = useState(new Set());
  const [currentTopic, setCurrentTopic] = useState(null);
  const [loading, setLoading] = useState(true);
  const [folderPath, setFolderPath] = useState('');

  const resultMap = useMemo(() => {
    const map = {};
    if (progressData?.results) {
      progressData.results.forEach((r) => { map[r.filename] = r.success; });
    }
    return map;
  }, [progressData]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [scanData, topicData] = await Promise.all([
        api.scanFolder(),
        api.getTopicFolders(),
      ]);
      setFiles(scanData.files || []);
      setFolderPath(scanData.folder || '');
      setTopicFolders(topicData.folders || []);
      setCurrentTopic(null);
      setSelectedFiles(new Set());
    } catch (err) {
      toast.error('Klasor taranamadi: ' + err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const selectTopic = useCallback(async (topic) => {
    if (topic === null) {
      setLoading(true);
      try {
        const scanData = await api.scanFolder();
        setFiles(scanData.files || []);
        setFolderPath(scanData.folder || '');
        setCurrentTopic(null);
        setSelectedFiles(new Set());
      } catch (err) {
        toast.error('Klasor taranamadi: ' + err.message);
      } finally {
        setLoading(false);
      }
      return;
    }
    setLoading(true);
    try {
      const data = await api.getTopicFolder(topic);
      setFiles(data.files || []);
      setFolderPath(data.path || '');
      setCurrentTopic(topic);
      setSelectedFiles(new Set());
    } catch (err) {
      toast.error('Konu klasoru yuklenemedi: ' + err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const toggleFile = useCallback((filename) => {
    setSelectedFiles((prev) => {
      const next = new Set(prev);
      if (next.has(filename)) next.delete(filename);
      else next.add(filename);
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    setSelectedFiles(new Set(files.map((f) => f.filename)));
  }, [files]);

  const clearSelection = useCallback(() => {
    setSelectedFiles(new Set());
  }, []);

  const solveAll = useCallback(async () => {
    try {
      const data = await api.solveFolder();
      onStartSolving(data.session_id);
      toast.success('Tum dosyalar cozuluyor...');
    } catch (err) {
      toast.error('Baslatma hatasi: ' + err.message);
    }
  }, [onStartSolving]);

  const solveSelected = useCallback(async () => {
    if (selectedFiles.size === 0) { toast.error('Lutfen en az bir dosya secin'); return; }
    try {
      const data = await api.solveSelected([...selectedFiles]);
      onStartSolving(data.session_id);
      toast.success(`${selectedFiles.size} dosya cozuluyor...`);
    } catch (err) {
      toast.error('Baslatma hatasi: ' + err.message);
    }
  }, [selectedFiles, onStartSolving]);

  const formatSize = (bytes) => {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div>
      {/* Topic Folders */}
      {topicFolders.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            {'\uD83D\uDCDA'} Konu Klasorleri
            <button className="btn btn-secondary" onClick={loadData} style={{ padding: '4px 8px', fontSize: 12 }}>
              {'\uD83D\uDD04'}
            </button>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            <button
              onClick={() => selectTopic(null)}
              className={`topic-folder-btn ${currentTopic === null ? 'active' : ''}`}
            >
              {'\uD83D\uDCC1'} Tumu
            </button>
            {topicFolders.map((folder) => (
              <button
                key={folder.name}
                onClick={() => selectTopic(folder.name)}
                className={`topic-folder-btn ${currentTopic === folder.name ? 'active' : ''}`}
              >
                {folder.is_root ? '\uD83D\uDCC1' : '\uD83D\uDCDA'} {folder.name}
                <span className="count">
                  {folder.count}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Folder Section */}
      <div className="folder-section">
        <div className="folder-header">
          <div className="folder-info">
            <span className="folder-icon">{'📂'}</span>
            <div>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>
                {currentTopic || 'Questions Klasoru'}
              </div>
              <code className="folder-path">
                {loading ? 'Taraniyor...' : `${files.length} dosya - ${folderPath}`}
              </code>
            </div>
          </div>
          <div className="folder-actions">
            <button className="btn btn-secondary" onClick={loadData} disabled={loading || processing}>
              {'\uD83D\uDD04'} Yenile
            </button>
            <button className="btn btn-secondary" onClick={selectAll} disabled={loading || processing || files.length === 0}>
              {'\u2705'} Tumunu Sec
            </button>
            <button className="btn btn-secondary" onClick={clearSelection} disabled={selectedFiles.size === 0}>
              {'\u274E'} Secimi Temizle
            </button>
            <button className="btn btn-primary" onClick={solveSelected} disabled={processing || selectedFiles.size === 0}>
              {'\u2728'} Secilenleri Coz
            </button>
            <button className="btn btn-primary" onClick={solveAll} disabled={processing || files.length === 0}>
              {'\uD83D\uDE80'} Tumunu Coz
            </button>
          </div>
        </div>

        {/* Selection Info */}
        {selectedFiles.size > 0 && (
          <div className="selection-info">
            <span>{'🎯'} Secilen:</span>
            <span style={{ fontWeight: 600, color: 'var(--success)' }}>{selectedFiles.size} soru</span>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="empty-state">
            <div className="spinner-ring" style={{ width: 40, height: 40, margin: '0 auto' }} />
            <div style={{ marginTop: 16 }}>Klasor taraniyor...</div>
          </div>
        )}

        {/* Empty */}
        {!loading && files.length === 0 && (
          <div className="empty-state">
            <div style={{ fontSize: '3rem', marginBottom: 16, opacity: 0.5 }}>{'\uD83D\uDCED'}</div>
            <div>Klasorde soru fotografi bulunamadi</div>
            <div style={{ fontSize: '0.85rem', marginTop: 8 }}>
              questions/ klasorune JPEG veya PNG dosyalari ekleyin
            </div>
          </div>
        )}

        {/* File Grid */}
        {!loading && files.length > 0 && (
          <div className="file-grid">
            {files.map((file, index) => {
              const isSelected = selectedFiles.has(file.filename);
              const result = resultMap[file.filename];
              const hasResult = result !== undefined;

              return (
                <div
                  key={file.filename}
                  onClick={() => !processing && toggleFile(file.filename)}
                  className={`file-card ${isSelected ? 'selected' : ''}`}
                >
                  <div style={{ position: 'relative' }}>
                    <img
                      src={api.getImageUrl(file.filename, currentTopic)}
                      alt={file.filename}
                      style={{ width: '100%', height: 100, objectFit: 'cover', borderRadius: '10px 10px 0 0' }}
                      loading="lazy"
                      onError={(e) => { e.target.style.display = 'none'; }}
                    />
                    <div className="thumb-overlay" />
                    {/* Checkbox */}
                    <div style={{
                      position: 'absolute', top: 8, left: 8,
                      width: 24, height: 24,
                      background: isSelected ? 'var(--success)' : 'var(--bg-glass)',
                      border: isSelected ? '2px solid var(--success)' : '2px solid var(--border-color)',
                      borderRadius: 6,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 14, transition: 'all 0.2s ease', zIndex: 2,
                    }}>
                      {isSelected ? '\u2713' : ''}
                    </div>
                    {/* Result status */}
                    {hasResult && (
                      <div style={{
                        position: 'absolute', top: 8, right: 8,
                        fontSize: '1.5rem',
                      }}>
                        {result ? '\u2705' : '\u274C'}
                      </div>
                    )}
                  </div>
                  <div style={{ padding: '8px 12px' }}>
                    <div className="filename" style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {file.filename}
                    </div>
                    {file.size && (
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: 2 }}>{formatSize(file.size)}</div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
