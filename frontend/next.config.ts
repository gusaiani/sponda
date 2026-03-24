import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  skipTrailingSlashRedirect: true,
  env: {
    NEXT_PUBLIC_GOOGLE_CLIENT_ID:
      process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ||
      "61540815310-n311ho945gmd0d0q0kcasr6msckk8m1t.apps.googleusercontent.com",
  },
};

export default nextConfig;
