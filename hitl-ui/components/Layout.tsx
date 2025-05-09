import React, { ReactNode } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useState, useEffect } from 'react';

type LayoutProps = {
  children: ReactNode;
};

const Layout = ({ children }: LayoutProps) => {
  const router = useRouter();
  const [username, setUsername] = useState<string>('ユーザー');
  const [currentTime, setCurrentTime] = useState<string>(
    new Date().toLocaleString('ja-JP')
  );

  // ユーザー情報の取得（実際には認証APIとの連携が必要）
  useEffect(() => {
    // ダミーのユーザー情報
    setUsername('開発者');
    
    // 1分ごとに時間を更新
    const timer = setInterval(() => {
      setCurrentTime(new Date().toLocaleString('ja-JP'));
    }, 60000);
    
    return () => clearInterval(timer);
  }, []);

  // 現在のパスに基づいてナビゲーションアイテムのアクティブ状態を決定
  const isActive = (path: string) => {
    return router.pathname === path ? 'active' : '';
  };

  return (
    <>
      <Head>
        <title>Webシステム開発AIエージェントチーム - HITL UI</title>
        <meta name="description" content="Human-in-the-Loop インターフェース" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      <nav className="navbar navbar-expand-lg navbar-dark">
        <div className="container">
          <Link href="/" className="navbar-brand">
            Webシステム開発AIエージェントチーム
          </Link>
          <button
            className="navbar-toggler"
            type="button"
            data-bs-toggle="collapse"
            data-bs-target="#navbarNav"
          >
            <span className="navbar-toggler-icon"></span>
          </button>
          <div className="collapse navbar-collapse" id="navbarNav">
            <ul className="navbar-nav me-auto">
              <li className="nav-item">
                <Link href="/" className={`nav-link ${isActive('/')}`}>
                  ダッシュボード
                </Link>
              </li>
              <li className="nav-item">
                <Link href="/product-owner" className={`nav-link ${isActive('/product-owner')}`}>
                  プロダクトオーナー
                </Link>
              </li>
              <li className="nav-item">
                <Link href="/developer" className={`nav-link ${isActive('/developer')}`}>
                  開発者
                </Link>
              </li>
              <li className="nav-item">
                <Link href="/approval-flow" className={`nav-link ${isActive('/approval-flow')}`}>
                  承認フロー
                </Link>
              </li>
            </ul>
            <span className="navbar-text">
              ユーザー: {username} | {currentTime}
            </span>
          </div>
        </div>
      </nav>

      <main>{children}</main>

      <footer className="bg-dark text-white text-center py-3 mt-5">
        <div className="container">
          <p className="mb-0">© 2023 Webシステム開発AIエージェントチーム</p>
        </div>
      </footer>
    </>
  );
};

export default Layout; 