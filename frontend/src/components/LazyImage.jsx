import { useState, useMemo } from 'react';

const PLACEHOLDER =
  "data:image/svg+xml;utf8," +
  "<svg xmlns='http://www.w3.org/2000/svg' width='80' height='60' viewBox='0 0 80 60'>" +
  "<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>" +
  "<stop offset='0' stop-color='%23f4efe6'/><stop offset='1' stop-color='%23efe7d9'/>" +
  "</linearGradient></defs><rect width='80' height='60' fill='url(%23g)'/></svg>";

export default function LazyImage({ src, alt, className = '', style = {}, ...rest }) {
  const [loaded, setLoaded] = useState(false);
  const merged = useMemo(
    () => ({
      backgroundImage: `url("${PLACEHOLDER}")`,
      backgroundSize: 'cover',
      backgroundPosition: 'center',
      ...style,
    }),
    [style]
  );

  return (
    <img
      src={src}
      alt={alt}
      className={`lazy-image ${loaded ? 'is-loaded' : ''} ${className}`}
      style={merged}
      loading="lazy"
      onLoad={() => setLoaded(true)}
      {...rest}
    />
  );
}

