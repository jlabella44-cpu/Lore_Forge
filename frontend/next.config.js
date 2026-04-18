/** @type {import('next').NextConfig} */
// `output: 'export'` emits a fully static site to `out/` that Tauri bundles
// and serves without a Node runtime. The implications:
//   - Dynamic route segments require `generateStaticParams`, so detail
//     pages are modelled as search-param routes instead of `[id]`.
//   - `next/image` optimisation needs the server, so we opt out.
//   - Trailing slashes make the folder-per-route layout behave predictably
//     when Tauri's asset protocol serves `out/` directly.
const nextConfig = {
  output: "export",
  reactStrictMode: true,
  trailingSlash: true,
  images: { unoptimized: true },
};

module.exports = nextConfig;
