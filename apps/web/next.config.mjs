/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // API base for the browser (defaults to localhost:8000 in compose).
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  },
};

export default nextConfig;
