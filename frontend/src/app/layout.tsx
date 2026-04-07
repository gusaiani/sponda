import { headers } from "next/headers";
import "./globals.css";

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const headersList = await headers();
  const locale = headersList.get("x-locale") || "en";
  const htmlLang = locale === "pt" ? "pt-BR" : "en";

  return (
    <html lang={htmlLang}>
      <head>
        <link rel="icon" type="image/svg+xml" href={process.env.NODE_ENV === "development" ? "/favicon-dev.svg" : "/favicon.svg"} />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Source+Code+Pro:wght@300;400&display=swap"
          rel="stylesheet"
        />
        <link rel="preload" href="/fonts/Satoshi-Medium.woff2" as="font" type="font/woff2" crossOrigin="anonymous" />
      </head>
      <body style={{ margin: 0 }}>
        {children}
      </body>
    </html>
  );
}
