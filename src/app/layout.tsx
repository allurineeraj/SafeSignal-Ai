import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'SafeSignalAI | HSE Intelligence',
  description: 'AI-powered safety reporting platform for industrial workers',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>
        <div className="min-h-screen flex flex-col bg-slate-900 text-slate-100">
          <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-md sticky top-0 z-50">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-2xl">🛡️</span>
                <span className="font-bold text-xl tracking-tight bg-gradient-to-r from-blue-400 to-emerald-400 bg-clip-text text-transparent">
                  SafeSignalAI
                </span>
              </div>
              <nav className="hidden md:flex gap-6 text-sm font-medium">
                <a href="/" className="hover:text-blue-400 transition-colors">Worker Portal</a>
                <a href="/hse" className="hover:text-blue-400 transition-colors">HSE Queue</a>
                <a href="/analytics" className="hover:text-blue-400 transition-colors">Analytics</a>
              </nav>
            </div>
          </header>
          <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
