import type { Metadata } from "next";
import { Spectral, JetBrains_Mono } from "next/font/google";
import { GeistSans } from "geist/font/sans";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

const serif = Spectral({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600"],
  variable: "--font-serif",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "Lore Forge",
  description: "Automated book-content pipeline",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${serif.variable} ${GeistSans.variable} ${mono.variable} font-sans antialiased`}
        style={
          {
            // Alias the geist package's native variable to the
            // design-system's --font-sans so globals.css stays clean.
            "--font-sans": "var(--font-geist-sans)",
          } as React.CSSProperties
        }
      >
        <div className="relative z-[1] grid min-h-screen grid-cols-[240px_1fr]">
          <Sidebar />
          <main className="relative min-h-screen overflow-x-hidden">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
