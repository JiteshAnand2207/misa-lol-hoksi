const apiOrigin = process.env.API_PROXY_TARGET
  || "http://127.0.0.1:8000";
const basePath = process.env.MISA_NEXT_ROOT_BASE_PATH === "true" ? "" : "/dashboard";
const mediaHosts = (process.env.NEXT_PUBLIC_MEDIA_HOSTS || "r2.misa.lol")
  .split(",")
  .map((host) => host.trim().toLowerCase())
  .filter(Boolean);

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  basePath,
  experimental: {
    optimizePackageImports: ["lucide-react", "react-icons"],
    middlewareClientMaxBodySize: "128mb",
  },
  images: {
    remotePatterns: mediaHosts.map((hostname) => ({ protocol: "https", hostname, pathname: "/**" })),
  },
  outputFileTracingRoot: process.cwd(),
  async rewrites() {
    const nativeRollout = process.env.MISA_NEXT_CORE_ROLLOUT === "true";
    return {
      afterFiles: nativeRollout
        ? [
            {
              source: "/constellation-assets/:path*",
              destination: `${apiOrigin}/constellation-assets/:path*`,
              basePath: false,
            },
          ]
        : [
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
          destination: nativeRollout ? "/p/:username" : `${apiOrigin}/:username`,
        },
      ],
    };
  },
};

export default nextConfig;
