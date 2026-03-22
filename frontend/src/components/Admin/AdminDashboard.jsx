import React, { useEffect, useState } from 'react';
import { ArrowLeft, MessageSquare, ThumbsUp, ThumbsDown, TrendingUp, Clock } from 'lucide-react';

const API_BASE = import.meta.env.DEV ? 'http://localhost:8000' : '';

const AdminDashboard = ({ onBack }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/admin/analytics`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="admin-dashboard">
        <div className="admin-loading">Loading analytics...</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="admin-dashboard">
        <div className="admin-loading">Failed to load analytics.</div>
      </div>
    );
  }

  const satisfactionRate = data.total_feedback > 0
    ? Math.round((data.feedback_up / data.total_feedback) * 100)
    : 0;

  return (
    <div className="admin-dashboard">
      <div className="admin-header">
        <button className="admin-back-btn" onClick={onBack}>
          <ArrowLeft size={18} /> Back to Chat
        </button>
        <h2 className="admin-title">Analytics Dashboard</h2>
      </div>

      <div className="admin-stats-grid">
        <div className="stat-card">
          <MessageSquare size={24} className="stat-icon" />
          <div className="stat-value">{data.total_queries}</div>
          <div className="stat-label">Total Queries</div>
        </div>
        <div className="stat-card">
          <ThumbsUp size={24} className="stat-icon positive" />
          <div className="stat-value">{data.feedback_up}</div>
          <div className="stat-label">Positive Feedback</div>
        </div>
        <div className="stat-card">
          <ThumbsDown size={24} className="stat-icon negative" />
          <div className="stat-value">{data.feedback_down}</div>
          <div className="stat-label">Negative Feedback</div>
        </div>
        <div className="stat-card">
          <TrendingUp size={24} className="stat-icon" />
          <div className="stat-value">{satisfactionRate}%</div>
          <div className="stat-label">Satisfaction Rate</div>
        </div>
      </div>

      {data.top_topics.length > 0 && (
        <div className="admin-section">
          <h3 className="admin-section-title">Top Queried Topics</h3>
          <div className="topic-bars">
            {data.top_topics.map((t, i) => {
              const maxCount = data.top_topics[0].count;
              const widthPct = Math.max(10, (t.count / maxCount) * 100);
              return (
                <div key={i} className="topic-bar-row">
                  <span className="topic-bar-label">{t.topic}</span>
                  <div className="topic-bar-track">
                    <div className="topic-bar-fill" style={{ width: `${widthPct}%` }} />
                  </div>
                  <span className="topic-bar-count">{t.count}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {data.daily_volume.length > 0 && (
        <div className="admin-section">
          <h3 className="admin-section-title">Daily Query Volume</h3>
          <div className="daily-grid">
            {data.daily_volume.slice(-14).map((d, i) => (
              <div key={i} className="daily-cell">
                <div className="daily-bar" style={{
                  height: `${Math.max(8, (d.count / Math.max(...data.daily_volume.map(x => x.count))) * 60)}px`
                }} />
                <span className="daily-date">{d.date.slice(5)}</span>
                <span className="daily-count">{d.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.recent_queries.length > 0 && (
        <div className="admin-section">
          <h3 className="admin-section-title">
            <Clock size={16} /> Recent Queries
          </h3>
          <div className="recent-queries-list">
            {data.recent_queries.map((q, i) => (
              <div key={i} className="recent-query-row">
                <span className="recent-query-text">{q.query}</span>
                <span className="recent-query-time">{q.timestamp?.slice(11, 16)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminDashboard;
