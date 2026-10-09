import React, { useState, useEffect } from 'react';
import { Calendar, Play, Trash2, Plus, Clock, Globe, ToggleLeft, ToggleRight, Loader } from 'lucide-react';

interface SchedulerConsoleProps {
  sessionId: string | null;
  url: string;
  history: any[];
}

interface ScheduledJob {
  id: string;
  name: string;
  url: string;
  history: any[];
  cron_expression: string;
  webhook_url: string;
  enabled: boolean;
  last_run?: string;
  next_run?: string;
  created_at: string;
}

function isValidCron(expr: string): { valid: boolean; message?: string } {
  const parts = expr.trim().split(/\s+/);
  const wildRange = /^(\*|[0-9]+)([-\/][0-9]+|[-\*])?$/;
  if (parts.length !== 5) return { valid: false, message: '必须恰好包含 5 个字段（分 时 日 月 周）' };
  const validators = [
    { name: '分钟', max: 59, pattern: wildRange },
    { name: '小时', max: 23, pattern: wildRange },
    { name: '日', max: 31, pattern: wildRange },
    { name: '月', max: 12, pattern: wildRange },
    { name: '星期', max: 7, pattern: wildRange },
  ];
  for (let i = 0; i < 5; i++) {
    const field = parts[i];
    const validator = validators[i];
    for (const segment of field.split(',')) {
      if (!validator.pattern.test(segment)) return { valid: false, message: `无效的“${validator.name}”字段：'${segment}'` };
    }
  }
  return { valid: true };
}

