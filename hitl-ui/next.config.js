/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.API_URL || 'http://localhost:8000'}/api/:path*`,
      },
      {
        source: '/hitl/:path*',
        destination: `${process.env.API_URL || 'http://localhost:8000'}/hitl/:path*`,
      },
    ];
  },
};

module.exports = nextConfig; 