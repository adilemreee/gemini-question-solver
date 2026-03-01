import { memo, useEffect, useMemo, useRef, useState } from 'react';
import { renderSolution } from '../lib/markdown';

function splitMarkdownByHeading(raw = '') {
  const normalized = String(raw).replace(/\r\n/g, '\n');
  if (!normalized.trim()) return [{ id: 'section-0', content: '' }];

  const lines = normalized.split('\n');
  const sections = [];
  let chunk = [];
  let inFence = false;
  let fenceToken = '';

  const pushChunk = () => {
    if (chunk.length === 0) return;
    sections.push({
      id: `section-${sections.length}`,
      content: chunk.join('\n').trim(),
    });
    chunk = [];
  };

  for (const line of lines) {
    const fenceMatch = line.match(/^(\s*)(`{3,}|~{3,})/);
    if (fenceMatch) {
      const token = fenceMatch[2][0];
      if (!inFence) {
        inFence = true;
        fenceToken = token;
      } else if (token === fenceToken) {
        inFence = false;
        fenceToken = '';
      }
    }

    const isHeading = !inFence && /^#{1,6}\s+\S/.test(line);
    if (isHeading && chunk.length > 0) {
      pushChunk();
    }
    chunk.push(line);
  }

  pushChunk();

  if (sections.length === 0) {
    return [{ id: 'section-0', content: normalized.trim() }];
  }
  return sections;
}

function observeInView(node, onVisible) {
  if (!node || typeof IntersectionObserver === 'undefined') {
    onVisible();
    return () => {};
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) onVisible();
      });
    },
    { rootMargin: '320px 0px' }
  );

  observer.observe(node);
  return () => observer.disconnect();
}

function scheduleIdle(task) {
  if (typeof window !== 'undefined' && typeof window.requestIdleCallback === 'function') {
    const id = window.requestIdleCallback(task, { timeout: 350 });
    return () => window.cancelIdleCallback(id);
  }
  const timer = setTimeout(task, 16);
  return () => clearTimeout(timer);
}

const SectionedMarkdown = memo(function SectionedMarkdown({ section, eager = false }) {
  const [visible, setVisible] = useState(eager);
  const [ready, setReady] = useState(eager);
  const ref = useRef(null);

  useEffect(() => {
    if (eager) {
      setVisible(true);
      setReady(true);
      return undefined;
    }
    return observeInView(ref.current, () => setVisible(true));
  }, [eager]);

  useEffect(() => {
    if (!visible || ready) return undefined;
    return scheduleIdle(() => setReady(true));
  }, [visible, ready]);

  const html = useMemo(() => (ready ? renderSolution(section.content) : ''), [ready, section.content]);

  return (
    <section ref={ref} className="md-chunk">
      {ready ? (
        <div className="solution-content" dangerouslySetInnerHTML={{ __html: html }} />
      ) : (
        <div className="md-chunk-skeleton" />
      )}
    </section>
  );
});

export { splitMarkdownByHeading };
export default SectionedMarkdown;
