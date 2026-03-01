import { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { api } from './lib/api';
import FolderMode from './components/FolderMode';
import UploadMode from './components/UploadMode';
import ReportsMode from './components/ReportsMode';
import HistoryMode from './components/HistoryMode';
import TopicSummaryMode from './components/TopicSummaryMode';
import RateLimitDashboard from './components/RateLimitDashboard';
import LiveTimelinePanel from './components/LiveTimelinePanel';
import ReportModal from './components/ReportModal';
import ImageLightbox from './components/ImageLightbox';
import { useWebSocket } from './hooks/useWebSocket';
import { useProgress } from './hooks/useProgress';
import toast from 'react-hot-toast';

const TABS = [
  { id: 'folder', label: 'Klasor Tarama', short: 'Tarama', emoji: '\uD83D\uDCC1' },
  { id: 'upload', label: 'Dosya Yukleme', short: 'Yukleme', emoji: '\uD83D\uDCE4' },
  { id: 'reports', label: 'Raporlar', short: 'Rapor', emoji: '\uD83D\uDCC4' },
  { id: 'history', label: 'Gecmis', short: 'Gecmis', emoji: '\uD83D\uDCDA' },
  { id: 'topics', label: 'Konu Ozeti', short: 'Ozetler', emoji: '\uD83D\uDCDD' },
  { id: 'ratelimit', label: 'API Kullanim', short: 'Kullanim', emoji: '\uD83D\uDCCA' },
];

export default function App() {
  const [mode, setMode] = useState('folder');
  const [apiReady, setApiReady] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [progressData, setProgressData] = useState(null);
  const [results, setResults] = useState(null);
  const [modalData, setModalData] = useState(null);
  const [liveEvents, setLiveEvents] = useState([]);
  const [lightboxImage, setLightboxImage] = useState(null);
  const lastTickRef = useRef(0);

  const activeMode = TABS.find((t) => t.id === mode) || TABS[0];
  const doneCount = progressData?.progress || 0;
  const totalCount = progressData?.total || 0;
  const completionRate = totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0;

  useEffect(() => {
    api.getStatus().then((d) => {
      setApiReady(d.api_key_set);
    }).catch(() => setApiReady(false));
  }, []);

  const handleComplete = useCallback((data) => {
    setProcessing(false);
    setProgressData(data);
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

  const handleTick = useCallback((data) => {
    const now = Date.now();
    if (data?.status !== 'completed' && now - lastTickRef.current < 120) return;
    lastTickRef.current = now;

    const nextData = data?.status === 'completed'
      ? data
      : { ...data, results: undefined };
    setProgressData(nextData);

    if (data?.latest_result?.filename) {
      setLiveEvents((prev) => {
        const exists = prev.find((e) => e.filename === data.latest_result.filename);
        if (exists) return prev;
        return [{ ...data.latest_result, timestamp: Date.now() }, ...prev].slice(0, 30);
      });
    }
  }, []);

  const startSolving = useCallback(
    (sessionId) => {
      setProcessing(true);
      setResults(null);
      setLiveEvents([]);
      setProgressData({ progress: 0, total: 0, results: [] });
      
      // Try WebSocket first, fall back to polling
      try {
        ws.start(sessionId, handleTick);
      } catch {
        startPolling(sessionId, handleTick);
      }
    },
    [ws, startPolling, handleTick]
  );

  const openModal = useCallback((data) => setModalData(data), []);
  const closeModal = useCallback(() => setModalData(null), []);
  const openLightbox = useCallback((img) => setLightboxImage(img), []);
  const closeLightbox = useCallback(() => setLightboxImage(null), []);

  return (
    <>
      {/* Background decoration */}
      <div className="bg-decoration" />

      <div className="app-shell">
        <aside className="sidebar">
          <div className="brand">
            <div className="brand-icon">{'\uD83E\uDDE0'}</div>
            <div>
              <div className="brand-title">Gemini Solver</div>
              <div className="brand-subtitle">Akademik Cozum Platformu</div>
            </div>
          </div>

          <nav className="sidebar-nav">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => { setMode(tab.id); setResults(null); }}
                className={`sidebar-link ${mode === tab.id ? 'active' : ''}`}
              >
                <span className="sidebar-emoji">{tab.emoji}</span>
                <span>{tab.label}</span>
              </button>
            ))}
          </nav>

          <div className="sidebar-status">
            <div className={`status-dot ${
              apiReady === null ? 'checking' : apiReady ? 'connected' : 'disconnected'
            }`} />
            <span>{apiReady === null ? 'API kontrol ediliyor' : apiReady ? 'API hazir' : 'API anahtari eksik'}</span>
          </div>
        </aside>

        <main className="main">
          <section className="hero">
            <div className="hero-grid">
              <div>
                <div className="hero-eyebrow">Gemini Question Solver</div>
                <h1>Akademik soru cozum paneli</h1>
                <p>Gorselleri yukle veya klasorden tara; paralel cozum ve duzenli rapor akisini tek ekranda yonet.</p>
              </div>
              <div className="hero-metrics">
                <div className="hero-metric-card">
                  <span>Mod</span>
                  <strong>{activeMode.label}</strong>
                </div>
                <div className="hero-metric-card">
                  <span>Islem</span>
                  <strong>{processing ? 'Devam ediyor' : 'Hazir'}</strong>
                </div>
                <div className="hero-metric-card">
                  <span>Ilerleme</span>
                  <strong>{totalCount > 0 ? `%${completionRate}` : '-'}</strong>
                </div>
              </div>
            </div>
          </section>

          <div className="mode-switch-wrap">
            <div className="mode-switch">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => { setMode(tab.id); setResults(null); }}
                  className={`chip ${mode === tab.id ? 'active' : ''}`}
                >
                  {tab.short}
                </button>
              ))}
            </div>
          </div>

          <div className="content-stack">
            <section className="workflow-column">
              <AnimatePresence mode="wait">
                <motion.div
                  key={mode}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.2 }}
                >
                  {mode === 'folder' && (
                    <FolderMode
                      onStartSolving={startSolving}
                      processing={processing}
                      progressData={progressData}
                      onOpenLightbox={openLightbox}
                    />
                  )}
                  {mode === 'upload' && (
                    <UploadMode onStartSolving={startSolving} processing={processing} onOpenLightbox={openLightbox} />
                  )}
                  {mode === 'reports' && <ReportsMode onViewReport={openModal} />}
                  {mode === 'history' && (
                    <HistoryMode
                      onViewQuestion={openModal}
                      onStartSolving={startSolving}
                      processing={processing}
                      onOpenLightbox={openLightbox}
                    />
                  )}
                  {mode === 'topics' && <TopicSummaryMode />}
                  {mode === 'ratelimit' && <RateLimitDashboard />}
                </motion.div>
              </AnimatePresence>
            </section>

            {mode === 'folder' && processing && (
              <aside className="live-column">
                <LiveTimelinePanel
                  processing={processing}
                  progressData={progressData}
                  results={results}
                  liveEvents={liveEvents}
                  onViewQuestion={openModal}
                  onOpenLightbox={openLightbox}
                />
              </aside>
            )}
          </div>
        </main>
      </div>

      <ImageLightbox image={lightboxImage} onClose={closeLightbox} />
      {/* Modal */}
      <AnimatePresence>
        {modalData && <ReportModal data={modalData} onClose={closeModal} />}
      </AnimatePresence>
    </>
  );
}
