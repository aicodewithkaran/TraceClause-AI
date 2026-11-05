import type { NextConfig } from "next";

const backendUrl = process.env.NEXT_PUBLIC_API_URL 
  ? new URL(process.env.NEXT_PUBLIC_API_URL).origin 
  : "http://localhost:8000";

const cspHeader = `
  default-src 'self';
  script-src 'self' 'unsafe-inline' https://checkout.razorpay.com;
  frame-src 'self' https://api.razorpay.com https://checkout.razorpay.com;
  connect-src 'self' https://api.razorpay.com https://*.supabase.co ${backendUrl};
  img-src 'self' data: https:;
  style-src 'self' 'unsafe-inline';
`.replace(/\s{2,}/g, " ").trim();

const nextConfig: NextConfig = {
  productionBrowserSourceMaps: false,
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "Content-Security-Policy-Report-Only",
            value: cspHeader,
          },
        ],
      },
    ];
  },
};

export default nextConfig;
