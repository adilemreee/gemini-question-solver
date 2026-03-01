import { useState, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../lib/api';
import toast from 'react-hot-toast';

export default function ReportsMode({ onViewReport }) {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [folder, setFolder] = useState('output/');
  const [collapsedGroups, setCollapsedGroups] = useState(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getOutputs();
      setReports(data.reports);
      setFolder(data.folder);
    } catch (err) {
      toast.error('Raporlar yuklenemedi');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const groupedEntries = useMemo(() => {
    const sorted = [...reports].sort(
      (a, b) => new Date(b.modified).getTime() - new Date(a.modified).getTime()
    );
    const groupedMap = new Map();
    sorted.forEach((report) => {
      const dateKey = new Date(report.modified).toLocaleDateString('tr-TR', {
        timeZone: 'Europe/Istanbul',
      });
      if (!groupedMap.has(dateKey)) groupedMap.set(dateKey, []);
      groupedMap.get(dateKey).push(report);
    });
    return Array.from(groupedMap.entries());
  }, [reports]);

  useEffect(() => {
    const allKeys = new Set(groupedEntries.map(([key]) => key));
    setCollapsedGroups(allKeys);
  }, [groupedEntries]);

  const viewReport = async (filename) => {
    try {
      const data = await api.getReport(filename);
      onViewReport({
        type: 'report',
        title: filename,
        filename,
        raw: data.content,
        contentType: 'markdown',
      });
    } catch (err) {
      toast.error('Rapor yuklenemedi');
    }
  };

  const deleteReport = async (filename) => {
    if (!confirm(`"${filename}" raporunu silmek istediginize emin misiniz?`)) return;
    try {
      await api.deleteReport(filename);
      setReports((prev) => prev.filter((r) => r.filename !== filename));
      toast.success('Rapor silindi');
    } catch (err) {
      toast.error('Rapor silinemedi: ' + err.message);
    }
  };

  const toggleGroup = (key) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <div>
      <div className="folder-section">
        <div className="folder-header">
          <div className="folder-info">
            <span className="folder-icon">{'\uD83D\uDCC4'}</span>
            <div>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>Cozum Raporlari</div>
              <code className="folder-path">
                {loading ? 'Yukleniyor...' : `${reports.length} rapor - ${folder}`}
              </code>
            </div>
          </div>
          <button onClick={load} disabled={loading} className="btn btn-secondary">
            {'\uD83D\uDD04'} Yenile
          </button>
        </div>

        {/* Loading */}
        {loading && (
          <div className="empty-state">
            <div className="spinner-ring" style={{ width: 40, height: 40, margin: '0 auto' }} />
            <div style={{ marginTop: 16 }}>Raporlar yukleniyor...</div>
          </div>
        )}

        {/* Empty */}
        {!loading && reports.length === 0 && (
          <div className="empty-state">
            <div style={{ fontSize: '3rem', marginBottom: 16, opacity: 0.5 }}>{'\uD83D\uDCED'}</div>
            <div>Henuz rapor olusturulmamis</div>
          </div>
        )}

        {/* Reports grouped by date */}
        {!loading && reports.length > 0 && (
          <div>
            {groupedEntries.map(([dateKey, items]) => {
              const collapsed = collapsedGroups.has(dateKey);
              const isToday = dateKey === new Date().toLocaleDateString('tr-TR', { timeZone: 'Europe/Istanbul' });
              const totalSize = (items.reduce((sum, r) => sum + r.size, 0) / 1024).toFixed(1);

              return (
                <div key={dateKey} className="date-group">
                  {/* Date Group Header */}
                  <div className="date-group-header" onClick={() => toggleGroup(dateKey)}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontWeight: 600 }}>
                      <span style={{ fontSize: '1.5rem' }}>{'\uD83D\uDCC5'}</span>
                      <span>{isToday ? 'Bugun' : dateKey}</span>
                      <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 400 }}>
                        ({items.length} rapor &middot; {totalSize} KB)
                      </span>
                    </div>
                    <span style={{ transition: 'transform 0.2s ease', transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)', fontSize: '1.2rem' }}>
                      {'\u25BC'}
                    </span>
                  </div>

                  {/* Date Group Content */}
                  <AnimatePresence>
                    {!collapsed && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.25 }}
                        style={{ overflow: 'hidden' }}
                      >
                        <div className="date-group-content">
                          {items.map((report) => {
                            const date = new Date(report.modified);
                            const timeStr = date.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Istanbul' });
                            const sizeKB = (report.size / 1024).toFixed(1);

                            return (
                              <div key={report.filename} className="history-item">
                                <div style={{ display: 'flex', alignItems: 'center', gap: 16, flex: 1 }}>
                                  <span style={{ fontSize: '2rem' }}>{'\uD83D\uDCC4'}</span>
                                  <div style={{ flex: 1 }}>
                                    <div style={{ fontWeight: 600, marginBottom: 4 }}>{report.filename}</div>
                                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                                      <span>{timeStr}</span>
                                      <span>{sizeKB} KB</span>
                                    </div>
                                  </div>
                                </div>
                                <div style={{ display: 'flex', gap: 8 }}>
                                  <button
                                    onClick={() => viewReport(report.filename)}
                                    className="btn btn-secondary"
                                    style={{ padding: '8px 14px', fontSize: '0.85rem' }}
                                  >
                                    {'\uD83D\uDC41\uFE0F'} Gor
                                  </button>
                                  <button
                                    onClick={() => window.open(api.getReportPdfUrl(report.filename), '_blank')}
                                    className="btn btn-primary"
                                    style={{ padding: '8px 14px', fontSize: '0.85rem' }}
                                  >
                                    {'\uD83D\uDCE5'} PDF
                                  </button>
                                  <button
                                    onClick={() => deleteReport(report.filename)}
                                    className="btn btn-danger"
                                    style={{ padding: '8px 14px', fontSize: '0.85rem' }}
                                  >
                                    {'\uD83D\uDDD1\uFE0F'}
                                  </button>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
