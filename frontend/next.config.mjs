const apiOrigin = process.env.API_PROXY_TARGET
  || "http://127.0.0.1:8000";
const mediaHosts = (process.env.NEXT_PUBLIC_MEDIA_HOSTS || "r2.misa.lol")
  .split(",")
  .map((host) => host.trim().toLowerCase())
  .filter(Boolean);

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  basePath: "/dashboard",
  experimental: {
    optimizePackageImports: ["lucide-react", "react-icons"],
    middlewareClientMaxBodySize: "128mb",
  },
  images: {
    remotePatterns: mediaHosts.map((hostname) => ({ protocol: "https", hostname, pathname: "/**" })),
  },
  outputFileTracingRoot: process.cwd(),
  async rewrites() {
    return {
      afterFiles: [
        {
          source: "/constellation-assets/:path*",
          destination: `${apiOrigin}/constellation-assets/:path*`,
          basePath: false,
        },
        {
          source: "/api/:path*",
          destination: `${apiOrigin}/api/:path*`,
          basePath: false,
        },
      ],
      fallback: [
        {
          source: "/:username([a-zA-Z][a-zA-Z0-9_]{2,23})",
          destination: `${apiOrigin}/:username`,
          basePath: false,
        },
      ],
    };
  },
};

export default nextConfig;
