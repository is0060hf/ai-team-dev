import React, { useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useEffect } from 'react';

// ダミーのタスクデータ
const dummyTasks = [
  {
    task_id: 'task-001',
    context: { 
      title: 'ログイン機能の実装',
      tags: ['認証', 'フロントエンド', 'バックエンド']
    },
    description: 'ユーザー認証システムとログイン画面の実装',
    status: 'completed',
    created_at: '2023-10-30T10:00:00'
  },
  {
    task_id: 'task-002',
    context: { 
      title: 'データ可視化ダッシュボード',
      tags: ['データ可視化', 'フロントエンド', 'チャート']
    },
    description: 'ユーザーアクティビティを可視化するダッシュボードの開発',
    status: 'in_progress',
    created_at: '2023-10-31T09:15:00'
  },
  {
    task_id: 'task-003',
    context: { 
      title: 'モバイルアプリとの連携API',
      tags: ['API', 'バックエンド', 'モバイル']
    },
    description: 'モバイルアプリからのデータ連携用APIエンドポイントの設計と実装',
    status: 'waiting',
    created_at: '2023-11-01T14:30:00'
  }
];

export default function ProductOwner() {
  const router = useRouter();
  const [recentTasks, setRecentTasks] = useState(dummyTasks);
  const [searchTerm, setSearchTerm] = useState('');
  
  // フォームの状態
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    priority: '',
    deadline: '',
    tags: ''
  });
  
  // フォームの入力ハンドラ
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData({
      ...formData,
      [name]: value
    });
  };
  
  // 検索ハンドラ
  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchTerm(e.target.value.toLowerCase());
  };
  
  // タスク検索フィルター
  const filteredTasks = recentTasks.filter(task => {
    const title = task.context.title ? task.context.title.toLowerCase() : '';
    const description = task.description.toLowerCase();
    const tags = task.context.tags ? task.context.tags.join(' ').toLowerCase() : '';
    
    return title.includes(searchTerm) || 
           description.includes(searchTerm) || 
           tags.includes(searchTerm);
  });
  
  // フォームの送信ハンドラ
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // タグをカンマ区切りの文字列から配列に変換
    const tagsArray = formData.tags
      .split(',')
      .map(tag => tag.trim())
      .filter(tag => tag !== '');
    
    // 送信データの作成
    const submitData = {
      title: formData.title,
      description: formData.description,
      priority: formData.priority,
      deadline: formData.deadline || null,
      tags: tagsArray
    };
    
    try {
      // ここでは実際のAPIの代わりにモックレスポンスを使用
      // 実際の実装ではfetchでAPIを呼び出す
      console.log('提出データ:', submitData);
      
      // 成功のモック
      const mockResponse = {
        status: 'success',
        message: '要求が正常に提出されました',
        task_id: `task-${Math.floor(Math.random() * 1000)}`
      };
      
      // 新しいタスクを追加して表示
      const newTask = {
        task_id: mockResponse.task_id,
        context: { 
          title: submitData.title,
          tags: submitData.tags
        },
        description: submitData.description,
        status: 'waiting',
        created_at: new Date().toISOString()
      };
      
      setRecentTasks([newTask, ...recentTasks]);
      
      // フォームをリセット
      setFormData({
        title: '',
        description: '',
        priority: '',
        deadline: '',
        tags: ''
      });
      
      // 成功メッセージの表示
      alert(`${mockResponse.message}\nタスクID: ${mockResponse.task_id}`);
    } catch (error) {
      console.error('エラー:', error);
      alert('通信エラーが発生しました。再度お試しください。');
    }
  };
  
  return (
    <>
      <Head>
        <title>プロダクトオーナーインターフェース - Webシステム開発AIエージェントチーム</title>
        <meta name="description" content="プロダクトオーナー向けの要求入力インターフェース" />
      </Head>

      <div className="container mt-4">
        <h1 className="mb-4">プロダクトオーナーインターフェース</h1>
        
        <div className="row">
          {/* 要求入力フォーム */}
          <div className="col-md-6">
            <div className="card">
              <div className="card-header bg-purple text-white">
                新規要求の提出
              </div>
              <div className="card-body">
                <form onSubmit={handleSubmit}>
                  <div className="mb-3">
                    <label htmlFor="title" className="form-label">タイトル</label>
                    <input
                      type="text"
                      className="form-control"
                      id="title"
                      name="title"
                      value={formData.title}
                      onChange={handleInputChange}
                      required
                    />
                  </div>
                  
                  <div className="mb-3">
                    <label htmlFor="description" className="form-label">詳細説明</label>
                    <textarea
                      className="form-control"
                      id="description"
                      name="description"
                      rows={5}
                      value={formData.description}
                      onChange={handleInputChange}
                      required
                    ></textarea>
                  </div>
                  
                  <div className="mb-3">
                    <label htmlFor="priority" className="form-label">優先度</label>
                    <select
                      className="form-select"
                      id="priority"
                      name="priority"
                      value={formData.priority}
                      onChange={handleInputChange}
                      required
                    >
                      <option value="">選択してください</option>
                      <option value="high">高（High）</option>
                      <option value="medium">中（Medium）</option>
                      <option value="low">低（Low）</option>
                    </select>
                  </div>
                  
                  <div className="mb-3">
                    <label htmlFor="deadline" className="form-label">期限（オプション）</label>
                    <input
                      type="date"
                      className="form-control"
                      id="deadline"
                      name="deadline"
                      value={formData.deadline}
                      onChange={handleInputChange}
                    />
                  </div>
                  
                  <div className="mb-3">
                    <label htmlFor="tags" className="form-label">タグ（カンマ区切り、オプション）</label>
                    <input
                      type="text"
                      className="form-control"
                      id="tags"
                      name="tags"
                      placeholder="例: フロントエンド, デザイン, 認証"
                      value={formData.tags}
                      onChange={handleInputChange}
                    />
                  </div>
                  
                  <div className="mb-4">
                    <label htmlFor="attachments" className="form-label">添付ファイル（オプション）</label>
                    <input
                      type="file"
                      className="form-control"
                      id="attachments"
                      name="attachments"
                      multiple
                      disabled
                    />
                    <div className="form-text">現在この機能は利用できません（開発中）</div>
                  </div>
                  
                  <button type="submit" className="btn btn-primary">要求を提出</button>
                </form>
              </div>
            </div>
          </div>
          
          {/* 最近の要求 */}
          <div className="col-md-6">
            <div className="card">
              <div className="card-header bg-info text-white">
                最近の要求
              </div>
              <div className="card-body">
                <div className="mb-3">
                  <input
                    type="text"
                    className="form-control"
                    id="taskSearch"
                    placeholder="タスクを検索..."
                    value={searchTerm}
                    onChange={handleSearch}
                  />
                </div>
                
                {filteredTasks.length > 0 ? (
                  <div id="taskList">
                    {filteredTasks.map((task) => (
                      <div key={task.task_id} className="card mb-3 task-card">
                        <div className="card-body">
                          <div className="d-flex justify-content-between align-items-center">
                            <h5 className="card-title">{task.context.title}</h5>
                            <span className={`badge ${
                              task.status === 'completed' ? 'bg-success' :
                              task.status === 'in_progress' ? 'bg-warning' :
                              task.status === 'failed' ? 'bg-danger' : 'bg-secondary'
                            }`}>
                              {task.status}
                            </span>
                          </div>
                          <p className="card-text">{task.description}</p>
                          
                          <div className="mb-2">
                            {task.context.tags && task.context.tags.map((tag: string, index: number) => (
                              <span key={index} className="badge bg-light text-dark me-1 mb-1">{tag}</span>
                            ))}
                          </div>
                          
                          <div className="d-flex justify-content-between align-items-center">
                            <small className="text-muted">提出日: {new Date(task.created_at).toLocaleDateString('ja-JP')}</small>
                            <Link href={`/task/${task.task_id}`} className="btn btn-sm btn-outline-primary">
                              詳細を表示
                            </Link>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="alert alert-info">
                    最近の要求はありません。
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
} 