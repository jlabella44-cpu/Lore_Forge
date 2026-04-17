import type { Metadata } from "next";
import { DM_Sans } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

const font = DM_Sans({
  subsets: ["latin"],
  variable: "--font-body",
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
      <body className={`${font.variable} font-sans antialiased`}>
        <Sidebar />
        <main className="pl-56 min-h-screen">{children}</main>
      </body>
    </html>
  );
}
