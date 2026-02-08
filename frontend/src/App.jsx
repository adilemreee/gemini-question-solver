import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from './lib/api';
import FolderMode from './components/FolderMode';
import UploadMode from './components/UploadMode';
import ReportsMode from './components/ReportsMode';
import HistoryMode from './components/HistoryMode';
import TopicSummaryMode from './components/TopicSummaryMode';
import RateLimitDashboard from './components/RateLimitDashboard';
import ProgressSection from './components/ProgressSection';
import ResultsSection from './components/ResultsSection';
import ReportModal from './components/ReportModal';
import { useWebSocket } from './hooks/useWebSocket';
import { useProgress } from './hooks/useProgress';
import toast from 'react-hot-toast';

const TABS = [
  { id: 'folder', label: 'Klasorden Tara', emoji: '\uD83D\uDCC1' },
  { id: 'upload', label: 'Dosya Yukle', emoji: '\uD83D\uDCE4' },
  { id: 'reports', label: 'Raporlar', emoji: '\uD83D\uDCC4' },
  { id: 'history', label: 'Gecmis', emoji: '\uD83D\uDCDA' },
  { id: 'topics', label: 'Konu Ozeti', emoji: '\uD83D\uDCDD' },
  { id: 'ratelimit', label: 'API Kullanim', emoji: '\uD83D\uDCCA' },
];

export default function App() {
  const [mode, setMode] = useState('folder');
  const [apiReady, setApiReady] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [progressData, setProgressData] = useState(null);
  const [results, setResults] = useState(null);
  const [modalData, setModalData] = useState(null);

  useEffect(() => {
    api.getStatus().then((d) => {
      setApiReady(d.api_key_set);
    }).catch(() => setApiReady(false));
  }, []);

  const handleComplete = useCallback((data) => {
    setProcessing(false);
    setProgressData(null);
    setResults(data.results);
    const ok = data.results.filter((r) => r.success).length;
    toast.success(`${ok} / ${data.total || data.results.length} soru basariyla cozuldu`);
  }, []);

  const handleError = useCallback((err) => {
    setProcessing(false);
    setProgressData(null);
    toast.error(err);
  }, []);

  // WebSocket primary, polling fallback
  const ws = useWebSocket(handleComplete, handleError);
  const { start: startPolling } = useProgress(handleComplete, handleError);

  const startSolving = useCallback(
    (sessionId) => {
      setProcessing(true);
      setResults(null);
      setProgressData({ progress: 0, total: 0, results: [] });
      
      // Try WebSocket first, fall back to polling
      try {
        ws.start(sessionId, (data) => setProgressData(data));
      } catch {
        startPolling(sessionId, (data) => setProgressData(data));
      }
    },
    [ws, startPolling]
  );

  const openModal = useCallback((data) => setModalData(data), []);
  const closeModal = useCallback(() => setModalData(null), []);

  return (
    <>
      {/* Background decoration */}
      <div className="bg-decoration" />

      <div className="container">
        {/* Header */}
        <header className="header">
          <h1>
            {'\uD83E\uDDE0'} Gemini Question Solver
          </h1>
          <p>
            Soru fotograflarini yukle veya klasorden tara, paralel olarak coz
          </p>
        </header>

        {/* Status bar */}
        <div className="status-bar">
          <div className={`status-dot ${
            apiReady === null ? 'checking' : apiReady ? 'connected' : 'disconnected'
          }`} />
          <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
            {apiReady === null ? 'API baglantisi kontrol ediliyor...' : apiReady ? 'API baglantisi hazir \u2713' : '\u26A0\uFE0F GEMINI_API_KEY ayarlanmamis'}
          </span>
        </div>

        {/* Mode Tabs */}
        <div className="mode-tabs">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => { setMode(tab.id); setResults(null); }}
              className={`mode-tab ${mode === tab.id ? 'active' : ''}`}
            >
              {tab.emoji} {tab.label}
            </button>
          ))}
        </div>

        {/* Progress */}
        <AnimatePresence>
          {processing && progressData && <ProgressSection data={progressData} />}
        </AnimatePresence>

        {/* Mode Content */}
        <AnimatePresence mode="wait">
          <motion.div
            key={mode}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            {mode === 'folder' && (
              <FolderMode onStartSolving={startSolving} processing={processing} progressData={progressData} />
            )}
            {mode === 'upload' && (
              <UploadMode onStartSolving={startSolving} processing={processing} />
            )}
            {mode === 'reports' && <ReportsMode onViewReport={openModal} />}
            {mode === 'history' && (
              <HistoryMode onViewQuestion={openModal} onStartSolving={startSolving} processing={processing} />
            )}
            {mode === 'topics' && <TopicSummaryMode />}
            {mode === 'ratelimit' && <RateLimitDashboard />}
          </motion.div>
        </AnimatePresence>

        {/* Completion Banner & Results - below mode content */}
        <AnimatePresence>
          {results && (
            <ResultsSection results={results} mode={mode} onViewQuestion={openModal} />
          )}
        </AnimatePresence>
      </div>{/* container end */}

      {/* Modal */}
      <AnimatePresence>
        {modalData && <ReportModal data={modalData} onClose={closeModal} />}
      </AnimatePresence>
    </>
  );
}
