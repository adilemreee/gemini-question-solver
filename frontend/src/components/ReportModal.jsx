import { useState, useCallback, useMemo } from 'react';
import { motion } from 'framer-motion';
import { api } from '../lib/api';
import { renderSolution } from '../lib/markdown';
import DeferredMarkdown from './DeferredMarkdown';
import toast from 'react-hot-toast';

function escapeHtml(text = '') {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

export default function ReportModal({ data, onClose }) {
  const [explaining, setExplaining] = useState(false);
  const [explanation, setExplanation] = useState(null);
  const [hintLevel, setHintLevel] = useState(0);
  const [hints, setHints] = useState({});
  const [loadingHint, setLoadingHint] = useState(false);

  const contentType = data.contentType || (data.raw ? 'markdown' : 'html');
  const markdownRaw = data.raw || '';
  const htmlContent = data.content || '';

  const printableHtml = useMemo(() => {
    if (contentType === 'markdown') return renderSolution(markdownRaw);
    if (contentType === 'text') return `<pre>${escapeHtml(markdownRaw || htmlContent)}</pre>`;
    return htmlContent;
  }, [contentType, markdownRaw, htmlContent]);

  const handlePrint = () => {
    if (!printableHtml) return;
    const w = window.open('', '_blank');
    w.document.write(`<!DOCTYPE html><html><head><meta charset="UTF-8"><title>${data.title}</title>
      <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
      <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif;line-height:1.8;padding:48px;color:#1a1a2e;background:#fff;max-width:860px;margin:0 auto}
        h1{color:#31517a;border-bottom:2px solid #e8dcc6;padding-bottom:16px;margin-bottom:28px;font-size:22px}
        h2{color:#31517a;margin-top:32px;margin-bottom:14px;font-size:18px}
        h3{color:#4f6f99;margin-top:24px;margin-bottom:10px;font-size:15px}
        p{margin-bottom:14px;line-height:1.8;color:#374151}
        strong{color:#1f2937}
        code{background:#f3efe8;padding:2px 6px;border-radius:4px;font-family:monospace;font-size:13px;color:#31517a}
        pre{background:#f8f5ef;color:#1f2937;padding:20px;border-radius:8px;overflow-x:auto;margin:20px 0;border:1px solid #e8dcc6}
        pre code{background:transparent;color:inherit;padding:0}
        ul,ol{margin-left:24px;margin-bottom:16px}li{margin-bottom:8px;line-height:1.7}
        hr{border:none;border-top:1px solid #e8dcc6;margin:28px 0}
        blockquote{border-left:3px solid #6b8ab3;padding:12px 16px;margin:16px 0;background:#f8f5ef;border-radius:0 4px 4px 0}
        table{width:100%;border-collapse:collapse;margin:16px 0}
        th,td{border:1px solid #e8dcc6;padding:10px 14px;text-align:left}
        th{background:#f8f5ef;font-weight:600}
        .katex{font-size:1.1em}
        .katex-display{margin:20px 0;padding:16px;background:#f8f5ef;border-radius:8px;border-left:3px solid #6b8ab3}
        .footer{margin-top:48px;padding-top:16px;border-top:1px solid #e8dcc6;text-align:center;color:#7b8798;font-size:11px}
        @media print{body{padding:20px}@page{margin:1.5cm}}
      </style></head><body>
      <h1>${escapeHtml(data.title || 'Rapor')}</h1>
      ${printableHtml}
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

  const handleExplain = useCallback(async () => {
    if (!data.questionId) return;
    const selectedText = window.getSelection()?.toString() || '';
    setExplaining(true);
    setExplanation(null);
    try {
      const result = await api.explainQuestion(data.questionId, selectedText);
      if (result.success) {
        setExplanation(result.explanation);
        toast.success('Aciklama olusturuldu');
      } else {
        toast.error(result.error || 'Aciklama basarisiz');
      }
    } catch (err) {
      toast.error(err.message);
    } finally {
      setExplaining(false);
    }
  }, [data.questionId]);

  const handleHint = useCallback(async (level) => {
    if (!data.questionId) return;
    setLoadingHint(true);
    try {
      const result = await api.getHints(data.questionId, level);
      if (result.success) {
        setHints((prev) => ({ ...prev, [level]: result.hint }));
        setHintLevel(level);
        toast.success(`Ipucu ${level} olusturuldu`);
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
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="modal-backdrop"
        onClick={onClose}
      />

      <div className="modal-center">
        <motion.div
          initial={{ opacity: 0, scale: 0.92, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.92, y: 20 }}
          transition={{ type: 'spring', stiffness: 280, damping: 28 }}
          className="report-viewer"
        >
          <div className="report-header">
            <h3>{'\uD83D\uDCC4'} {data.title}</h3>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {isQuestion && data.questionId && !data.isError && (
                <>
                  <button
                    onClick={handleExplain}
                    disabled={explaining}
                    className="btn btn-secondary"
                    style={{ padding: '8px 14px', fontSize: '0.82rem' }}
                  >
                    {explaining ? (
                      <><span className="spinner-ring" style={{ display: 'inline-block', width: 14, height: 14 }} /> Aciklaniyor...</>
                    ) : (
                      <>{'\uD83E\uDD14'} Anlat</>
                    )}
                  </button>
                  <button
                    onClick={() => handleHint(Math.min((hintLevel || 0) + 1, 3))}
                    disabled={loadingHint}
                    className="btn btn-secondary"
                    style={{ padding: '8px 14px', fontSize: '0.82rem' }}
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
                    {'\uD83D\uDCE5'} PDF
                  </button>
                  <button onClick={handlePrint} className="btn btn-secondary" style={{ padding: '8px 16px', fontSize: '0.85rem' }}>
                    {'\uD83D\uDDA8\uFE0F'} Yazdir
                  </button>
                  <button onClick={handleDownloadMD} className="btn btn-secondary" style={{ padding: '8px 16px', fontSize: '0.85rem' }}>
                    {'\u2B07\uFE0F'} MD
                  </button>
                </>
              )}
              <button onClick={onClose} className="btn btn-secondary" style={{ padding: '8px 16px', fontSize: '0.85rem' }}>
                {'\u2715'} Kapat
              </button>
            </div>
          </div>

          {data.meta && (
            <div className="modal-meta">
              {data.meta.imageUrl && (
                <img src={data.meta.imageUrl} alt={data.title} className="modal-meta-image" />
              )}
              <div className="modal-meta-grid">
                {data.meta.topic && <div><strong>Konu:</strong> {data.meta.topic}</div>}
                {data.meta.status && <div><strong>Durum:</strong> {data.meta.status}</div>}
                {data.meta.timeTaken != null && <div><strong>Sure:</strong> {data.meta.timeTaken.toFixed(2)}s</div>}
                {data.meta.createdAt && <div><strong>Tarih:</strong> {new Date(data.meta.createdAt).toLocaleString('tr-TR', { timeZone: 'Europe/Istanbul' })}</div>}
              </div>
            </div>
          )}

          {Object.keys(hints).length > 0 && (
            <div style={{ padding: '0 24px' }}>
              {[1, 2, 3].map((level) => hints[level] && (
                <div key={level} className="hint-card">
                  <div className="hint-title">{'\uD83D\uDCA1'} Ipucu {level}</div>
                  <DeferredMarkdown raw={hints[level]} />
                </div>
              ))}
            </div>
          )}

          {explanation && (
            <div style={{ padding: '0 24px', marginBottom: 12 }}>
              <div className="hint-card">
                <div className="hint-title">{'\uD83E\uDD14'} Aciklama</div>
                <DeferredMarkdown raw={explanation} />
              </div>
            </div>
          )}

          <div className="report-body markdown-scroll">
            {contentType === 'markdown' && (
              <DeferredMarkdown raw={markdownRaw} />
            )}
            {contentType === 'text' && (
              <pre className="plain-text">{markdownRaw || htmlContent}</pre>
            )}
            {contentType === 'html' && (
              <div className="solution-content" dangerouslySetInnerHTML={{ __html: htmlContent }} />
            )}
          </div>
        </motion.div>
      </div>
    </>
  );
}
