import type { NextConfig } from "next";

// Server-only: where the FastAPI backend lives (Render). Never a NEXT_PUBLIC_ variable.
const BACKEND = (process.env.BETWEEN_BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

const config: NextConfig = {
  poweredByHeader: false,
  turbopack: { rules: { "*.css": { loaders: ["@tailwindcss/turbopack"], as: "*.css" } } },
  experimental: { serverActions: { bodySizeLimit: "3mb" } }, // receipts and agreements are capped at 2 MB by the backend
  async rewrites() {
    // Same-origin pass-through for what the browser fetches itself: vendored Bryntum and AG Studio's
    // scripts and feeds. The browser's session cookie goes with them; the backend checks it as before.
    const to = (p: string) => ({ source: p, destination: `${BACKEND}${p}` });
    return {
      beforeFiles: [
        to("/static/:path*"),
        to("/f/:fid/calendar.json"),
        to("/f/:fid/money.json"),
        to("/f/:fid/money/ai"),
        to("/f/:fid/money/preview"),
        to("/f/:fid/money/expense/:file"),
      ],
      afterFiles: [],
      fallback: [],
    };
  },
};

export default config;
