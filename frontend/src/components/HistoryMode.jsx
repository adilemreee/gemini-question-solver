import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from '../lib/api';
import { renderSolution } from '../lib/markdown';
import toast from 'react-hot-toast';

export default function HistoryMode({ onViewQuestion, onStartSolving, processing }) {
  const [questions, setQuestions] = useState([]);
  const [stats, setStats] = useState({ total: 0, success: 0, failed: 0, success_rate: 0 });
  const [topics, setTopics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState('');
  const [filterTopic, setFilterTopic] = useState('');
  const [collapsedGroups, setCollapsedGroups] = useState(new Set());
  const [retrying, setRetrying] = useState(null);

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

  const grouped = {};
  questions.forEach((q) => {
    const date = new Date(q.created_at);
    const key = date.toLocaleDateString('tr-TR', { timeZone: 'Europe/Istanbul' });
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(q);
  });

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

  const handleView = async (question) => {
    try {
      const q = await api.getQuestion(question.id);
      let content = '';
      if (q.solution) {
        content = `<div style="margin-bottom:24px;padding:16px;background:rgba(255,255,255,0.03);border-radius:12px;">
          <img src="/api/image/${encodeURIComponent(q.filename)}?topic=${encodeURIComponent(q.topic || '')}" style="max-height:200px;display:block;margin:0 auto 16px;border-radius:8px;" onerror="this.style.display='none'">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:13px;color:rgba(255,255,255,0.6)">
            <div><strong style="color:#f1f5f9">Konu:</strong> ${q.topic || 'Genel'}</div>
            <div><strong style="color:#f1f5f9">Durum:</strong> ${q.status === 'success' ? 'Basarili' : 'Basarisiz'}</div>
            <div><strong style="color:#f1f5f9">Sure:</strong> ${q.time_taken ? q.time_taken.toFixed(2) + 's' : '-'}</div>
            <div><strong style="color:#f1f5f9">Tarih:</strong> ${new Date(q.created_at).toLocaleString('tr-TR', { timeZone: 'Europe/Istanbul' })}</div>
          </div>
        </div>` + renderSolution(q.solution);
      } else if (q.error) {
        content = `<div style="color:#ef4444;padding:16px;border:1px solid rgba(239,68,68,0.3);border-radius:12px;background:rgba(239,68,68,0.08)">Hata: ${q.error}</div>`;
      }
      onViewQuestion({
        type: 'question',
        title: q.filename,
        content,
        isError: q.status !== 'success',
        questionId: q.id,
      });
    } catch (err) {
      toast.error('Soru yuklenemedi');
    }
  };

  const handleViewAll = async (dateKey, questionIds) => {
    try {
      const all = await Promise.all(questionIds.map((id) => api.getQuestion(id)));
      let html = `<div style="margin-bottom:20px;padding:14px;background:rgba(99,102,241,0.06);border-radius:10px;text-align:center;font-size:13px;color:rgba(255,255,255,0.5)">
        <span style="color:#34d399;font-weight:600">${all.filter(q => q.status === 'success').length} basarili</span>
        <span style="margin:0 8px">&middot;</span>
        <span style="color:#f87171;font-weight:600">${all.filter(q => q.status !== 'success').length} basarisiz</span>
        <span style="margin:0 8px">&middot;</span>
        Toplam ${all.length} soru
      </div>`;
      all.forEach((q, idx) => {
        const solution = q.solution ? renderSolution(q.solution) : (q.error ? `<div style="color:#f87171;padding:14px;border:1px solid rgba(248,113,113,0.2);border-radius:10px;background:rgba(248,113,113,0.06);margin-top:12px">Hata: ${q.error}</div>` : '');
        html += `<div style="margin-bottom:32px;padding-bottom:24px;border-bottom:1px solid rgba(255,255,255,0.05)">
          <div style="display:flex;align-items:flex-start;gap:16px;margin-bottom:14px">
            <img src="/api/image/${encodeURIComponent(q.filename)}?topic=${encodeURIComponent(q.topic || '')}" style="width:70px;height:70px;object-fit:cover;border-radius:10px" onerror="this.style.display='none'">
            <div>
              <div style="font-size:15px;font-weight:600;margin-bottom:6px">Soru ${idx + 1}: ${q.filename}</div>
              <div style="display:flex;gap:12px;font-size:12px;color:rgba(255,255,255,0.4)">
                <span>${q.status === 'success' ? 'Cozuldu' : 'Basarisiz'}</span>
                <span>${q.topic || 'Genel'}</span>
                <span>${q.time_taken ? q.time_taken.toFixed(1) + 's' : '-'}</span>
              </div>
            </div>
          </div>
          ${solution}
        </div>`;
      });
      onViewQuestion({
        type: 'question',
        title: `${dateKey} - Tum Cozumler (${all.length} soru)`,
        content: html,
      });
    } catch (err) {
      toast.error('Cozumler yuklenemedi');
    }
  };

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
            {Object.entries(grouped).map(([dateKey, qs], groupIdx) => {
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
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontWeight: 600 }}>
                      <span style={{ fontSize: '1.5rem' }}>{'\uD83D\uDCC5'}</span>
                      <span>{isToday ? 'Bugun' : dateKey}</span>
                      <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 400 }}>({qs.length} soru)</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleViewAll(dateKey, qs.map((q) => q.id));
                        }}
                        className="btn btn-primary"
                        style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                      >
                        {'\uD83D\uDCD6'} Tumu
                      </button>
                      <div style={{ display: 'flex', gap: 12, fontSize: '0.85rem' }}>
                        <span style={{ color: 'var(--success)' }}>{successCount} basarili</span>
                        <span style={{ color: 'var(--error)' }}>{failedCount} basarisiz</span>
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
                          {qs.map((q, qIdx) => {
                            const time = new Date(q.created_at);
                            const timeStr = time.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Istanbul' });
                            return (
                              <div
                                key={q.id}
                                className={`history-item ${q.status === 'success' ? 'success-item' : 'failed-item'}`}
                              >
                                <div style={{ display: 'flex', alignItems: 'center', gap: 16, flex: 1 }}>
                                  <span style={{ fontSize: '2rem' }}>
                                    {q.status === 'success' ? '\u2705' : '\u274C'}
                                  </span>
                                  <div style={{ flex: 1 }}>
                                    <div style={{ fontWeight: 600, marginBottom: 4 }}>{q.filename}</div>
                                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                                      {q.topic && (
                                        <span style={{
                                          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%)',
                                          color: 'white', padding: '2px 8px', borderRadius: 12, fontSize: '0.75rem'
                                        }}>
                                          {q.topic}
                                        </span>
                                      )}
                                      <span>{q.time_taken ? q.time_taken.toFixed(1) + 's' : '-'}</span>
                                      <span>{timeStr}</span>
                                      {q.retry_count > 0 && (
                                        <span style={{ color: 'var(--warning)' }}>{q.retry_count}x tekrar</span>
                                      )}
                                    </div>
                                  </div>
                                </div>
                                <div style={{ display: 'flex', gap: 8 }}>
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
