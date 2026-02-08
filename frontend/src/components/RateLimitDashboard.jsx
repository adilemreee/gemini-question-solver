import { useState, useEffect, useCallback } from 'react';
import { api } from '../lib/api';
import toast from 'react-hot-toast';

export default function RateLimitDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(false);

  const load = useCallback(async () => {
    try {
      const result = await api.getRateLimit();
      setData(result);
    } catch (err) {
      toast.error('Rate limit verileri yuklenemedi');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, load]);

  const StatCard = ({ title, emoji, stats }) => (
    <div className="result-card" style={{ margin: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
        <span style={{ fontSize: '1.5rem' }}>{emoji}</span>
        <span style={{ fontWeight: 600 }}>{title}</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <div style={{ textAlign: 'center', padding: 10, background: 'rgba(99,102,241,0.08)', borderRadius: 10 }}>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--primary)' }}>{stats.count}</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Istek</div>
        </div>
        <div style={{ textAlign: 'center', padding: 10, background: 'rgba(52,211,153,0.08)', borderRadius: 10 }}>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--success)' }}>{stats.avg_duration}s</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Ort. Sure</div>
        </div>
      </div>
    </div>
  );

  return (
    <div>
      <div className="folder-section">
        <div className="folder-header">
          <div className="folder-info">
            <span className="folder-icon">{'\uD83D\uDCCA'}</span>
            <div>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>API Kullanim Paneli</div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                Gemini API istek istatistikleri ve rate limit durumu
              </div>
            </div>
          </div>
          <div className="folder-actions">
            <button onClick={load} disabled={loading} className="btn btn-secondary" style={{ padding: '8px 14px', fontSize: '0.85rem' }}>
              {'\uD83D\uDD04'} Yenile
            </button>
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`btn ${autoRefresh ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '8px 14px', fontSize: '0.85rem' }}
            >
              {autoRefresh ? '\u23F8\uFE0F Durdur' : '\u25B6\uFE0F Otomatik'}
            </button>
          </div>
        </div>

        {loading && !data && (
          <div className="empty-state">
            <div className="spinner-ring" style={{ width: 40, height: 40, margin: '0 auto' }} />
            <div style={{ marginTop: 16 }}>Veriler yukleniyor...</div>
          </div>
        )}

        {data && (
          <>
            {/* Overview Stats */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 16, marginTop: 16 }}>
              <StatCard title="Son 1 Dakika" emoji={'\u23F1\uFE0F'} stats={data.last_minute} />
              <StatCard title="Son 1 Saat" emoji={'\uD83D\uDD52'} stats={data.last_hour} />
              <StatCard title="Son 24 Saat" emoji={'\uD83D\uDCC5'} stats={data.last_day} />
            </div>

            {/* Total Counter */}
            <div style={{ marginTop: 20, padding: 16, background: 'rgba(99,102,241,0.06)', borderRadius: 12, textAlign: 'center' }}>
              <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>Toplam API istegi: </span>
              <span style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--primary)' }}>{data.total_all_time}</span>
            </div>

            {/* Recent Requests Log */}
            {data.recent_requests && data.recent_requests.length > 0 && (
              <div style={{ marginTop: 20 }}>
                <div style={{ fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
                  {'\uD83D\uDCCB'} Son Istekler
                </div>
                <div style={{ maxHeight: 300, overflowY: 'auto', borderRadius: 10 }}>
                  {data.recent_requests.map((req, i) => {
                    const time = new Date(req.timestamp);
                    const timeStr = time.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit', timeZone: 'Europe/Istanbul' });
                    return (
                      <div key={i} className="history-item" style={{ padding: '10px 16px', marginBottom: 4 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1 }}>
                          <span style={{ color: 'var(--success)', fontSize: '0.9rem' }}>{'\u2705'}</span>
                          <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>{timeStr}</span>
                          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{req.model}</span>
                        </div>
                        <span style={{ fontSize: '0.85rem', color: 'var(--primary)', fontWeight: 500 }}>
                          {req.duration.toFixed(1)}s
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
