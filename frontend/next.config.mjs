/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/proxy/:path*",
        destination: "http://127.0.0.1:8000/:path*", // The Proxy Magic
      },
    ];
  },
};

export default nextConfig;
