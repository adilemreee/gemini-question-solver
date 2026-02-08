import { motion } from 'framer-motion';

export default function ProgressSection({ data }) {
  const percent = data.total > 0 ? (data.progress / data.total) * 100 : 0;
  const latest = data.latest_result;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="progress-section"
    >
      {/* Header */}
      <div className="progress-header">
        <span className="progress-title gradient-text">
          {'\uD83E\uDDE0'} Isleniyor...
        </span>
        <span style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>
          {data.progress} / {data.total}
        </span>
      </div>

      {/* Progress bar */}
      <div className="progress-bar-container">
        <motion.div
          className="progress-bar"
          initial={{ width: 0 }}
          animate={{ width: `${percent}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        >
          <div className="progress-shimmer" />
        </motion.div>
      </div>

      {/* Footer */}
      <div className="progress-footer">
        <span>{'\u2728'} Paralel isleme aktif</span>
        <span style={{ fontWeight: 600 }}>%{Math.round(percent)}</span>
      </div>

      {/* Live result indicator (from WebSocket) */}
      {latest && (
        <div style={{
          marginTop: 8,
          padding: '8px 14px',
          fontSize: '0.82rem',
          color: 'var(--text-secondary)',
          background: 'rgba(99,102,241,0.06)',
          borderRadius: 8,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}>
          <span>{latest.success ? '\u2705' : '\u274C'}</span>
          <span style={{ fontWeight: 500 }}>{latest.filename}</span>
          {latest.topic && <span style={{ opacity: 0.7 }}>({latest.topic})</span>}
          {latest.time_taken && <span style={{ opacity: 0.5 }}>{latest.time_taken.toFixed(1)}s</span>}
        </div>
      )}
    </motion.div>
  );
}
