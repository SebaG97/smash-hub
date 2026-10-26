"use client";

import { useState } from "react";

/**
 * Club logo from /smashclublogo.jpg; falls back to a CSS emblem in the same palette
 * when the file is missing, so the layout never shows a broken image.
 */
export function Logo({
  size,
  className,
}: {
  size: number;
  className?: string;
}) {
  const [missing, setMissing] = useState(false);
  if (missing)
    return (
      <span
        className={`logo-fallback ${className || ""}`}
        style={{ width: size, height: size, fontSize: size * 0.32 }}
        aria-hidden="true"
      >
        S<b>C</b>
      </span>
    );
  return (
    <img
      src="/smashclublogo.jpg"
      alt=""
      width={size}
      height={size}
      className={`logo ${className || ""}`}
      onError={() => setMissing(true)}
      // The server-rendered image can fail before React attaches onError.
      ref={(img) => {
        if (img?.complete && img.naturalWidth === 0) setMissing(true);
      }}
    />
  );
}
