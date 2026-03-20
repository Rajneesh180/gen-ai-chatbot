import React from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

const RetrievalPanel = ({ details, isExpanded, onToggle }) => {
  if (!details || details.length === 0) return null;

  return (
    <div className="transparency-section">
      <button className="toggle-details-btn" onClick={onToggle}>
        {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        How I found this (Retrieval Details)
      </button>
      
      {isExpanded && (
        <div className="retrieval-details slide-down-fade">
          {details.slice(0, 3).map((chunk, cIdx) => (
            <div key={cIdx} className="chunk-card">
              <div className="chunk-header">
                <span className="chunk-rank">Rank #{chunk.rank}</span>
                <span className="chunk-score">Score: {chunk.rrf_score.toFixed(3)}</span>
              </div>
              <div className="chunk-title">{chunk.title} {chunk.heading && `> ${chunk.heading}`}</div>
              <div className="chunk-snippet">"{chunk.snippet}"</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default RetrievalPanel;
