import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Intellect RAG Assistant",
  description: "Enterprise-grade RAG pipeline",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // Defaulting to dark mode to match the requested ChatGPT/Gemini style
    <html lang="en" className="dark">
      <body className={`${inter.className} antialiased h-screen overflow-hidden`}>
        {children}
      </body>
    </html>
  );
}
