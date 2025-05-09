import React from 'react';
import Head from 'next/head';
import Link from 'next/link';

export default function Home() {
  return (
    <>
      <Head>
        <title>HITL ダッシュボード - Webシステム開発AIエージェントチーム</title>
        <meta name="description" content="Human-in-the-Loop ダッシュボード" />
      </Head>

      <div className="container mt-4">
        <h1 className="mb-4">HITL ダッシュボード</h1>
        
        <div className="row">
          <div className="col-md-4">
            <div className="card">
              <div className="card-header bg-purple">
                プロダクトオーナー向け
              </div>
              <div className="card-body">
                <h5 className="card-title">要求管理</h5>
                <p className="card-text">プロジェクト要求の入力・管理・追跡を行います。</p>
                <Link href="/product-owner" className="btn btn-primary">アクセス</Link>
              </div>
            </div>
          </div>
          
          <div className="col-md-4">
            <div className="card">
              <div className="card-header bg-teal">
                開発者向け
              </div>
              <div className="card-body">
                <h5 className="card-title">モニタリング＆介入</h5>
                <p className="card-text">AI開発プロセスの監視と必要時の介入を行います。</p>
                <Link href="/developer" className="btn btn-success">アクセス</Link>
              </div>
            </div>
          </div>
          
          <div className="col-md-4">
            <div className="card">
              <div className="card-header bg-orange">
                承認フロー
              </div>
              <div className="card-body">
                <h5 className="card-title">タスク承認管理</h5>
                <p className="card-text">PMとプロダクトオーナー間の承認フローを管理します。</p>
                <Link href="/approval-flow" className="btn btn-warning">アクセス</Link>
              </div>
            </div>
          </div>
        </div>
        
        <div className="row mt-4">
          <div className="col-12">
            <div className="card">
              <div className="card-header bg-info text-white">
                システム概要
              </div>
              <div className="card-body">
                <h5 className="card-title">Webシステム開発AIエージェントチーム</h5>
                <p className="card-text">
                  このシステムは、CrewAIフレームワークを基盤とし、動的かつ拡張可能なチーム構成でWebシステム開発を行うAIエージェントチームを実現します。
                  PdM、PM、デザイナー、PL、エンジニア、テスターといった役割を持つAIエージェントが協調して開発を進めます。
                </p>
                <p className="card-text">
                  Human-in-the-loop (HITL) インターフェースを通じて、プロダクトオーナー（人間）との対話、
                  開発プロセスの監視、および重要な判断ポイントでの人間の介入を可能にします。
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
} 