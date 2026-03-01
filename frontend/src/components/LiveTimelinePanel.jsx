import { useMemo, useState, useCallback } from 'react';
import LazyImage from './LazyImage';
import DeferredMarkdown from './DeferredMarkdown';

export default function LiveTimelinePanel({
  processing,
  progressData,
  results,
  liveEvents,
  onViewQuestion,
  onOpenLightbox,
}) {
  const percent = progressData?.total > 0 ? (progressData.progress / progressData.total) * 100 : 0;
  const [expanded, setExpanded] = useState(new Set());

  const timelineItems = useMemo(() => {
    if (results && results.length > 0) return results;
    if (liveEvents && liveEvents.length > 0) return liveEvents;
    return [];
  }, [results, liveEvents]);

  const toggleExpand = useCallback((key) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  return (
    <section className="live-panel">
      <div className="live-header">
        <div>
          <div className="live-title">Canli Akis</div>
          <div className="live-subtitle">{processing ? 'Isleniyor' : 'Tamamlandi'}</div>
        </div>
        <div className="live-metric">
          <span>{progressData?.progress || 0}</span>
          <span>/</span>
          <span>{progressData?.total || results?.length || 0}</span>
        </div>
      </div>

      <div className="progress-bar-container" style={{ marginBottom: 12 }}>
        <div className="progress-bar" style={{ width: `${percent}%` }} />
      </div>

      {timelineItems.length === 0 && (
        <div className="empty-state" style={{ padding: 20 }}>
          Islem kaydi olustukca burada gorunecek
        </div>
      )}

      {timelineItems.length > 0 && (
        <div className="timeline">
          {timelineItems.map((item, idx) => {
            const key = `${item.filename || 'item'}-${idx}`;
            const isExpanded = expanded.has(key);
            const imageSrc = item.filename
              ? `/api/image/${encodeURIComponent(item.filename)}${item.topic ? `?topic=${encodeURIComponent(item.topic)}` : ''}`
              : null;
            const previewText = item.solution ? item.solution.replace(/\s+/g, ' ').slice(0, 220) : '';

            return (
              <div key={key} className="timeline-item">
                <div className={`timeline-dot ${item.success ? 'success' : item.success === false ? 'error' : ''}`} />
                <div className="timeline-card">
                  <div className="timeline-header">
                    <div className="timeline-left">
                      {imageSrc && (
                        <figure className="timeline-figure">
                          <div className="thumb-wrap" onClick={() => onOpenLightbox?.({ src: imageSrc, alt: item.filename })}>
                            <LazyImage src={imageSrc} alt={item.filename} className="timeline-thumb" />
                            <span className="zoom-icon">+</span>
                          </div>
                          <figcaption className="timeline-caption">{item.filename}</figcaption>
                        </figure>
                      )}
                      <div>
                        <div className="timeline-title-row">
                          <div className="timeline-title">{item.success ? 'Cozuldu' : item.success === false ? 'Basarisiz' : 'Islendi'}</div>
                          <span className={`timeline-state ${item.success ? 'success' : item.success === false ? 'error' : 'processing'}`}>
                            {item.success ? 'OK' : item.success === false ? 'Hata' : 'Suruyor'}
                          </span>
                        </div>
                        <div className="timeline-meta">
                          {item.topic && <span className="topic-badge">{item.topic}</span>}
                          {item.time_taken && <span>{item.time_taken.toFixed(1)}s</span>}
                        </div>
                      </div>
                    </div>
                    {item.solution && (
                      <button
                        className="btn btn-secondary"
                        onClick={() =>
                          onViewQuestion({
                            type: 'result',
                            title: item.filename,
                            raw: item.solution,
                            contentType: 'markdown',
                            isError: !item.success,
                          })
                        }
                        style={{ padding: '6px 12px', fontSize: '0.82rem' }}
                      >
                        Goruntule
                      </button>
                    )}
                  </div>

                  {item.solution && (
                    <div className="snippet">
                      {isExpanded ? (
                        <DeferredMarkdown raw={item.solution} eagerCount={1} />
                      ) : (
                        <div className="snippet-text">{previewText}{item.solution.length > 220 ? '...' : ''}</div>
                      )}
                      <button className="snippet-toggle" onClick={() => toggleExpand(key)}>
                        {isExpanded ? 'Kisalt' : 'Genislet'}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
