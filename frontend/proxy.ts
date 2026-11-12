import { NextRequest, NextResponse } from "next/server";

// AG Studio's CDN file, pinned with SRI on the Money & Time page. Nothing else loads from a CDN.
const STUDIO_CDN = "https://cdn.jsdelivr.net/npm/ag-studio@3.1.0/";

export function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const dev = process.env.NODE_ENV === "development";
  const money = /^\/f\/[^/]+\/money$/.test(request.nextUrl.pathname);
  // Styles allow inline: React style props, Motion and AG Studio set them. Scripts never run inline without the nonce.
  const csp = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${money ? ` ${STUDIO_CDN}` : ""}${dev ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self' https://www.sandbox.paypal.com",
    "frame-ancestors 'none'",
    ...(dev ? [] : ["upgrade-insecure-requests"]),
  ].join("; ");
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);
  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("Referrer-Policy", "same-origin");
  response.headers.set("X-Content-Type-Options", "nosniff");
  return response;
}

export const config = {
  matcher: [
    {
      source: "/((?!_next/static|_next/image|static/|favicon.ico|.*\\.json$).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
