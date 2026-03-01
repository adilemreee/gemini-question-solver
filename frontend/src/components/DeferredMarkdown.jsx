import { useMemo } from 'react';
import SectionedMarkdown, { splitMarkdownByHeading } from './SectionedMarkdown';

export default function DeferredMarkdown({ raw, className = '', eagerCount = 2 }) {
  const sections = useMemo(() => splitMarkdownByHeading(raw), [raw]);

  return (
    <div className={`deferred-markdown ${className}`.trim()}>
      {sections.map((section, idx) => (
        <SectionedMarkdown key={section.id} section={section} eager={idx < eagerCount} />
      ))}
    </div>
  );
}
