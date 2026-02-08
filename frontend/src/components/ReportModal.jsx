import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { api } from '../lib/api';
import { renderSolution } from '../lib/markdown';
import toast from 'react-hot-toast';

export default function ReportModal({ data, onClose }) {
  const [explaining, setExplaining] = useState(false);
  const [explanation, setExplanation] = useState(null);
  const [hintLevel, setHintLevel] = useState(0);
  const [hints, setHints] = useState({});
  const [loadingHint, setLoadingHint] = useState(false);

  const handlePrint = () => {
    if (!data.content) return;
    const w = window.open('', '_blank');
    w.document.write(`<!DOCTYPE html><html><head><meta charset="UTF-8"><title>${data.title}</title>
      <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
      <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;line-height:1.8;padding:48px;color:#1a1a2e;background:#fff;max-width:800px;margin:0 auto}
        h1{color:#4f46e5;border-bottom:2px solid #e5e7eb;padding-bottom:16px;margin-bottom:28px;font-size:22px}
        h2{color:#4f46e5;margin-top:32px;margin-bottom:14px;font-size:18px}
        h3{color:#4338ca;margin-top:24px;margin-bottom:10px;font-size:15px}
        p{margin-bottom:14px;line-height:1.8;color:#374151}
        strong{color:#1f2937}
        code{background:#f3f4f6;padding:2px 6px;border-radius:4px;font-family:monospace;font-size:13px;color:#4f46e5}
        pre{background:#1e1e2e;color:#cdd6f4;padding:20px;border-radius:8px;overflow-x:auto;margin:20px 0}
        pre code{background:transparent;color:inherit;padding:0}
        ul,ol{margin-left:24px;margin-bottom:16px}li{margin-bottom:8px;line-height:1.7}
        hr{border:none;border-top:1px solid #e5e7eb;margin:28px 0}
        blockquote{border-left:3px solid #6366f1;padding:12px 16px;margin:16px 0;background:#f5f3ff;border-radius:0 4px 4px 0}
        table{width:100%;border-collapse:collapse;margin:16px 0}
        th,td{border:1px solid #e5e7eb;padding:10px 14px;text-align:left}
        th{background:#f9fafb;font-weight:600}
        .katex{font-size:1.1em}
        .katex-display{margin:20px 0;padding:16px;background:#f5f3ff;border-radius:8px;border-left:3px solid #6366f1}
        .footer{margin-top:48px;padding-top:16px;border-top:1px solid #e5e7eb;text-align:center;color:#9ca3af;font-size:11px}
        @media print{body{padding:20px}@page{margin:1.5cm}}
      </style></head><body>
      <h1>${data.title}</h1>
      ${data.content}
      <div class="footer">Gemini Question Solver ile olusturuldu</div>
      <script>window.onload=function(){setTimeout(function(){window.print()},500)}<\/script>
    </body></html>`);
    w.document.close();
  };

  const handleDownloadMD = () => {
    if (!data.filename) return;
    window.open(`/api/report/${encodeURIComponent(data.filename)}/raw`, '_blank');
  };

  const handleDownloadPDF = () => {
    if (!data.filename) return;
    window.open(`/api/report/${encodeURIComponent(data.filename)}/pdf`, '_blank');
  };

  // "Bunu anlamadim" - re-explain with AI
  const handleExplain = useCallback(async () => {
    if (!data.questionId) return;
    const selectedText = window.getSelection()?.toString() || '';
    setExplaining(true);
    setExplanation(null);
    try {
      const result = await api.explainQuestion(data.questionId, selectedText);
      if (result.success) {
        setExplanation(result.explanation);
        toast.success('Aciklama olusturuldu!');
      } else {
        toast.error(result.error || 'Aciklama basarisiz');
      }
    } catch (err) {
      toast.error(err.message);
    } finally {
      setExplaining(false);
    }
  }, [data.questionId]);

  // Ipucu modu - progressive hints
  const handleHint = useCallback(async (level) => {
    if (!data.questionId) return;
    setLoadingHint(true);
    try {
      const result = await api.getHints(data.questionId, level);
      if (result.success) {
        setHints((prev) => ({ ...prev, [level]: result.hint }));
        setHintLevel(level);
        toast.success(`Ipucu ${level} olusturuldu!`);
      } else {
        toast.error(result.error || 'Ipucu olusturulamadi');
      }
    } catch (err) {
      toast.error(err.message);
    } finally {
      setLoadingHint(false);
    }
  }, [data.questionId]);

  const isQuestion = data.type === 'question' || data.type === 'result';

  return (
    <>
      {/* Backdrop */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="modal-backdrop"
        onClick={onClose}
      />

      {/* Centering wrapper */}
      <div className="modal-center">
        <motion.div
          initial={{ opacity: 0, scale: 0.92, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.92, y: 20 }}
          transition={{ type: 'spring', stiffness: 300, damping: 28 }}
          className="report-viewer"
        >
        {/* Header */}
        <div className="report-header">
          <h3 style={{ fontSize: '1.1rem' }}>
            {'\uD83D\uDCC4'} {data.title}
          </h3>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {/* AI Features - only for questions */}
            {isQuestion && data.questionId && !data.isError && (
              <>
                <button
                  onClick={handleExplain}
                  disabled={explaining}
                  className="btn btn-secondary"
                  style={{ padding: '8px 14px', fontSize: '0.82rem', background: 'rgba(251,191,36,0.12)', borderColor: 'rgba(251,191,36,0.3)' }}
                >
                  {explaining ? (
                    <><span className="spinner-ring" style={{ display: 'inline-block', width: 14, height: 14 }} /> Aciklaniyor...</>
                  ) : (
                    <>{'\uD83E\uDD14'} Bunu Anlamadim</>
                  )}
                </button>
                <button
                  onClick={() => handleHint(Math.min((hintLevel || 0) + 1, 3))}
                  disabled={loadingHint}
                  className="btn btn-secondary"
                  style={{ padding: '8px 14px', fontSize: '0.82rem', background: 'rgba(52,211,153,0.12)', borderColor: 'rgba(52,211,153,0.3)' }}
                >
                  {loadingHint ? (
                    <><span className="spinner-ring" style={{ display: 'inline-block', width: 14, height: 14 }} /> Ipucu...</>
                  ) : (
                    <>{'\uD83D\uDCA1'} Ipucu {hintLevel > 0 ? `(${Math.min(hintLevel + 1, 3)}/3)` : ''}</>
                  )}
                </button>
              </>
            )}
            {data.type === 'report' && (
              <>
                <button onClick={handleDownloadPDF} className="btn btn-primary" style={{ padding: '8px 16px', fontSize: '0.85rem' }}>
                  {'\uD83D\uDCE5'} PDF Indir
                </button>
                <button onClick={handlePrint} className="btn btn-secondary" style={{ padding: '8px 16px', fontSize: '0.85rem' }}>
                  {'\uD83D\uDDA8\uFE0F'} Yazdir
                </button>
                <button onClick={handleDownloadMD} className="btn btn-secondary" style={{ padding: '8px 16px', fontSize: '0.85rem' }}>
                  {'\u2B07\uFE0F'} MD Indir
                </button>
              </>
            )}
            <button onClick={onClose} className="btn btn-secondary" style={{ padding: '8px 16px', fontSize: '0.85rem' }}>
              {'\u2715'} Kapat
            </button>
          </div>
        </div>

        {/* Hint Cards */}
        {Object.keys(hints).length > 0 && (
          <div style={{ padding: '0 24px' }}>
            {[1, 2, 3].map((level) => hints[level] && (
              <div key={level} style={{
                marginBottom: 12,
                padding: 16,
                background: level === 1 ? 'rgba(52,211,153,0.06)' : level === 2 ? 'rgba(251,191,36,0.06)' : 'rgba(239,68,68,0.06)',
                borderRadius: 12,
                border: `1px solid ${level === 1 ? 'rgba(52,211,153,0.2)' : level === 2 ? 'rgba(251,191,36,0.2)' : 'rgba(239,68,68,0.2)'}`,
              }}>
                <div style={{ fontWeight: 600, marginBottom: 8, fontSize: '0.9rem', color: level === 1 ? 'var(--success)' : level === 2 ? 'var(--warning)' : 'var(--error)' }}>
                  {'\uD83D\uDCA1'} Ipucu {level} - {level === 1 ? 'Hafif' : level === 2 ? 'Orta' : 'Detayli'}
                </div>
                <div className="solution-content" dangerouslySetInnerHTML={{ __html: renderSolution(hints[level]) }} />
              </div>
            ))}
          </div>
        )}

        {/* Explanation Section */}
        {explanation && (
          <div style={{ padding: '0 24px', marginBottom: 12 }}>
            <div style={{
              padding: 16,
              background: 'rgba(251,191,36,0.06)',
              borderRadius: 12,
              border: '1px solid rgba(251,191,36,0.2)',
            }}>
              <div style={{ fontWeight: 600, marginBottom: 8, fontSize: '0.9rem', color: 'var(--warning)' }}>
                {'\uD83E\uDD14'} Basitlestirilmis Aciklama
              </div>
              <div className="solution-content" dangerouslySetInnerHTML={{ __html: renderSolution(explanation) }} />
            </div>
          </div>
        )}

        {/* Content */}
        <div className="report-body">
          {data.isError ? (
            <div style={{ color: 'var(--error)', padding: 16, border: '1px solid rgba(248,113,113,0.3)', borderRadius: 14, background: 'rgba(248,113,113,0.08)' }}>
              {data.content}
            </div>
          ) : (
            <div className="solution-content" dangerouslySetInnerHTML={{ __html: data.content }} />
          )}
        </div>
        </motion.div>
      </div>
    </>
  );
}
