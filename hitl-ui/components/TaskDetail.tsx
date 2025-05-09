import React from 'react';

// タスクのインターフェース定義
export interface Task {
  id: string;
  title: string;
  description: string;
  requestedBy: string;
  assignedTo: string;
  status: string;
  priority: string;
  createdAt: string;
  dueDate: string;
  tags: string[];
  comments: TaskComment[];
  progress?: number;
  errors?: TaskError[];
}

export interface TaskComment {
  author: string;
  content: string;
  timestamp: string;
}

export interface TaskError {
  id: string;
  message: string;
  timestamp: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  resolved: boolean;
}

// ステータスの表示名マッピング
export const STATUS_LABELS: Record<string, string> = {
  approval_pending: '承認待ち',
  approved: '承認済み',
  rejected: '却下',
  in_progress: '進行中',
  completed: '完了',
  error: 'エラー'
};

// ステータスに応じたバッジクラス
export const STATUS_BADGE_CLASSES: Record<string, string> = {
  approval_pending: 'badge bg-warning',
  approved: 'badge bg-success',
  rejected: 'badge bg-danger',
  in_progress: 'badge bg-info',
  completed: 'badge bg-primary',
  error: 'badge bg-danger'
};

interface TaskDetailProps {
  task: Task;
  onClose?: () => void;
  onApprove?: (taskId: string, comment: string) => void;
  onReject?: (taskId: string, comment: string) => void;
  onAddFeedback?: (taskId: string, comment: string) => void;
  showActions?: boolean;
}

const TaskDetail: React.FC<TaskDetailProps> = ({
  task,
  onClose,
  onApprove,
  onReject,
  onAddFeedback,
  showActions = true
}) => {
  const handleFeedbackSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const commentInput = document.getElementById('feedbackComment') as HTMLTextAreaElement;
    
    if (onAddFeedback && commentInput && commentInput.value.trim()) {
      onAddFeedback(task.id, commentInput.value);
      commentInput.value = '';
    }
  };

  return (
    <div className="task-detail">
      <div className="task-detail-header mb-4">
        <h2>{task.title}</h2>
        <div className="d-flex align-items-center">
          <span className={`${STATUS_BADGE_CLASSES[task.status]} me-2`}>
            {STATUS_LABELS[task.status] || task.status}
          </span>
          <span className="text-muted">ID: {task.id}</span>
        </div>
      </div>

      <div className="row mb-4">
        <div className="col">
          <h5>説明</h5>
          <p>{task.description}</p>
        </div>
      </div>

      <div className="row mb-4">
        <div className="col-md-6">
          <h5>基本情報</h5>
          <table className="table table-sm">
            <tbody>
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
          <h5>タグ</h5>
          <div className="mb-4">
            {task.tags.map(tag => (
              <span key={tag} className="badge bg-secondary me-1 mb-1">{tag}</span>
            ))}
          </div>

          {task.progress !== undefined && (
            <div className="mb-4">
              <h5>進捗</h5>
              <div className="progress">
                <div 
                  className="progress-bar" 
                  role="progressbar" 
                  style={{width: `${task.progress}%`}} 
                  aria-valuenow={task.progress} 
                  aria-valuemin={0} 
                  aria-valuemax={100}
                >
                  {task.progress}%
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {task.errors && task.errors.length > 0 && (
        <div className="row mb-4">
          <div className="col">
            <h5>エラー履歴</h5>
            <div className="timeline error-timeline">
              {task.errors.map(error => (
                <div key={error.id} className="timeline-item">
                  <div className={`timeline-badge ${error.resolved ? 'bg-success' : 'bg-danger'}`}>
                    {error.resolved ? '✓' : '!'}
                  </div>
                  <div className="timeline-content">
                    <div className="d-flex justify-content-between">
                      <span className={`fw-bold ${error.resolved ? 'text-success' : 'text-danger'}`}>
                        {error.severity.toUpperCase()}
                      </span>
                      <small className="text-muted">{new Date(error.timestamp).toLocaleString('ja-JP')}</small>
                    </div>
                    <p>{error.message}</p>
                    {error.resolved && <small className="text-success">解決済み</small>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="row mb-4">
        <div className="col">
          <h5>コメント履歴</h5>
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

      {showActions && (
        <div className="row mb-4">
          <div className="col">
            <h5>フィードバック</h5>
            <form onSubmit={handleFeedbackSubmit}>
              <div className="mb-3">
                <textarea 
                  id="feedbackComment" 
                  className="form-control" 
                  rows={3} 
                  placeholder="コメントを入力してください"
                  required
                ></textarea>
              </div>
              <button type="submit" className="btn btn-primary">送信</button>
            </form>
          </div>
        </div>
      )}

      {showActions && task.status === 'approval_pending' && (onApprove || onReject) && (
        <div className="row mb-4">
          <div className="col">
            <h5>承認/却下</h5>
            <div className="mb-3">
              <textarea 
                id="approvalComment" 
                className="form-control" 
                rows={3} 
                placeholder="承認または却下の理由を入力してください（任意）"
              ></textarea>
            </div>
            <div className="d-flex gap-2">
              {onReject && (
                <button 
                  className="btn btn-danger" 
                  onClick={() => {
                    const commentInput = document.getElementById('approvalComment') as HTMLTextAreaElement;
                    onReject(task.id, commentInput?.value || '');
                  }}
                >
                  却下
                </button>
              )}
              {onApprove && (
                <button 
                  className="btn btn-success" 
                  onClick={() => {
                    const commentInput = document.getElementById('approvalComment') as HTMLTextAreaElement;
                    onApprove(task.id, commentInput?.value || '');
                  }}
                >
                  承認
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TaskDetail; 