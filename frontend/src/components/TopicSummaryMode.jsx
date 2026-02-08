import { useState, useEffect, useCallback } from 'react';
import { api } from '../lib/api';
import { renderSolution } from '../lib/markdown';
import toast from 'react-hot-toast';

export default function TopicSummaryMode() {
  const [topics, setTopics] = useState([]);
  const [savedSummaries, setSavedSummaries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generatingTopic, setGeneratingTopic] = useState(null);
  const [expandedSummary, setExpandedSummary] = useState(null);

  const topicIcons = {
    'Matematik': '\uD83D\uDCD0',
    'Fizik': '\u26A1',
    'Kimya': '\uD83E\uDDEA',
    'Biyoloji': '\uD83E\uDDEC',
    'Türkçe': '\uD83D\uDCDD',
    'Tarih': '\uD83D\uDCDC',
    'Coğrafya': '\uD83C\uDF0D',
    'İngilizce': '\uD83D\uDD24',
    'Genel': '\uD83D\uDCDA',
  };

  const loadData = useCallback(async () => {
    try {
      const [topicsData, summariesData] = await Promise.all([
        api.getTopics(),
        api.getSummaries(),
      ]);
      setTopics(topicsData);
      setSavedSummaries(summariesData.summaries || []);
    } catch {
      toast.error('Veriler yüklenemedi');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const generateSummary = useCallback(async (topicName) => {
    setGeneratingTopic(topicName);
    try {
      const data = await api.getTopicSummary(topicName);
      if (data.success) {
        toast.success(`${topicName} özeti oluşturuldu!`);
        const fresh = await api.getSummaries();
        setSavedSummaries(fresh.summaries || []);
      } else {
        toast.error(data.error || 'Özet oluşturulamadı');
      }
    } catch (err) {
      toast.error(err.message || 'Özet oluşturulamadı');
    } finally {
      setGeneratingTopic(null);
    }
  }, []);

  const handleDelete = useCallback(async (id) => {
    if (!confirm('Bu özeti silmek istediğinizden emin misiniz?')) return;
    try {
      await api.deleteSummary(id);
      setSavedSummaries((prev) => prev.filter((s) => s.id !== id));
      toast.success('Özet silindi');
      if (expandedSummary === id) setExpandedSummary(null);
    } catch {
      toast.error('Silinemedi');
    }
  }, [expandedSummary]);

  // Group saved summaries by topic
  const summariesByTopic = {};
  savedSummaries.forEach((s) => {
    if (!summariesByTopic[s.topic]) summariesByTopic[s.topic] = [];
    summariesByTopic[s.topic].push(s);
  });

  const topicsWithSummaries = Object.keys(summariesByTopic).sort();

  const formatDate = (dateStr) => {
    try {
      const d = new Date(dateStr + 'Z');
      return d.toLocaleDateString('tr-TR', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Istanbul' });
    } catch { return dateStr; }
  };

  return (
    <div>
      {/* Generate Section */}
      <div className="folder-section">
        <div className="folder-header">
          <div className="folder-info">
            <span className="folder-icon">{'\u2728'}</span>
            <div>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>Yeni Özet Oluştur</div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                Çözülmüş sorulardan otomatik konu özeti ve formül kartları oluştur
              </div>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="empty-state">
            <div className="spinner-ring" style={{ width: 40, height: 40, margin: '0 auto' }} />
            <div style={{ marginTop: 16 }}>Yükleniyor...</div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 16 }}>
            {topics.filter(t => t.name !== 'Genel').map((topic) => {
              const isGenerating = generatingTopic === topic.name;
              const count = (summariesByTopic[topic.name] || []).length;
              return (
                <button
                  key={topic.name}
                  onClick={() => generateSummary(topic.name)}
                  disabled={isGenerating || !!generatingTopic}
                  className="btn btn-secondary"
                  style={{
                    padding: '10px 18px',
                    fontSize: '0.9rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    opacity: (generatingTopic && !isGenerating) ? 0.5 : 1,
                  }}
                >
                  {isGenerating ? (
                    <span className="spinner-ring" style={{ display: 'inline-block', width: 16, height: 16 }} />
                  ) : (
                    <span>{topic.icon || topicIcons[topic.name] || '\uD83D\uDCDA'}</span>
                  )}
                  {topic.name}
                  {count > 0 && (
                    <span style={{
                      background: 'var(--primary)',
                      color: '#fff',
                      fontSize: '0.7rem',
                      padding: '2px 6px',
                      borderRadius: 8,
                      fontWeight: 600,
                    }}>{count}</span>
                  )}
                </button>
              );
            })}
          </div>
        )}

        {generatingTopic && (
          <div style={{
            marginTop: 16,
            padding: 16,
            background: 'rgba(99,102,241,0.06)',
            borderRadius: 12,
            display: 'flex',
            alignItems: 'center',
            gap: 12,
          }}>
            <span className="spinner-ring" style={{ display: 'inline-block', width: 20, height: 20 }} />
            <span style={{ color: 'var(--text-secondary)' }}>
              <strong>{generatingTopic}</strong> özeti AI ile oluşturuluyor... (30-60sn sürebilir)
            </span>
          </div>
        )}
      </div>

      {/* Saved Summaries by Topic */}
      {topicsWithSummaries.length === 0 && !loading && (
        <div className="folder-section">
          <div className="empty-state">
            <div style={{ fontSize: '3rem', marginBottom: 16 }}>{'\uD83D\uDCDD'}</div>
            <div style={{ color: 'var(--text-secondary)' }}>
              Henüz kaydedilmiş özet yok. Yukarıdan bir ders seçerek özet oluşturun.
            </div>
          </div>
        </div>
      )}

      {topicsWithSummaries.map((topicName) => {
        const topicSummaries = summariesByTopic[topicName];
        const topicData = topics.find(t => t.name === topicName);
        const icon = topicData?.icon || topicIcons[topicName] || '\uD83D\uDCDA';

        return (
          <div key={topicName} className="folder-section" style={{ marginTop: 16 }}>
            <div className="folder-header">
              <div className="folder-info">
                <span className="folder-icon">{icon}</span>
                <div>
                  <div style={{ fontWeight: 600, fontSize: '1.05rem' }}>{topicName}</div>
                  <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                    {topicSummaries.length} özet
                  </div>
                </div>
              </div>
            </div>

            <div style={{ marginTop: 12 }}>
              {topicSummaries.map((summary) => {
                const isExpanded = expandedSummary === summary.id;
                return (
                  <div
                    key={summary.id}
                    className="result-card"
                    style={{
                      margin: '0 0 12px 0',
                      cursor: 'pointer',
                      border: isExpanded ? '1px solid var(--primary)' : undefined,
                    }}
                  >
                    {/* Summary Header */}
                    <div
                      onClick={() => setExpandedSummary(isExpanded ? null : summary.id)}
                      style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span style={{ fontSize: '1.2rem' }}>{'\uD83D\uDCD6'}</span>
                        <div>
                          <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                            {topicName} Özeti
                          </div>
                          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', gap: 12, marginTop: 2 }}>
                            <span>{formatDate(summary.created_at)}</span>
                            <span>{summary.based_on} sorudan</span>
                            {summary.time_taken && <span>{summary.time_taken.toFixed(1)}s</span>}
                          </div>
                        </div>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleDelete(summary.id); }}
                          className="btn btn-secondary"
                          style={{ padding: '6px 12px', fontSize: '0.8rem', color: 'var(--error)' }}
                        >
                          {'\uD83D\uDDD1\uFE0F'}
                        </button>
                        <span style={{
                          fontSize: '1.1rem',
                          transition: 'transform 0.2s',
                          transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                          color: 'var(--text-secondary)',
                        }}>
                          {'\u25BC'}
                        </span>
                      </div>
                    </div>

                    {/* Expanded Content */}
                    {isExpanded && (
                      <div style={{ marginTop: 16, borderTop: '1px solid var(--border)', paddingTop: 16 }}>
                        <div
                          className="solution-content"
                          dangerouslySetInnerHTML={{ __html: renderSolution(summary.summary) }}
                        />
                      </div>
                    )}

                    {/* Preview when collapsed */}
                    {!isExpanded && (
                      <div style={{ marginTop: 10, position: 'relative' }}>
                        <div
                          className="solution-content"
                          style={{ maxHeight: 60, overflow: 'hidden', opacity: 0.6, fontSize: '0.85rem' }}
                          dangerouslySetInnerHTML={{ __html: renderSolution(summary.summary.slice(0, 300)) }}
                        />
                        <div style={{
                          position: 'absolute',
                          bottom: 0,
                          left: 0,
                          right: 0,
                          height: 40,
                          background: 'linear-gradient(transparent, var(--bg-secondary))',
                        }} />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
