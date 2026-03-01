import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export default function ImageLightbox({ image, onClose }) {
  useEffect(() => {
    if (!image) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [image, onClose]);

  return (
    <AnimatePresence>
      {image && (
        <>
          <motion.div className="lightbox-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
          <div className="lightbox-center" onClick={onClose}>
            <motion.figure
              className="lightbox-figure"
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              transition={{ type: 'spring', stiffness: 250, damping: 24 }}
              onClick={(e) => e.stopPropagation()}
            >
              <img src={image.src} alt={image.alt || 'preview'} />
              {image.alt && <figcaption>{image.alt}</figcaption>}
            </motion.figure>
          </div>
        </>
      )}
    </AnimatePresence>
  );
}

