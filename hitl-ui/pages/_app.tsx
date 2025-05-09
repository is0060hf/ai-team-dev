import 'bootstrap/dist/css/bootstrap.min.css';
import 'bootstrap-icons/font/bootstrap-icons.css';
import '@/styles/globals.css';
import type { AppProps } from 'next/app';
import { useEffect } from 'react';
import Layout from '@/components/Layout';

export default function App({ Component, pageProps }: AppProps) {
  // Bootstrapのスクリプトをクライアントサイドでのみ読み込む
  useEffect(() => {
    typeof document !== 'undefined' && require('bootstrap/dist/js/bootstrap.bundle.min.js');
  }, []);

  return (
    <Layout>
      <Component {...pageProps} />
    </Layout>
  );
} 