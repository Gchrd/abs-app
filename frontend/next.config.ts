import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'standalone',
  productionBrowserSourceMaps: false, // Disable source maps to save memory and CPU during Docker build
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://backend:8000/:path*', // Proxy to Backend container
      },
    ];
  },
};

export default nextConfig;
