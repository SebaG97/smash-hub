"use client";
import { useEffect, useState } from "react";

export function BackendStatus() {
  const [status, setStatus] = useState("Comprobando conexión…");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 5000);
    let active = true;
    const api = (process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(
      /\/$/,
      "",
    );
    fetch(`${api}/health/ready`, {
      signal: controller.signal,
      cache: "no-store",
    })
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok || body.status !== "ready")
          throw new Error("Unavailable");
        if (active) setStatus("Backend disponible");
      })
      .catch(() => {
        if (active) setStatus("Backend no disponible");
      })
      .finally(() => clearTimeout(timer));
    return () => {
      active = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, [attempt]);
  return (
    <div className="status">
      <span className="status-dot" aria-hidden="true" />
      <span role="status">{status}</span>
      <button
        onClick={() => {
          setStatus("Comprobando conexión…");
          setAttempt(attempt + 1);
        }}
        aria-label="Volver a comprobar el backend"
      >
        Reintentar ↻
      </button>
    </div>
  );
}
