import React, { useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';

// ダミーのタスクデータ
const dummyActiveTasks = [
  {
    task_id: 'task-002',
    recipient: 'エンジニア',
    task_type: 'コード実装',
    description: 'データ可視化ダッシュボードのフロントエンド実装',
    status: 'in_progress',
    progress: 0.65,
    created_at: '2023-10-31T09:15:00',
  },
  {
    task_id: 'task-004',
    recipient: 'テスター',
    task_type: 'テスト実行',
    description: 'ログイン機能の統合テスト',
    status: 'waiting_info',
    progress: 0.3,
    created_at: '2023-11-02T11:20:00',
  },
  {
    task_id: 'task-005',
    recipient: 'PL',
    task_type: '設計レビュー',
    description: 'APIエンドポイント設計のレビュー',
    status: 'blocked',
    progress: 0.1,
    created_at: '2023-11-03T14:45:00',
  }
];

// ダミーのエラーデータ
const dummyErrorHistory = [
  {
    task_id: 'task-002',
    category: 'API_ERROR',
    severity: 'HIGH',
    message: '外部API呼び出し中にタイムアウトが発生しました。',
    timestamp: '2023-11-01T15:23:45',
    recovery_attempts: 3,
    max_retries: 3,
    resolved: true
  },
  {
    task_id: 'task-005',
    category: 'DEPENDENCY_ERROR',
    severity: 'CRITICAL',
    message: '必要なライブラリの互換性問題が発生しました。',
    timestamp: '2023-11-03T14:50:22',
    recovery_attempts: 1,
    max_retries: 3,
    resolved: false
  }
];

export default function Developer() {
  const router = useRouter();
  const [activeTasks, setActiveTasks] = useState(dummyActiveTasks);
  const [errorHistory, setErrorHistory] = useState(dummyErrorHistory);
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [currentTab, setCurrentTab] = useState('active-tasks');

  // タスク検索フィルター
  const filteredTasks = activeTasks.filter(task => {
    const textMatch = 
      task.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      task.task_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      task.recipient.toLowerCase().includes(searchTerm.toLowerCase()) ||
      task.task_type.toLowerCase().includes(searchTerm.toLowerCase());
    
    const statusMatch = statusFilter === 'all' || task.status === statusFilter;
    
    return textMatch && statusMatch;
  });

  // ステータスフィルター変更ハンドラ
  const handleStatusFilterChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setStatusFilter(e.target.value);
  };

  // 検索ハンドラ
  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchTerm(e.target.value);
  };

  // エラー検索ハンドラ
  const handleErrorSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    // エラー検索ロジックを実装（将来的に）
  };

  // タブ切り替えハンドラ
  const handleTabChange = (tab: string) => {
    setCurrentTab(tab);
  };

  // タスク介入ハンドラ
  const handleTaskIntervention = (task_id: string, action: string) => {
    console.log(`タスク ${task_id} に ${action} アクションを実行`);
    // 実際にはAPIを呼び出して介入処理を行う
  };

  return (
    <>
      <Head>
        <title>開発者モニタリングインターフェース - Webシステム開発AIエージェントチーム</title>
        <meta name="description" content="AI開発プロセスの監視と介入を行うインターフェース" />
      </Head>

      <div className="container mt-4">
        <h1 className="mb-4">開発者モニタリングインターフェース</h1>
        
        <ul className="nav nav-tabs mb-4">
          <li className="nav-item">
            <a 
              className={`nav-link ${currentTab === 'active-tasks' ? 'active' : ''}`} 
              href="#active-tasks" 
              onClick={(e) => { e.preventDefault(); handleTabChange('active-tasks'); }}
            >
              アクティブタスク
            </a>
          </li>
          <li className="nav-item">
            <a 
              className={`nav-link ${currentTab === 'error-history' ? 'active' : ''}`} 
              href="#error-history" 
              onClick={(e) => { e.preventDefault(); handleTabChange('error-history'); }}
            >
              エラー履歴
            </a>
          </li>
          <li className="nav-item">
            <a 
              className={`nav-link ${currentTab === 'agent-status' ? 'active' : ''}`} 
              href="#agent-status" 
              onClick={(e) => { e.preventDefault(); handleTabChange('agent-status'); }}
            >
              エージェント状態
            </a>
          </li>
          <li className="nav-item">
            <a 
              className={`nav-link ${currentTab === 'performance' ? 'active' : ''}`} 
              href="#performance" 
              onClick={(e) => { e.preventDefault(); handleTabChange('performance'); }}
            >
              パフォーマンス
            </a>
          </li>
        </ul>
        
        <div className="tab-content">
          {/* アクティブタスクタブ */}
          <div className={`tab-pane ${currentTab === 'active-tasks' ? 'show active' : ''}`} id="active-tasks">
            <div className="mb-3">
              <div className="row">
                <div className="col-md-8">
                  <input 
                    type="text" 
                    className="form-control" 
                    id="taskSearchInput" 
                    placeholder="タスクを検索..." 
                    value={searchTerm}
                    onChange={handleSearchChange}
                  />
                </div>
                <div className="col-md-4">
                  <select 
                    className="form-select" 
                    id="statusFilter"
                    value={statusFilter}
                    onChange={handleStatusFilterChange}
                  >
                    <option value="all">全てのステータス</option>
                    <option value="in_progress">処理中</option>
                    <option value="waiting_info">情報待ち</option>
                    <option value="blocked">ブロック</option>
                    <option value="critical">クリティカル</option>
                  </select>
                </div>
              </div>
            </div>
            
            {filteredTasks.length > 0 ? (
              <div id="taskCards">
                {filteredTasks.map((task) => (
                  <div 
                    key={task.task_id} 
                    className="card mb-3 task-card" 
                    data-status={task.status}
                  >
                    <div className={`card-header ${
                      task.status === 'blocked' || task.status === 'critical' ? 'bg-danger-soft' : 
                      task.status === 'in_progress' ? 'bg-teal text-white' : 'bg-light'
                    }`}>
                      <div className="d-flex justify-content-between align-items-center">
                        <h5 className="mb-0">{task.recipient} → {task.task_type}</h5>
                        <span className={`badge ${
                          task.status === 'in_progress' ? 'bg-success' : 
                          task.status === 'waiting_info' ? 'bg-warning' : 
                          task.status === 'blocked' ? 'bg-danger' : 'bg-secondary'
                        }`}>
                          {task.status}
                        </span>
                      </div>
                    </div>
                    <div className="card-body">
                      <h6 className="card-title">{task.task_id}</h6>
                      <p className="card-text">{task.description}</p>
                      
                      <div className="progress mb-3">
                        <div 
                          className="progress-bar" 
                          role="progressbar" 
                          style={{ width: `${task.progress * 100}%` }} 
                          aria-valuenow={task.progress * 100} 
                          aria-valuemin={0} 
                          aria-valuemax={100}
                        >
                          {Math.round(task.progress * 100)}%
                        </div>
                      </div>
                      
                      <div className="d-flex justify-content-between align-items-center">
                        <small className="text-muted">開始: {new Date(task.created_at).toLocaleDateString('ja-JP')}</small>
                        <div>
                          <button 
                            className="btn btn-sm btn-outline-secondary me-1" 
                            onClick={() => handleTaskIntervention(task.task_id, 'intervene')}
                          >
                            介入
                          </button>
                          <Link href={`/task/${task.task_id}`} className="btn btn-sm btn-outline-primary">
                            詳細
                          </Link>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="alert alert-info">
                現在アクティブなタスクはありません。
              </div>
            )}
          </div>
          
          {/* エラー履歴タブ */}
          <div className={`tab-pane ${currentTab === 'error-history' ? 'show active' : ''}`} id="error-history">
            <div className="mb-3">
              <input 
                type="text" 
                className="form-control" 
                id="errorSearchInput" 
                placeholder="エラーを検索..." 
                onChange={handleErrorSearchChange}
              />
            </div>
            
            {errorHistory.length > 0 ? (
              <div className="card">
                <div className="card-header bg-danger text-white">
                  エラー履歴
                </div>
                <div className="card-body p-0">
                  <div className="table-responsive">
                    <table className="table table-hover mb-0">
                      <thead>
                        <tr>
                          <th>タスクID</th>
                          <th>エラーカテゴリ</th>
                          <th>重要度</th>
                          <th>発生時間</th>
                          <th>回復試行</th>
                          <th>状態</th>
                          <th>アクション</th>
                        </tr>
                      </thead>
                      <tbody id="errorTableBody">
                        {errorHistory.map((error, index) => (
                          <tr key={index}>
                            <td>
                              <Link href={`/task/${error.task_id}`}>
                                {error.task_id}
                              </Link>
                            </td>
                            <td>{error.category}</td>
                            <td>
                              <span className={`badge ${
                                error.severity === 'CRITICAL' ? 'bg-danger' : 
                                error.severity === 'HIGH' ? 'bg-warning' : 'bg-info'
                              }`}>
                                {error.severity}
                              </span>
                            </td>
                            <td>{new Date(error.timestamp).toLocaleString('ja-JP')}</td>
                            <td>{error.recovery_attempts} / {error.max_retries}</td>
                            <td>
                              <span className={`badge ${error.resolved ? 'bg-success' : 'bg-danger'}`}>
                                {error.resolved ? '解決済み' : '未解決'}
                              </span>
                            </td>
                            <td>
                              <button 
                                className="btn btn-sm btn-outline-secondary"
                                onClick={() => console.log(`エラー詳細: ${error.task_id}`)}
                              >
                                詳細
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            ) : (
              <div className="alert alert-success">
                記録されているエラーはありません。
              </div>
            )}
          </div>
          
          {/* エージェント状態タブ */}
          <div className={`tab-pane ${currentTab === 'agent-status' ? 'show active' : ''}`} id="agent-status">
            <div className="row">
              <div className="col-md-6">
                <div className="card mb-3">
                  <div className="card-header bg-primary text-white">
                    コアエージェント状態
                  </div>
                  <div className="card-body p-0">
                    <div className="table-responsive">
                      <table className="table mb-0">
                        <thead>
                          <tr>
                            <th>エージェント</th>
                            <th>状態</th>
                            <th>アクティブタスク</th>
                            <th>使用リソース</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td>PdM</td>
                            <td><span className="badge bg-success">オンライン</span></td>
                            <td>1</td>
                            <td>
                              <div className="progress" style={{ width: '100px' }}>
                                <div className="progress-bar" role="progressbar" style={{ width: '25%' }} aria-valuenow={25} aria-valuemin={0} aria-valuemax={100}>25%</div>
                              </div>
                            </td>
                          </tr>
                          <tr>
                            <td>PM</td>
                            <td><span className="badge bg-success">オンライン</span></td>
                            <td>2</td>
                            <td>
                              <div className="progress" style={{ width: '100px' }}>
                                <div className="progress-bar" role="progressbar" style={{ width: '40%' }} aria-valuenow={40} aria-valuemin={0} aria-valuemax={100}>40%</div>
                              </div>
                            </td>
                          </tr>
                          <tr>
                            <td>デザイナー</td>
                            <td><span className="badge bg-success">オンライン</span></td>
                            <td>1</td>
                            <td>
                              <div className="progress" style={{ width: '100px' }}>
                                <div className="progress-bar" role="progressbar" style={{ width: '30%' }} aria-valuenow={30} aria-valuemin={0} aria-valuemax={100}>30%</div>
                              </div>
                            </td>
                          </tr>
                          <tr>
                            <td>PL</td>
                            <td><span className="badge bg-success">オンライン</span></td>
                            <td>3</td>
                            <td>
                              <div className="progress" style={{ width: '100px' }}>
                                <div className="progress-bar" role="progressbar" style={{ width: '60%' }} aria-valuenow={60} aria-valuemin={0} aria-valuemax={100}>60%</div>
                              </div>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>
              
              <div className="col-md-6">
                <div className="card mb-3">
                  <div className="card-header bg-info text-white">
                    動的エージェント状態
                  </div>
                  <div className="card-body p-0">
                    <div className="table-responsive">
                      <table className="table mb-0">
                        <thead>
                          <tr>
                            <th>エージェント</th>
                            <th>インスタンス数</th>
                            <th>状態</th>
                            <th>アクション</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td>エンジニア</td>
                            <td>3</td>
                            <td><span className="badge bg-success">オンライン</span></td>
                            <td>
                              <button className="btn btn-sm btn-outline-primary me-1">+</button>
                              <button className="btn btn-sm btn-outline-secondary">-</button>
                            </td>
                          </tr>
                          <tr>
                            <td>テスター</td>
                            <td>2</td>
                            <td><span className="badge bg-success">オンライン</span></td>
                            <td>
                              <button className="btn btn-sm btn-outline-primary me-1">+</button>
                              <button className="btn btn-sm btn-outline-secondary">-</button>
                            </td>
                          </tr>
                          <tr>
                            <td>AIアーキテクト</td>
                            <td>1</td>
                            <td><span className="badge bg-warning">アイドル</span></td>
                            <td>
                              <button className="btn btn-sm btn-outline-primary me-1">+</button>
                              <button className="btn btn-sm btn-outline-secondary">-</button>
                            </td>
                          </tr>
                          <tr>
                            <td>プロンプトエンジニア</td>
                            <td>1</td>
                            <td><span className="badge bg-warning">アイドル</span></td>
                            <td>
                              <button className="btn btn-sm btn-outline-primary me-1">+</button>
                              <button className="btn btn-sm btn-outline-secondary">-</button>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            <div className="card">
              <div className="card-header bg-teal text-white">
                システムリソース使用状況
              </div>
              <div className="card-body">
                <div className="row">
                  <div className="col-md-6">
                    <h5>CPU使用率</h5>
                    <div className="progress mb-3">
                      <div className="progress-bar bg-success" role="progressbar" style={{ width: '45%' }} aria-valuenow={45} aria-valuemin={0} aria-valuemax={100}>45%</div>
                    </div>
                    
                    <h5>メモリ使用率</h5>
                    <div className="progress mb-3">
                      <div className="progress-bar bg-info" role="progressbar" style={{ width: '60%' }} aria-valuenow={60} aria-valuemin={0} aria-valuemax={100}>60%</div>
                    </div>
                  </div>
                  
                  <div className="col-md-6">
                    <h5>APIコール（1時間）</h5>
                    <div className="progress mb-3">
                      <div className="progress-bar bg-warning" role="progressbar" style={{ width: '30%' }} aria-valuenow={30} aria-valuemin={0} aria-valuemax={100}>30%</div>
                    </div>
                    
                    <h5>ストレージ使用率</h5>
                    <div className="progress mb-3">
                      <div className="progress-bar bg-primary" role="progressbar" style={{ width: '25%' }} aria-valuenow={25} aria-valuemin={0} aria-valuemax={100}>25%</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          
          {/* パフォーマンスタブ */}
          <div className={`tab-pane ${currentTab === 'performance' ? 'show active' : ''}`} id="performance">
            <div className="card mb-4">
              <div className="card-header bg-primary text-white">
                パフォーマンスメトリクス
              </div>
              <div className="card-body">
                <div className="alert alert-info">
                  リアルタイムチャートはこちらに表示されます。現在この機能は開発中です。
                </div>
                
                <div className="row mt-4">
                  <div className="col-md-6">
                    <h5>タスク完了率（24時間）</h5>
                    <div className="progress mb-3">
                      <div className="progress-bar bg-success" role="progressbar" style={{ width: '85%' }} aria-valuenow={85} aria-valuemin={0} aria-valuemax={100}>85%</div>
                    </div>
                    
                    <h5>平均タスク実行時間</h5>
                    <div className="progress mb-3">
                      <div className="progress-bar bg-info" role="progressbar" style={{ width: '50%' }} aria-valuenow={50} aria-valuemin={0} aria-valuemax={100}>3分42秒</div>
                    </div>
                  </div>
                  
                  <div className="col-md-6">
                    <h5>エラー率（24時間）</h5>
                    <div className="progress mb-3">
                      <div className="progress-bar bg-danger" role="progressbar" style={{ width: '15%' }} aria-valuenow={15} aria-valuemin={0} aria-valuemax={100}>15%</div>
                    </div>
                    
                    <h5>タスクキュー長</h5>
                    <div className="progress mb-3">
                      <div className="progress-bar bg-warning" role="progressbar" style={{ width: '30%' }} aria-valuenow={30} aria-valuemin={0} aria-valuemax={100}>12タスク</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            <div className="card">
              <div className="card-header bg-teal text-white">
                アラート設定
              </div>
              <div className="card-body">
                <div className="table-responsive">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>メトリクス</th>
                        <th>条件</th>
                        <th>通知方法</th>
                        <th>状態</th>
                        <th>アクション</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>エラー率</td>
                        <td>&gt; 20%</td>
                        <td>メール、Slack</td>
                        <td><span className="badge bg-success">有効</span></td>
                        <td>
                          <button className="btn btn-sm btn-outline-secondary me-1">編集</button>
                          <button className="btn btn-sm btn-outline-danger">無効化</button>
                        </td>
                      </tr>
                      <tr>
                        <td>タスクキュー長</td>
                        <td>&gt; 20</td>
                        <td>メール</td>
                        <td><span className="badge bg-success">有効</span></td>
                        <td>
                          <button className="btn btn-sm btn-outline-secondary me-1">編集</button>
                          <button className="btn btn-sm btn-outline-danger">無効化</button>
                        </td>
                      </tr>
                      <tr>
                        <td>API使用量</td>
                        <td>&gt; 90%</td>
                        <td>メール、Slack</td>
                        <td><span className="badge bg-success">有効</span></td>
                        <td>
                          <button className="btn btn-sm btn-outline-secondary me-1">編集</button>
                          <button className="btn btn-sm btn-outline-danger">無効化</button>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                
                <button className="btn btn-primary mt-3">
                  <i className="bi bi-plus-circle"></i> 新しいアラートを追加
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
} 