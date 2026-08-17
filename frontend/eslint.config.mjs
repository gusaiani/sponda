import coreWebVitals from "eslint-config-next/core-web-vitals";
import typescript from "eslint-config-next/typescript";

export default [
  {
    // Build output and retired code. `dist/` is the old Vite bundle that
    // Django still serves as a fallback shell; nothing in it is authored here.
    ignores: [
      ".next/**",
      "dist/**",
      "node_modules/**",
      "next-env.d.ts",
      "public/**",
    ],
  },
  ...coreWebVitals,
  ...typescript,
];
