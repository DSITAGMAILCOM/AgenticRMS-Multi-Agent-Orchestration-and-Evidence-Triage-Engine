// static/config.js
// Intelligent Backend API URL configuration.
// Automatically routes to localhost during local dev, and to the live Render backend when deployed on Netlify.
(function() {
  const isLocal = typeof window !== 'undefined' && (
    window.location.hostname === 'localhost' ||
    window.location.hostname === '127.0.0.1' ||
    window.location.hostname === ''
  );

  // If hosted on Netlify or external web, connect to Render backend:
  const RENDER_BACKEND_URL = "https://agenticrms-multi-agent-orchestration-and.onrender.com";

  window.BACKEND_API_URL = window.BACKEND_API_URL || (isLocal ? "" : RENDER_BACKEND_URL);
})();
