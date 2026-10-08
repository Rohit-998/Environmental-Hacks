import type { NextConfig } from "next";

// Static export: the dashboard is plain HTML/JS on Amplify Hosting and talks to the API Gateway URL.
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
