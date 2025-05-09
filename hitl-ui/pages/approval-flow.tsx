import React, { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import Head from 'next/head';
import Link from 'next/link';
import { Task, TaskComment, STATUS_LABELS, STATUS_BADGE_CLASSES } from '../components/TaskDetail';

// モックデータ
const MOCK_APPROVAL_TASKS: Task[] = [
  {
    id: 'task-001',
    title: 'ログイン機能の実装',
    description: 'ユーザー認証システムとログインフォームの実装',
    requestedBy: 'プロダクトオーナー',
    assignedTo: 'エンジニアA',
    status: 'approval_pending',
    priority: '高',
    createdAt: '2023-10-15T10:30:00',
    dueDate: '2023-10-30T18:00:00',
    tags: ['認証', 'セキュリティ', 'UI'],
    comments: [
      { author: 'PM', content: '要件を明確にする必要があります', timestamp: '2023-10-16T09:15:00' },
      { author: 'デザイナー', content: 'モックアップを作成しました', timestamp: '2023-10-17T14:20:00' }
    ]
  },
  {
    id: 'task-002',
    title: 'ダッシュボード画面の設計',
    description: 'ユーザー向けダッシュボードの設計と実装',
    requestedBy: 'プロダクトオーナー',
    assignedTo: 'デザイナー',
    status: 'approval_pending',
    priority: '中',
    createdAt: '2023-10-16T15:45:00',
    dueDate: '2023-11-05T18:00:00',
    tags: ['UI/UX', 'ダッシュボード', 'データ可視化'],
    comments: [
      { author: 'PM', content: 'ユーザーのニーズを考慮した設計を行ってください', timestamp: '2023-10-17T11:30:00' }
    ]
  },
  {
    id: 'task-003',
    title: 'API連携機能の実装',
    description: '外部APIとの連携機能の実装',
    requestedBy: 'PM',
    assignedTo: 'エンジニアB',
    status: 'approved',
    priority: '高',
    createdAt: '2023-10-14T09:00:00',
    dueDate: '2023-10-28T18:00:00',
    tags: ['API', 'バックエンド', '外部連携'],
    comments: [
      { author: 'プロダクトオーナー', content: '承認しました。予定通り進めてください', timestamp: '2023-10-14T16:45:00' }
    ]
  },
  {
    id: 'task-004',
    title: 'レポート出力機能の追加',
    description: 'PDF形式でのレポート出力機能の実装',
    requestedBy: 'PM',
    assignedTo: 'エンジニアC',
    status: 'rejected',
    priority: '低',
    createdAt: '2023-10-10T13:20:00',
    dueDate: '2023-10-25T18:00:00',
    tags: ['PDF', 'レポート', 'データエクスポート'],
    comments: [
      { author: 'プロダクトオーナー', content: '現時点では優先度が低いため、次期リリースへ延期します', timestamp: '2023-10-11T10:15:00' }
    ]
  },
  {
    id: 'task-005',
    title: 'パフォーマンス最適化',
    description: 'アプリケーション全体のパフォーマンス最適化',
    requestedBy: 'PM',
    assignedTo: 'エンジニアA',
    status: 'approval_pending',
    priority: '中',
    createdAt: '2023-10-18T11:10:00',
    dueDate: '2023-11-10T18:00:00',
    tags: ['パフォーマンス', '最適化', 'UX'],
    comments: [
      { author: 'PL', content: '特にデータ読み込み部分の最適化が必要です', timestamp: '2023-10-19T09:30:00' }
    ]
  }
];

interface ApprovalStats {
  pending: number;
  approved: number;
  rejected: number;
}

export default function ApprovalFlow() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedTask, setSelectedTask] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>('all');
  const [approvalStats, setApprovalStats] = useState<ApprovalStats>({
    pending: 0,
    approved: 0,
    rejected: 0
  });

  // タスクデータの取得（実際はAPIからデータを取得）
  useEffect(() => {
    // モックデータをセット
    setTasks(MOCK_APPROVAL_TASKS);
    
    // 統計情報の計算
    const stats = MOCK_APPROVAL_TASKS.reduce((acc, task) => {
      if (task.status === 'approval_pending') acc.pending++;
      if (task.status === 'approved') acc.approved++;
      if (task.status === 'rejected') acc.rejected++;
      return acc;
    }, { pending: 0, approved: 0, rejected: 0 });
    
    setApprovalStats(stats);
  }, []);

  // タスクの承認
  const handleApprove = (taskId: string, comment = '') => {
    setTasks(prevTasks => 
      prevTasks.map(task => 
        task.id === taskId 
          ? { 
              ...task, 
              status: 'approved', 
              comments: comment 
                ? [...task.comments, { author: 'プロダクトオーナー', content: `承認: ${comment}`, timestamp: new Date().toISOString() }]
                : task.comments
            }
          : task
      )
    );
    setSelectedTask(null);
    
    // 統計情報の更新
    setApprovalStats(prev => ({
      ...prev,
      pending: prev.pending - 1,
      approved: prev.approved + 1
    }));
  };

  // タスクの却下
  const handleReject = (taskId: string, comment = '') => {
    setTasks(prevTasks => 
      prevTasks.map(task => 
        task.id === taskId 
          ? { 
              ...task, 
              status: 'rejected',
              comments: comment 
                ? [...task.comments, { author: 'プロダクトオーナー', content: `却下: ${comment}`, timestamp: new Date().toISOString() }]
                : task.comments
            }
          : task
      )
    );
    setSelectedTask(null);
    
    // 統計情報の更新
    setApprovalStats(prev => ({
      ...prev,
      pending: prev.pending - 1,
      rejected: prev.rejected + 1
    }));
  };

  // フィルタリングされたタスクリスト
  const filteredTasks = tasks.filter(task => {
    if (filter === 'all') return true;
    return task.status === filter;
  });

  // タスク詳細モーダル
  const renderTaskDetailModal = () => {
    if (!selectedTask) return null;
    
    const task = tasks.find(t => t.id === selectedTask);
    if (!task) return null;
    
    return (
      <div className="modal show d-block" tabIndex="-1" role="dialog">
        <div className="modal-dialog modal-lg">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">タスク詳細: {task.title}</h5>
              <button type="button" className="btn-close" onClick={() => setSelectedTask(null)}></button>
            </div>
            <div className="modal-body">
              <div className="row mb-3">
                <div className="col">
                  <h6>説明</h6>
                  <p>{task.description}</p>
                </div>
              </div>
              
              <div className="row mb-3">
                <div className="col-md-6">
                  <h6>基本情報</h6>
                  <table className="table table-sm">
                    <tbody>
                      <tr>
                        <th scope="row">ステータス</th>
                        <td><span className={STATUS_BADGE_CLASSES[task.status]}>{STATUS_LABELS[task.status]}</span></td>
                      </tr>
                      <tr>
                        <th scope="row">優先度</th>
                        <td>{task.priority}</td>
                      </tr>
                      <tr>
                        <th scope="row">作成者</th>
                        <td>{task.requestedBy}</td>
                      </tr>
                      <tr>
                        <th scope="row">担当者</th>
                        <td>{task.assignedTo}</td>
                      </tr>
                      <tr>
                        <th scope="row">作成日</th>
                        <td>{new Date(task.createdAt).toLocaleString('ja-JP')}</td>
                      </tr>
                      <tr>
                        <th scope="row">期限</th>
                        <td>{new Date(task.dueDate).toLocaleString('ja-JP')}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                
                <div className="col-md-6">
                  <h6>タグ</h6>
                  <div>
                    {task.tags.map(tag => (
                      <span key={tag} className="badge bg-secondary me-1 mb-1">{tag}</span>
                    ))}
                  </div>
                  
                  <h6 className="mt-3">コメント履歴</h6>
                  <div className="timeline">
                    {task.comments.map((comment, index) => (
                      <div key={index} className="timeline-item">
                        <div className="timeline-badge">{comment.author.charAt(0)}</div>
                        <div className="timeline-content">
                          <div className="d-flex justify-content-between">
                            <span className="fw-bold">{comment.author}</span>
                            <small className="text-muted">{new Date(comment.timestamp).toLocaleString('ja-JP')}</small>
                          </div>
                          <p>{comment.content}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              
              {task.status === 'approval_pending' && (
                <div className="row">
                  <div className="col-12">
                    <h6>承認/却下コメント</h6>
                    <textarea id="approvalComment" className="form-control mb-3" rows={3} placeholder="コメントを入力してください（任意）"></textarea>
                  </div>
                </div>
              )}
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn-secondary" onClick={() => setSelectedTask(null)}>閉じる</button>
              
              {task.status === 'approval_pending' && (
                <>
                  <button 
                    type="button" 
                    className="btn btn-danger" 
                    onClick={() => {
                      const commentInput = document.getElementById('approvalComment') as HTMLTextAreaElement;
                      handleReject(task.id, commentInput?.value || '');
                    }}
                  >
                    却下
                  </button>
                  <button 
                    type="button" 
                    className="btn btn-success" 
                    onClick={() => {
                      const commentInput = document.getElementById('approvalComment') as HTMLTextAreaElement;
                      handleApprove(task.id, commentInput?.value || '');
                    }}
                  >
                    承認
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <Layout>
      <Head>
        <title>承認フロー管理 - Webシステム開発AIエージェントチーム</title>
        <meta name="description" content="タスク承認フロー管理インターフェース" />
      </Head>

      <div className="container mt-4">
        <h1 className="mb-4">承認フロー管理</h1>
        
        {/* 統計情報カード */}
        <div className="row mb-4">
          <div className="col-md-4">
            <div className="card bg-light">
              <div className="card-body">
                <h5 className="card-title">承認待ち</h5>
                <p className="card-text display-4">{approvalStats.pending}</p>
              </div>
            </div>
          </div>
          <div className="col-md-4">
            <div className="card bg-light">
              <div className="card-body">
                <h5 className="card-title">承認済み</h5>
                <p className="card-text display-4">{approvalStats.approved}</p>
              </div>
            </div>
          </div>
          <div className="col-md-4">
            <div className="card bg-light">
              <div className="card-body">
                <h5 className="card-title">却下</h5>
                <p className="card-text display-4">{approvalStats.rejected}</p>
              </div>
            </div>
          </div>
        </div>
        
        {/* フィルタコントロール */}
        <div className="row mb-4">
          <div className="col">
            <div className="btn-group" role="group">
              <button 
                type="button" 
                className={`btn ${filter === 'all' ? 'btn-primary' : 'btn-outline-primary'}`}
                onClick={() => setFilter('all')}
              >
                すべて
              </button>
              <button 
                type="button" 
                className={`btn ${filter === 'approval_pending' ? 'btn-warning' : 'btn-outline-warning'}`}
                onClick={() => setFilter('approval_pending')}
              >
                承認待ち
              </button>
              <button 
                type="button" 
                className={`btn ${filter === 'approved' ? 'btn-success' : 'btn-outline-success'}`}
                onClick={() => setFilter('approved')}
              >
                承認済み
              </button>
              <button 
                type="button" 
                className={`btn ${filter === 'rejected' ? 'btn-danger' : 'btn-outline-danger'}`}
                onClick={() => setFilter('rejected')}
              >
                却下
              </button>
            </div>
          </div>
        </div>
        
        {/* タスク一覧 */}
        <div className="row">
          <div className="col">
            <div className="card">
              <div className="card-header bg-orange text-white">
                タスク一覧
              </div>
              <div className="card-body">
                <div className="table-responsive">
                  <table className="table table-hover">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>タイトル</th>
                        <th>担当者</th>
                        <th>優先度</th>
                        <th>作成日</th>
                        <th>期限</th>
                        <th>ステータス</th>
                        <th>アクション</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredTasks.map(task => (
                        <tr key={task.id} className="task-row">
                          <td>{task.id}</td>
                          <td>{task.title}</td>
                          <td>{task.assignedTo}</td>
                          <td>{task.priority}</td>
                          <td>{new Date(task.createdAt).toLocaleDateString('ja-JP')}</td>
                          <td>{new Date(task.dueDate).toLocaleDateString('ja-JP')}</td>
                          <td>
                            <span className={STATUS_BADGE_CLASSES[task.status]}>
                              {STATUS_LABELS[task.status]}
                            </span>
                          </td>
                          <td>
                            <button 
                              className="btn btn-sm btn-outline-primary" 
                              onClick={() => setSelectedTask(task.id)}
                            >
                              詳細
                            </button>
                            
                            {task.status === 'approval_pending' && (
                              <>
                                <button 
                                  className="btn btn-sm btn-outline-success ms-1" 
                                  onClick={() => handleApprove(task.id)}
                                >
                                  承認
                                </button>
                                <button 
                                  className="btn btn-sm btn-outline-danger ms-1" 
                                  onClick={() => handleReject(task.id)}
                                >
                                  却下
                                </button>
                              </>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      {/* タスク詳細モーダル */}
      {renderTaskDetailModal()}
      
      {/* モーダル表示時の背景オーバーレイ */}
      {selectedTask && (
        <div className="modal-backdrop fade show"></div>
      )}
    </Layout>
  );
} 