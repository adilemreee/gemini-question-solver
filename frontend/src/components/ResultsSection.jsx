import { motion } from 'framer-motion';
import { renderSolution } from '../lib/markdown';

export default function ResultsSection({ results, mode, onViewQuestion }) {
  if (!results || results.length === 0) return null;
  const successCount = results.filter((r) => r.success).length;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      style={{ marginBottom: 32 }}
    >
      {/* Completion Banner */}
      <div className="completion-banner">
        <h2>
          {'\u2705'} Tamamlandi!
        </h2>
        <p>
          {successCount} / {results.length} soru basariyla cozuldu
        </p>
      </div>

      {/* Result Cards */}
      {results.map((result, idx) => (
        <div
          key={idx}
          className="result-card"
        >
          <div className="result-header">
            {/* Thumbnail */}
            <img
              src={`/api/image/${encodeURIComponent(result.filename)}`}
              alt={result.filename}
              className="result-image"
              onError={(e) => (e.target.style.display = 'none')}
            />
            {/* Info */}
            <div className="result-info">
              <h3>
                Soru {idx + 1}: {result.filename}
              </h3>
              <div className="result-meta">
                <span>{result.success ? '\u2705 Cozuldu' : '\u274C Basarisiz'}</span>
                <span>{result.time_taken?.toFixed(1)}s</span>
                {result.topic && result.topic !== 'Genel' && <span>{result.topic}</span>}
              </div>
            </div>
            <button
              onClick={() => onViewQuestion({
                type: 'result',
                title: result.filename,
                content: result.success ? renderSolution(result.solution) : result.error,
                isError: !result.success,
              })}
              className="btn btn-secondary"
              style={{ padding: '8px 16px', fontSize: '0.85rem' }}
            >
              {'\uD83D\uDC41\uFE0F'} Goruntule
            </button>
          </div>

          {/* Solution preview */}
          {result.success && result.solution && (
            <div style={{ position: 'relative' }}>
              <div
                className="solution-content solution-preview"
                dangerouslySetInnerHTML={{ __html: renderSolution(result.solution) }}
              />
              <div className="solution-fade" />
            </div>
          )}
        </div>
      ))}
    </motion.div>
  );
}
