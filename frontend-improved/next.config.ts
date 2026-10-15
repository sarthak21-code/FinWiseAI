import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: process.env.NEXT_BUILD_DIR || ".next",
  cacheComponents: true,
  partialPrefetching: true,
};

export default nextConfig;