export const SchedulerConsole: React.FC<SchedulerConsoleProps> = ({ sessionId, url, history }) => {
  const [jobs, setJobs] = useState<ScheduledJob[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [runningJobId, setRunningJobId] = useState<string | null>(null);

  // Form state
  const [showAddForm, setShowAddForm] = useState(false);
  const [jobName, setJobName] = useState('');
  const [cronExpression, setCronExpression] = useState('*/5 * * * *');
  const [cronValidation, setCronValidation] = useState<{ valid: boolean; message?: string }>({ valid: true });
  const [webhookUrl, setWebhookUrl] = useState('');
  const [editingJob, setEditingJob] = useState<ScheduledJob | null>(null);

  useEffect(() => {
    fetchJobs();
  }, []);

  const fetchJobs = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('/api/scheduler/jobs');
      if (response.ok) {
        const data = await response.json();
        setJobs(data.jobs || []);
      }
    } catch (e) {
      console.error('Failed to fetch scheduled jobs', e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    setCronValidation(isValidCron(cronExpression));
  }, [cronExpression]);

  const handleSaveJob = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!jobName || !cronExpression) {
      alert('任务名称和 Cron 表达式为必填项。');
      return;
    }
    if (!cronValidation.valid) {
      alert(`无效的 Cron 表达式：${cronValidation.message}`);
      return;
    }

    setIsSaving(true);
    try {
      const response = await fetch('/api/scheduler/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: editingJob?.id || undefined,
          name: jobName,
          url: editingJob?.url || url,
          history: editingJob?.history || history,
          cron_expression: cronExpression,
          webhook_url: webhookUrl,
          enabled: editingJob ? editingJob.enabled : true
        })
      });

      if (response.ok) {
        setShowAddForm(false);
        setEditingJob(null);
        setJobName('');
        setWebhookUrl('');
        fetchJobs();
      } else {
        const err = await response.json();
        alert('保存任务失败：' + (err.detail || '未知错误'));
      }
    } catch (e) {
      console.error('Error saving job', e);
      alert('保存任务时出错');
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggleJob = async (job: ScheduledJob) => {
    try {
      const response = await fetch(`/api/scheduler/jobs/${job.id}/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !job.enabled })
      });
      if (response.ok) {
        fetchJobs();
      }
    } catch (e) {
      console.error('Failed to toggle job', e);
    }
  };

  const handleDeleteJob = async (jobId: string) => {
    if (!confirm('确定要删除这个定时任务吗？')) return;
    try {
      const response = await fetch(`/api/scheduler/jobs/${jobId}`, {
        method: 'DELETE'
      });
      if (response.ok) {
        fetchJobs();
      }
    } catch (e) {
      console.error('Failed to delete job', e);
    }
  };

  const handleTriggerRun = async (jobId: string) => {
    setRunningJobId(jobId);
    try {
      const response = await fetch(`/api/scheduler/jobs/${jobId}/run`, {
        method: 'POST'
      });
      if (response.ok) {
        alert('无头任务已在后台成功触发运行！');
        setTimeout(fetchJobs, 2000); // refresh to see last run
      }
    } catch (e) {
      console.error('Failed to trigger job run', e);
    } finally {
      setRunningJobId(null);
    }
  };

  const startScheduleNew = () => {
    if (history.length === 0) {
      alert('请先构建抓取配方，再创建定时任务！');
      return;
    }
    setEditingJob(null);
    setJobName(`抓取 HN 列表`);
    setCronExpression('0 * * * *'); // Hourly default
    setWebhookUrl('https://httpbin.org/post');
    setShowAddForm(true);
  };

  const formatDate = (isoStr?: string) => {
    if (!isoStr) return '从未';
    try {
      const d = new Date(isoStr);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) + ' ' + d.toLocaleDateString();
    } catch (_) {
      return '从未';
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', background: 'var(--bg-panel)' }}>
      {/* Header bar */}
      <div style={{
        padding: '12px 16px',
        borderBottom: '1px solid var(--border-light)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        background: '#0a0d16'
      }}>
        <span style={{ fontSize: '13px', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}>
          <Calendar size={14} color="var(--accent-primary)" />
          定时爬虫与 Webhook
        </span>
        {!showAddForm && (
          <button
            className="btn btn-primary"
            onClick={startScheduleNew}
            disabled={!sessionId || history.length === 0}
            style={{ padding: '0 8px', height: '26px', fontSize: '11px', gap: '4px' }}
          >
            <Plus size={12} />
            定时运行配方
          </button>
        )}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {showAddForm ? (
          <form onSubmit={handleSaveJob} style={{ display: 'flex', flexDirection: 'column', gap: '12px', background: '#0a0d16', padding: '16px', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border-light)' }}>
            <h4 style={{ margin: 0, fontSize: '13px', color: 'var(--accent-primary)' }}>
              {editingJob ? '编辑定时任务' : '定时运行当前配方'}
            </h4>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>任务名称：</label>
              <input
                type="text"
                value={jobName}
                onChange={(e) => setJobName(e.target.value)}
                placeholder="例如：HN 首页抓取器"
                required
                style={{
                  background: 'var(--bg-main)',
                  border: '1px solid var(--border-light)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '6px 10px',
                  color: '#fff',
                  fontSize: '12px'
                }}
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '11px', color: 'var(--text-secondary)', display: 'flex', justifyContent: 'space-between' }}>
                <span>Cron 间隔表达式：</span>
                <a href="https://crontab.guru" target="_blank" rel="noreferrer" style={{ color: 'var(--accent-secondary)', textDecoration: 'none' }}>crontab.guru</a>
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type="text"
                  value={cronExpression}
                  onChange={(e) => setCronExpression(e.target.value)}
                  placeholder="例如：*/5 * * * *（每 5 分钟）"
                  required
                  style={{
                    background: 'var(--bg-main)',
                    border: `1px solid ${cronExpression && !cronValidation.valid ? 'var(--accent-error)' : 'var(--border-light)'}`,
                    borderRadius: 'var(--radius-sm)',
                    padding: '6px 10px',
                    color: '#fff',
                    fontSize: '12px',
                    fontFamily: 'var(--font-mono)',
                    width: '100%',
                    boxSizing: 'border-box'
                  }}
                />
                {cronExpression && !cronValidation.valid && (
                  <span style={{
                    position: 'absolute',
                    right: '8px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    fontSize: '10px',
                    color: 'var(--accent-error)',
                    fontFamily: 'var(--font-mono)',
                    pointerEvents: 'none'
                  }}>
                    {cronValidation.message}
                  </span>
                )}
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Webhook URL 导出器（POST 抓取数据）：</label>
              <input
                type="url"
                value={webhookUrl}
                onChange={(e) => setWebhookUrl(e.target.value)}
                placeholder="https://yourserver.com/webhook"
                style={{
                  background: 'var(--bg-main)',
                  border: '1px solid var(--border-light)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '6px 10px',
                  color: '#fff',
                  fontSize: '12px'
                }}
              />
            </div>

            <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
              <button type="submit" className="btn btn-primary" disabled={isSaving} style={{ flex: 1, height: '32px', fontSize: '12px' }}>
                {isSaving ? '保存中...' : '保存任务'}
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowAddForm(false)}
                style={{ flex: 1, height: '32px', fontSize: '12px' }}
              >
                取消
              </button>
            </div>
          </form>
        ) : isLoading ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100px', gap: '8px', color: 'var(--text-muted)' }}>
            <Loader size={16} className="loader" />
            <span style={{ fontSize: '12px' }}>正在加载定时任务配置...</span>
          </div>
        ) : jobs.length === 0 ? (
          <div style={{ border: '1px dashed var(--border-light)', borderRadius: 'var(--radius-md)', padding: '24px 12px', textAlign: 'center', color: 'var(--text-muted)' }}>
            <Clock size={32} style={{ marginBottom: '8px', opacity: 0.5 }} />
            <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>暂无后台任务</div>
            <div style={{ fontSize: '11.5px', maxWidth: '240px', margin: '0 auto' }}>
              启动浏览器会话、录制列表提取步骤，然后点击“定时运行配方”让它在后台周期性运行！
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {jobs.map((job) => (
              <div
                key={job.id}
                style={{
                  background: '#0a0d16',
                  border: '1px solid var(--border-light)',
                  borderRadius: 'var(--radius-lg)',
                  padding: '12px 14px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', overflow: 'hidden' }}>
                    <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>{job.name}</span>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }} title={job.url}>
                      {job.url}
                    </span>
                  </div>
                  
                  {/* Enable/Disable switch toggle */}
                  <button
                    onClick={() => handleToggleJob(job)}
                    style={{ background: 'transparent', border: 'none', padding: 0, cursor: 'pointer', display: 'flex', color: job.enabled ? 'var(--accent-secondary)' : 'var(--text-muted)' }}
                    title={job.enabled ? '禁用' : '启用'}
                  >
                    {job.enabled ? <ToggleRight size={28} /> : <ToggleLeft size={28} />}
                  </button>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', borderTop: '1px solid var(--border-light)', paddingTop: '8px', fontSize: '11px' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
                    <span style={{ color: 'var(--text-muted)' }}>间隔（Cron）</span>
                    <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{job.cron_expression}</span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
                    <span style={{ color: 'var(--text-muted)' }}>步骤数</span>
                    <span style={{ color: 'var(--text-primary)' }}>{job.history.length} 个步骤</span>
                  </div>
                </div>

                {job.webhook_url && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', background: 'rgba(236,72,153,0.06)', padding: '4px 8px', borderRadius: '4px', border: '1px solid rgba(236,72,153,0.1)' }}>
                    <Globe size={11} color="var(--accent-secondary)" />
                    <span style={{ color: 'var(--text-secondary)', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap', flex: 1 }}>
                      {job.webhook_url}
                    </span>
                  </div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', fontSize: '10.5px', color: 'var(--text-muted)', background: 'var(--bg-main)', padding: '6px 8px', borderRadius: '4px' }}>
                  <div>上次运行：<span style={{ color: 'var(--text-primary)' }}>{formatDate(job.last_run)}</span></div>
                  <div>下次运行：<span style={{ color: job.enabled ? 'var(--accent-primary)' : 'var(--text-muted)' }}>{job.enabled ? formatDate(job.next_run) : '已禁用'}</span></div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '6px', marginTop: '2px' }}>
                  <button
                    className="btn btn-secondary"
                    onClick={() => handleTriggerRun(job.id)}
                    disabled={runningJobId === job.id}
                    style={{ height: '26px', padding: '0 8px', fontSize: '11px', gap: '4px' }}
                    title="立即运行爬虫"
                  >
                    {runningJobId === job.id ? <Loader size={12} className="loader" /> : <Play size={12} color="var(--accent-secondary)" />}
                    立即运行
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={() => handleDeleteJob(job.id)}
                    style={{ height: '26px', padding: '0 8px', fontSize: '11px', gap: '4px', borderColor: 'var(--accent-error)' }}
                    title="删除任务"
                  >
                    <Trash2 size={12} color="var(--accent-error)" />
                    删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
