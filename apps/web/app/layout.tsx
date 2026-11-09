import type { Metadata } from "next";
import { Bricolage_Grotesque } from "next/font/google";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";

const display = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-bricolage",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Thesis",
  description: "Open-source VC due diligence",
};

/** Apply saved theme before first paint so sidenav/shell tokens track correctly. */
const themeBoot = `(function(){try{var s=localStorage.getItem('thesis-theme');var d=window.matchMedia('(prefers-color-scheme: dark)').matches;var t=(s==='dark'||s==='light')?s:(d?'dark':'light');var r=document.documentElement;r.dataset.theme=t;r.classList.add(t==='dark'?'t-dark':'t-light');r.classList.remove(t==='dark'?'t-light':'t-dark');r.style.colorScheme=t;}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${GeistSans.variable} ${GeistMono.variable} ${display.variable} t-light`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBoot }} />
      </head>
      <body
        className={GeistSans.className}
        style={
          {
            ["--font-sans" as string]: "var(--font-geist-sans)",
            ["--font-mono" as string]: "var(--font-geist-mono)",
            ["--font-display" as string]: "var(--font-bricolage)",
          } as React.CSSProperties
        }
      >
        {children}
      </body>
    </html>
  );
}
