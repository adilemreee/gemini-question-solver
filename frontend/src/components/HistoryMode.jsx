import { useState, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../lib/api';
import LazyImage from './LazyImage';
import toast from 'react-hot-toast';

export default function HistoryMode({ onViewQuestion, onStartSolving, processing, onOpenLightbox }) {
  const [questions, setQuestions] = useState([]);
  const [stats, setStats] = useState({ total: 0, success: 0, failed: 0, success_rate: 0 });
  const [topics, setTopics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('');
  const [filterTopic, setFilterTopic] = useState('');
  const [collapsedGroups, setCollapsedGroups] = useState(new Set());
  const [retrying, setRetrying] = useState(null);
  const [reclassifying, setReclassifying] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [statsData, questionsData, topicsData] = await Promise.all([
        api.getStats(),
        api.getQuestions({ status: filterStatus || undefined, topic: filterTopic || undefined, archived: false }),
        api.getTopics(),
      ]);
      setStats(statsData);
      setQuestions(questionsData.questions);
      setTopics(topicsData);
    } catch (err) {
      toast.error('Veriler yuklenemedi');
    } finally {
      setLoading(false);
    }
  }, [filterStatus, filterTopic]);

  useEffect(() => { load(); }, [load]);

  const groupedEntries = useMemo(() => {
    const sorted = [...questions].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
    const groupedMap = new Map();
    sorted.forEach((question) => {
      const key = new Date(question.created_at).toLocaleDateString('tr-TR', {
        timeZone: 'Europe/Istanbul',
      });
      if (!groupedMap.has(key)) groupedMap.set(key, []);
      groupedMap.get(key).push(question);
    });
    return Array.from(groupedMap.entries());
  }, [questions]);

  useEffect(() => {
    const today = new Date().toLocaleDateString('tr-TR', { timeZone: 'Europe/Istanbul' });
    const nextCollapsed = new Set(groupedEntries.map(([key]) => key).filter((key) => key !== today));
    setCollapsedGroups(nextCollapsed);
  }, [groupedEntries]);

  const toggleGroup = (key) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const handleRetry = async (id) => {
    setRetrying(id);
    try {
      const data = await api.retryQuestion(id);
      if (data.success) toast.success('Soru basariyla cozuldu!');
      else toast.error('Soru tekrar basarisiz oldu');
      load();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setRetrying(null);
    }
  };

  const handleRetryAll = async () => {
    if (!confirm('Tum basarisiz sorulari tekrar cozmek istediginize emin misiniz?')) return;
    try {
      const data = await api.retryAllFailed();
      if (data.session_id) {
        toast.success(`${data.count} soru tekrar cozuluyor...`);
        onStartSolving(data.session_id);
      }
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleArchive = async () => {
    if (!confirm('Tum basarili sorulari arsivlemek istediginize emin misiniz?')) return;
    try {
      const data = await api.archiveSuccessful();
      toast.success(`${data.count} soru arsivlendi`);
      load();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleDeleteAll = async () => {
    if (!confirm('TUM SORULARI silmek istediginize emin misiniz? Bu islem geri alinamaz!')) return;
    try {
      const data = await api.deleteAllQuestions();
      toast.success(`${data.count} soru silindi`);
      load();
    } catch (err) {
      toast.error(err.message);
    }
  };

  const handleReclassify = async () => {
    if (!confirm('Tüm soruları güncel konu kalıplarına göre yeniden sınıflandırmak istediğinize emin misiniz?')) return;
    setReclassifying(true);
    try {
      const data = await api.reclassifyAll();
      if (data.changed > 0) {
        toast.success(`${data.changed}/${data.total} soru yeniden sınıflandırıldı`);
      } else {
        toast.success(`Tüm sorular zaten doğru sınıflandırılmış (${data.total} soru kontrol edildi)`);
      }
      load();
    } catch (err) {
      toast.error(err.message || 'Yeniden sınıflandırma başarısız');
    } finally {
      setReclassifying(false);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm('Bu soruyu silmek istediginize emin misiniz?')) return;
    try {
      await api.deleteQuestion(id);
      setQuestions((prev) => prev.filter((q) => q.id !== id));
      toast.success('Soru silindi');
    } catch (err) {
      toast.error(err.message);
    }
  };

  const getQuestionImageUrl = useCallback((q) => {
    const encodedFilename = encodeURIComponent(q.filename || '');
    if (q.session_id && q.image_path && String(q.image_path).includes('/uploads/')) {
      return `/api/session-image/${encodeURIComponent(q.session_id)}/${encodedFilename}`;
    }
    return api.getImageUrl(q.filename, q.topic || '');
  }, []);

  const handleView = async (question) => {
    try {
      const q = await api.getQuestion(question.id);
      const imageUrl = getQuestionImageUrl(q);
      onViewQuestion({
        type: 'question',
        title: q.filename,
        raw: q.solution || `Hata: ${q.error || 'Bilinmeyen hata'}`,
        contentType: q.solution ? 'markdown' : 'text',
        isError: q.status !== 'success',
        questionId: q.id,
        meta: {
          topic: q.topic || 'Genel',
          status: q.status === 'success' ? 'Basarili' : 'Basarisiz',
          timeTaken: q.time_taken ?? null,
          createdAt: q.created_at,
          imageUrl,
        },
      });
    } catch (err) {
      toast.error('Soru yuklenemedi');
    }
  };

  const handleViewAll = useCallback(async (dateKey, questionIds) => {
    try {
      const all = await Promise.all(questionIds.map((id) => api.getQuestion(id)));
      const successCount = all.filter((q) => q.status === 'success').length;
      const failedCount = all.length - successCount;
      let markdown = `# ${dateKey} Tum Cozumler\n\n`;
      markdown += `- Toplam: ${all.length}\n`;
      markdown += `- Basarili: ${successCount}\n`;
      markdown += `- Basarisiz: ${failedCount}\n\n---\n`;

      all.forEach((q, idx) => {
        const imageUrl = getQuestionImageUrl(q);
        markdown += `\n## Soru ${idx + 1}: ${q.filename}\n`;
        markdown += `- Durum: ${q.status === 'success' ? 'Cozuldu' : 'Basarisiz'}\n`;
        markdown += `- Konu: ${q.topic || 'Genel'}\n`;
        markdown += `- Sure: ${q.time_taken ? `${q.time_taken.toFixed(1)}s` : '-'}\n\n`;
        markdown += `![${q.filename}](${imageUrl})\n\n`;
        markdown += q.solution || `Hata: ${q.error || 'Bilinmeyen hata'}`;
        markdown += '\n\n---\n';
      });
      onViewQuestion({
        type: 'question',
        title: `${dateKey} - Tum Cozumler (${all.length} soru)`,
        raw: markdown,
        contentType: 'markdown',
      });
    } catch (err) {
      toast.error('Cozumler yuklenemedi');
    }
  }, [getQuestionImageUrl, onViewQuestion]);

  return (
    <div>
      <div className="folder-section">
        {/* Stats Bar */}
        <div className="stats-bar">
          <div className="stat-item">
            <span className="stat-value">{stats.total}</span>
            <span className="stat-label">Toplam</span>
          </div>
          <div className="stat-item success-stat">
            <span className="stat-value">{stats.success}</span>
            <span className="stat-label">Basarili</span>
          </div>
          <div className="stat-item failed-stat">
            <span className="stat-value">{stats.failed}</span>
            <span className="stat-label">Basarisiz</span>
          </div>
          <div className="stat-item">
            <span className="stat-value">%{stats.success_rate}</span>
            <span className="stat-label">Basari</span>
          </div>
        </div>

        {/* Filter Bar */}
        <div className="filter-bar">
          <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
            <option value="">Tum Durumlar</option>
            <option value="success">{'\u2705'} Basarili</option>
            <option value="failed">{'\u274C'} Basarisiz</option>
          </select>
          <select value={filterTopic} onChange={(e) => setFilterTopic(e.target.value)}>
            <option value="">Tum Konular</option>
            {topics.map((t) => (
              <option key={t.name} value={t.name}>{t.icon} {t.name}</option>
            ))}
          </select>
          <button onClick={load} disabled={loading} className="btn btn-secondary" style={{ padding: '10px 16px', fontSize: '0.85rem' }}>
            {'\uD83D\uDD04'} Yenile
          </button>
          {stats.failed > 0 && (
            <button onClick={handleRetryAll} disabled={processing} className="btn btn-primary" style={{ padding: '10px 16px', fontSize: '0.85rem' }}>
              {'\uD83D\uDD04'} Tumunu Tekrar Dene
            </button>
          )}
          <button onClick={handleArchive} className="btn btn-secondary" style={{ padding: '10px 16px', fontSize: '0.85rem' }}>
            {'\uD83D\uDCE6'} Basarilari Arsivle
          </button>
          <button onClick={handleReclassify} disabled={reclassifying} className="btn btn-secondary" style={{ padding: '10px 16px', fontSize: '0.85rem' }}>
            {reclassifying ? (
              <><span className="spinner-ring" style={{ display: 'inline-block', width: 14, height: 14, marginRight: 6 }} />Sınıflandırılıyor...</>
            ) : (
              <>{'\uD83D\uDD00'} Yeniden Sınıfla</>
            )}
          </button>
          <button onClick={handleDeleteAll} className="btn btn-danger" style={{ padding: '10px 16px', fontSize: '0.85rem' }}>
            {'\uD83D\uDDD1\uFE0F'} Tumunu Sil
          </button>
        </div>

        {/* Loading */}
        {loading && (
          <div className="empty-state">
            <div className="spinner-ring" style={{ width: 40, height: 40, margin: '0 auto' }} />
            <div style={{ marginTop: 16 }}>Veriler yukleniyor...</div>
          </div>
        )}

        {/* Empty */}
        {!loading && questions.length === 0 && (
          <div className="empty-state">
            <div style={{ fontSize: '3rem', marginBottom: 16, opacity: 0.5 }}>{'\uD83D\uDCED'}</div>
            <div>Henuz soru cozulmemis</div>
          </div>
        )}

        {/* Questions grouped by date */}
        {!loading && questions.length > 0 && (
          <div>
            {groupedEntries.map(([dateKey, qs], groupIdx) => {
              const collapsed = collapsedGroups.has(dateKey);
              const successCount = qs.filter((q) => q.status === 'success').length;
              const failedCount = qs.length - successCount;
              const isToday = dateKey === new Date().toLocaleDateString('tr-TR', { timeZone: 'Europe/Istanbul' });

              return (
                <motion.div
                  key={dateKey}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: groupIdx * 0.04 }}
                  className="date-group"
                >
                  {/* Date Group Header */}
                  <div className="date-group-header" onClick={() => toggleGroup(dateKey)}>
                    <div className="date-group-left">
                      <span className="date-group-icon">{'\uD83D\uDCC5'}</span>
                      <span>{isToday ? 'Bugun' : dateKey}</span>
                      <span className="date-group-meta">({qs.length} soru)</span>
                    </div>
                    <div className="date-group-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleViewAll(dateKey, qs.map((q) => q.id));
                        }}
                        className="btn btn-primary"
                        style={{ padding: '6px 12px', fontSize: '0.8rem', minWidth: 88 }}
                      >
                        {'\uD83D\uDCD6'} Tumu
                      </button>
                      <div className="date-group-statuses">
                        <span className="status-pill success">{successCount} basarili</span>
                        <span className="status-pill error">{failedCount} basarisiz</span>
                      </div>
                      <span style={{ transition: 'transform 0.2s ease', transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)', fontSize: '1.2rem' }}>
                        {'\u25BC'}
                      </span>
                    </div>
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
                          {qs.map((q) => {
                            const time = new Date(q.created_at);
                            const timeStr = time.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Istanbul' });
                            const imageUrl = getQuestionImageUrl(q);
                            return (
                              <div
                                key={q.id}
                                className={`history-item ${q.status === 'success' ? 'success-item' : 'failed-item'}`}
                              >
                                <div className="history-main">
                                  <button
                                    type="button"
                                    className="history-thumb-btn"
                                    onClick={() => onOpenLightbox?.({ src: imageUrl, alt: q.filename })}
                                    aria-label={`${q.filename} buyut`}
                                  >
                                    <LazyImage
                                      src={imageUrl}
                                      alt={q.filename}
                                      className="history-thumb"
                                      onError={(e) => { e.currentTarget.style.display = 'none'; }}
                                    />
                                    <span className="zoom-icon">+</span>
                                  </button>

                                  <div className="history-info">
                                    <div className="history-title-row">
                                      <span className="history-status">{q.status === 'success' ? '\u2705' : '\u274C'}</span>
                                      <div style={{ fontWeight: 700, marginBottom: 2 }}>{q.filename}</div>
                                    </div>
                                    <div className="history-meta-row">
                                      {q.topic && <span className="topic-badge">{q.topic}</span>}
                                      <span className="meta-chip">{q.time_taken ? q.time_taken.toFixed(1) + 's' : '-'}</span>
                                      <span className="meta-chip">{timeStr}</span>
                                      {q.retry_count > 0 && <span className="meta-chip warning">{q.retry_count}x tekrar</span>}
                                    </div>
                                  </div>
                                </div>
                                <div className="history-actions">
                                  {q.status === 'failed' && (
                                    <button
                                      onClick={() => handleRetry(q.id)}
                                      disabled={retrying === q.id}
                                      className="btn btn-primary"
                                      style={{ padding: '8px 14px', fontSize: '0.85rem' }}
                                    >
                                      {retrying === q.id ? (
                                        <span className="spinner-ring" style={{ display: 'inline-block', width: 16, height: 16 }} />
                                      ) : (
                                        <>{'\uD83D\uDD04'} Tekrar</>
                                      )}
                                    </button>
                                  )}
                                  <button
                                    onClick={() => handleView(q)}
                                    className="btn btn-secondary"
                                    style={{ padding: '8px 14px', fontSize: '0.85rem' }}
                                  >
                                    {'\uD83D\uDC41\uFE0F'} Gor
                                  </button>
                                  <button
                                    onClick={() => handleDelete(q.id)}
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
                </motion.div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
