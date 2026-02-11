/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/v1/:path*',
        destination: 'http://127.0.0.1:8000/v1/:path*', // Proxy to Backend
      },
      {
        source: '/rag/:path*',
        destination: 'http://127.0.0.1:8000/rag/:path*', // Proxy RAG endpoints
      },
    ]
  },
};

export default nextConfig;
