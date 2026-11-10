// static/config.js
// Intelligent Backend API URL configuration.
// Automatically routes to localhost:8000 during local dev (including Live Server / different ports),
// and to the live Render backend when deployed on Netlify or external hosting.
(function() {
  const hostname = (typeof window !== 'undefined' && window.location.hostname) || '';
  const port = (typeof window !== 'undefined' && window.location.port) || '';

  const isLocal = (
    hostname === 'localhost' ||
    hostname === '127.0.0.1' ||
    hostname === '' ||
    hostname === '0.0.0.0'
  );

  // If running from Live Server (:5500), Vite/Webpack (:3000, :5173), or file://:
  let localBackend = "";
  if (isLocal) {
    if (port && port !== "8000") {
      localBackend = `http://${hostname || 'localhost'}:8000`;
    } else if (!port && window.location.protocol === 'file:') {
      localBackend = "http://localhost:8000";
    }
  }

  // If hosted on Netlify or external web, connect to Render backend:
  const RENDER_BACKEND_URL = "https://agenticrms-multi-agent-orchestration-and.onrender.com";

  window.BACKEND_API_URL = window.BACKEND_API_URL || (isLocal ? localBackend : RENDER_BACKEND_URL);
})();
