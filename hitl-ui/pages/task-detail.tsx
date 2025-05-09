import React, { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import Head from 'next/head';
import { useRouter } from 'next/router';
import Link from 'next/link';
import TaskDetail, { Task, TaskComment, TaskError } from '../components/TaskDetail';

// モックデータ - 詳細なタスク情報
const MOCK_TASKS: Record<string, Task> = {
  'task-001': {
    id: 'task-001',
    title: 'ログイン機能の実装',
    description: 'ユーザー認証システムとログインフォームの実装。セキュアなパスワード管理と多要素認証のサポートを含む。',
    requestedBy: 'プロダクトオーナー',
    assignedTo: 'エンジニアA',
    status: 'in_progress',
    priority: '高',
    createdAt: '2023-10-15T10:30:00',
    dueDate: '2023-10-30T18:00:00',
    tags: ['認証', 'セキュリティ', 'UI', 'フロントエンド'],
    progress: 65,
    comments: [
      { author: 'PM', content: '要件を明確にする必要があります', timestamp: '2023-10-16T09:15:00' },
      { author: 'デザイナー', content: 'モックアップを作成しました', timestamp: '2023-10-17T14:20:00' },
      { author: 'エンジニアA', content: 'ログインフォームの基本実装が完了しました', timestamp: '2023-10-20T16:35:00' },
      { author: 'PL', content: 'コードレビュー完了。セキュリティ対策を強化してください', timestamp: '2023-10-21T11:40:00' },
      { author: 'エンジニアA', content: 'セキュリティ対策強化中。多要素認証の実装を進めています', timestamp: '2023-10-22T15:10:00' }
    ],
    errors: [
      {
        id: 'err-001-1',
        message: 'パスワードハッシュ関数の脆弱性が見つかりました',
        severity: 'high',
        timestamp: '2023-10-21T10:45:00',
        resolved: true
      },
      {
        id: 'err-001-2',
        message: 'セッション管理に関するセキュリティ問題が検出されました',
        severity: 'medium',
        timestamp: '2023-10-22T09:30:00',
        resolved: false
      }
    ]
  },
  'task-002': {
    id: 'task-002',
    title: 'ダッシュボード画面の設計',
    description: 'ユーザー向けダッシュボードの設計と実装。データ可視化、パフォーマンス指標表示、カスタマイズ可能なウィジェットを含む。',
    requestedBy: 'プロダクトオーナー',
    assignedTo: 'デザイナー',
    status: 'approval_pending',
    priority: '中',
    createdAt: '2023-10-16T15:45:00',
    dueDate: '2023-11-05T18:00:00',
    tags: ['UI/UX', 'ダッシュボード', 'データ可視化', 'フロントエンド'],
    progress: 85,
    comments: [
      { author: 'PM', content: 'ユーザーのニーズを考慮した設計を行ってください', timestamp: '2023-10-17T11:30:00' },
      { author: 'デザイナー', content: '初期デザイン案を作成しました', timestamp: '2023-10-18T14:25:00' },
      { author: 'PL', content: 'デザインレビュー完了。一部修正が必要です', timestamp: '2023-10-19T10:15:00' },
      { author: 'デザイナー', content: 'レビューを反映した修正版を作成しました', timestamp: '2023-10-20T16:40:00' },
      { author: 'PM', content: '修正版を確認しました。承認プロセスに進めてください', timestamp: '2023-10-21T09:30:00' }
    ]
  },
  'task-003': {
    id: 'task-003',
    title: 'API連携機能の実装',
    description: '外部APIとの連携機能の実装。認証、データ変換、エラーハンドリングを含む。',
    requestedBy: 'PM',
    assignedTo: 'エンジニアB',
    status: 'completed',
    priority: '高',
    createdAt: '2023-10-14T09:00:00',
    dueDate: '2023-10-28T18:00:00',
    tags: ['API', 'バックエンド', '外部連携', 'インテグレーション'],
    progress: 100,
    comments: [
      { author: 'エンジニアB', content: 'API連携のスケルトンコードを実装しました', timestamp: '2023-10-15T14:30:00' },
      { author: 'PL', content: 'コードレビュー完了。認証周りを改善してください', timestamp: '2023-10-16T11:20:00' },
      { author: 'エンジニアB', content: '認証モジュールを改善しました', timestamp: '2023-10-18T15:45:00' },
      { author: 'テスター', content: 'テスト完了。すべてのテストケースが通過しました', timestamp: '2023-10-20T13:10:00' },
      { author: 'PL', content: '最終コードレビュー完了。問題なし', timestamp: '2023-10-21T10:30:00' },
      { author: 'PM', content: 'タスク完了を確認しました', timestamp: '2023-10-22T09:15:00' }
    ],
    errors: [
      {
        id: 'err-003-1',
        message: 'API認証トークンの有効期限切れ処理に不具合があります',
        severity: 'medium',
        timestamp: '2023-10-17T11:25:00',
        resolved: true
      }
    ]
  },
  'task-004': {
    id: 'task-004',
    title: 'レポート出力機能の追加',
    description: 'PDF形式でのレポート出力機能の実装。カスタマイズ可能なテンプレート、チャート/グラフの埋め込み、ページネーションを含む。',
    requestedBy: 'PM',
    assignedTo: 'エンジニアC',
    status: 'error',
    priority: '低',
    createdAt: '2023-10-10T13:20:00',
    dueDate: '2023-10-25T18:00:00',
    tags: ['PDF', 'レポート', 'データエクスポート', 'バックエンド'],
    progress: 45,
    comments: [
      { author: 'エンジニアC', content: 'レポートテンプレートエンジンの選定中です', timestamp: '2023-10-12T14:45:00' },
      { author: 'PL', content: 'PDFライブラリはpdfkitを使用してください', timestamp: '2023-10-13T10:30:00' },
      { author: 'エンジニアC', content: 'pdfkitを使用してベースコードを実装しました', timestamp: '2023-10-17T16:20:00' },
      { author: 'エンジニアC', content: 'グラフ埋め込み機能の実装中にエラーが発生しています', timestamp: '2023-10-19T15:10:00' },
      { author: 'PL', content: 'エラー状況を確認中です', timestamp: '2023-10-20T11:05:00' }
    ],
    errors: [
      {
        id: 'err-004-1',
        message: 'グラフレンダリング時にメモリリークが発生しています',
        severity: 'high',
        timestamp: '2023-10-19T15:05:00',
        resolved: false
      },
      {
        id: 'err-004-2',
        message: 'PDFサイズが制限を超えるとクラッシュする問題があります',
        severity: 'critical',
        timestamp: '2023-10-20T10:30:00',
        resolved: false
      }
    ]
  },
  'task-005': {
    id: 'task-005',
    title: 'パフォーマンス最適化',
    description: 'アプリケーション全体のパフォーマンス最適化。アセット最適化、データベースクエリ改善、キャッシング戦略の実装を含む。',
    requestedBy: 'PM',
    assignedTo: 'エンジニアA',
    status: 'in_progress',
    priority: '中',
    createdAt: '2023-10-18T11:10:00',
    dueDate: '2023-11-10T18:00:00',
    tags: ['パフォーマンス', '最適化', 'UX', 'バックエンド', 'フロントエンド'],
    progress: 35,
    comments: [
      { author: 'PL', content: '特にデータ読み込み部分の最適化が必要です', timestamp: '2023-10-19T09:30:00' },
      { author: 'エンジニアA', content: 'パフォーマンス監査を実施し、ボトルネックを特定しました', timestamp: '2023-10-20T14:20:00' },
      { author: 'エンジニアA', content: 'フロントエンドアセットの最適化が完了しました', timestamp: '2023-10-22T16:15:00' },
      { author: 'PL', content: 'フロントエンド最適化の効果を確認。データベースクエリの最適化を進めてください', timestamp: '2023-10-23T10:45:00' }
    ]
  }
};

const TaskDetailPage: React.FC = () => {
  const router = useRouter();
  const { id } = router.query;
  const [task, setTask] = useState<Task | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;

    // 実際はここでAPIリクエストを行う
    // モックデータを使用
    setLoading(true);
    
    setTimeout(() => {
      if (typeof id === 'string' && MOCK_TASKS[id]) {
        setTask(MOCK_TASKS[id]);
        setError(null);
      } else {
        setError('タスクが見つかりませんでした');
        setTask(null);
      }
      setLoading(false);
    }, 500); // 読み込み感のための遅延
  }, [id]);

  // フィードバック追加処理
  const handleAddFeedback = (taskId: string, content: string) => {
    if (!task) return;
    
    const newComment: TaskComment = {
      author: '開発者',
      content,
      timestamp: new Date().toISOString()
    };
    
    setTask({
      ...task,
      comments: [...task.comments, newComment]
    });
    
    // 実際はここでAPIリクエストを行う
    console.log(`タスク ${taskId} へのフィードバック: ${content}`);
  };

  return (
    <Layout>
      <Head>
        <title>タスク詳細 - Webシステム開発AIエージェントチーム</title>
        <meta name="description" content="タスク詳細情報と履歴" />
      </Head>

      <div className="container mt-4">
        <div className="d-flex justify-content-between align-items-center mb-4">
          <h1>タスク詳細</h1>
          <div>
            <Link href="/developer" className="btn btn-outline-secondary me-2">
              開発者ダッシュボードへ戻る
            </Link>
          </div>
        </div>

        {loading ? (
          <div className="text-center my-5">
            <div className="spinner-border text-primary" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
            <p className="mt-2">タスク情報を読み込み中...</p>
          </div>
        ) : error ? (
          <div className="alert alert-danger">
            <h4 className="alert-heading">エラー</h4>
            <p>{error}</p>
            <hr />
            <p className="mb-0">
              <Link href="/developer" className="alert-link">
                開発者ダッシュボードへ戻る
              </Link>
            </p>
          </div>
        ) : task ? (
          <div className="card">
            <div className="card-body">
              <TaskDetail 
                task={task} 
                onAddFeedback={handleAddFeedback}
                showActions={true}
              />
            </div>
          </div>
        ) : null}
      </div>
    </Layout>
  );
};

export default TaskDetailPage; 