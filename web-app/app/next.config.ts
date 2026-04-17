import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Produce a standalone server bundle at .next/standalone — copied into the
  // Docker image so the runtime container doesn't need node_modules. Required
  // by deploy/fly-webapp/Dockerfile.
  output: "standalone",
};

export default nextConfig;
