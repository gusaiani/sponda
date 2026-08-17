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
  {
    rules: {
      /**
       * Every `<img>` in this app is a company logo or a user avatar: 14px to
       * 40px, sized by a CSS class, with an `onError` handler that hides the
       * element or swaps in a fallback. They come from `/api/logos/<SYM>.png`,
       * a Django proxy that already normalises and caches them.
       *
       * `next/image` would be a downgrade here. It wants explicit width and
       * height (or `fill`), so 18 call sites would have to hardcode dimensions
       * their stylesheets currently own; its error handling does not map onto
       * the hide-or-swap fallback the logo pattern depends on; and it would put
       * a second image pipeline in front of a 14px PNG that is already proxied.
       * None of these is an LCP image, which is what the rule exists to protect.
       *
       * Turn this back on the day a real content image lands — a hero, a chart
       * export, an article illustration. For icons it is noise.
       */
      "@next/next/no-img-element": "off",

      /**
       * Written for the Pages Router: it warns that a font link outside
       * `pages/_document.js` "will only load for a single page". There is no
       * `pages/` directory here. The link lives in the App Router root layout,
       * which wraps every route, so the thing the rule is protecting against
       * cannot happen.
       *
       * Self-hosting via `next/font/google` would still be an improvement —
       * it drops a third-party round trip on first paint — but that is a
       * performance change to make deliberately, not a lint fix.
       */
      "@next/next/no-page-custom-font": "off",

      /**
       * A leading underscore is the codebase's existing signal for a binding
       * that is deliberately unused, e.g. `_omitted` when destructuring a
       * field out of a fixture. Honour it instead of forcing the name away.
       */
      "@typescript-eslint/no-unused-vars": ["warn", {
        argsIgnorePattern: "^_",
        varsIgnorePattern: "^_",
        caughtErrorsIgnorePattern: "^_",
        destructuredArrayIgnorePattern: "^_",
      }],
    },
  },
];
