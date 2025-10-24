

interface Driver {
  feature: string;
  impact: string;
  note: string;
}

interface PredictionResult {
  playerA: string;
  playerB: string;
  summary: {
    winner: string;
    proba: {
      A: number;
      B: number;
    };
    ci95: {
      A: [number, number];
      B: [number, number];
    };
  };
  explain: {
    drivers: Driver[];
  };
  warnings?: string[];
  sources?: string[];
}

interface ResultCardProps {
  result: PredictionResult;
}

export default function ResultCard({ result }: ResultCardProps) {
  const { playerA, playerB, summary, explain, warnings, sources } = result;
  const winnerName = summary.winner === 'A' ? playerA : playerB;
  const winnerProb = summary.winner === 'A' ? summary.proba.A : summary.proba.B;

  return (
    <div style={{
      background: 'white',
      padding: '2rem',
      borderRadius: '8px',
      boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
    }}>
      <h2 style={{ marginTop: 0, marginBottom: '1.5rem', color: '#333' }}>
        Prediction Result
      </h2>
      
      {/* Winner announcement */}
      <div style={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        color: 'white',
        padding: '1.5rem',
        borderRadius: '8px',
        marginBottom: '1.5rem',
        textAlign: 'center'
      }}>
        <div style={{ fontSize: '1.1rem', marginBottom: '0.5rem', opacity: 0.9 }}>
          Predicted Winner
        </div>
        <div style={{ fontSize: '2rem', fontWeight: 'bold', marginBottom: '0.5rem' }}>
          {winnerName}
        </div>
        <div style={{ fontSize: '1.5rem' }}>
          {(winnerProb * 100).toFixed(1)}% probability
        </div>
      </div>
      
      {/* Probabilities with confidence intervals */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '1rem',
        marginBottom: '1.5rem'
      }}>
        <div style={{
          padding: '1rem',
          background: summary.winner === 'A' ? '#e8f5e9' : '#f5f5f5',
          borderRadius: '4px',
          border: summary.winner === 'A' ? '2px solid #4caf50' : '1px solid #ddd'
        }}>
          <div style={{ fontWeight: '600', marginBottom: '0.5rem' }}>{playerA}</div>
          <div style={{ fontSize: '1.3rem', fontWeight: 'bold', marginBottom: '0.25rem' }}>
            {(summary.proba.A * 100).toFixed(1)}%
          </div>
          <div style={{ fontSize: '0.85rem', color: '#666' }}>
            95% CI: {(summary.ci95.A[0] * 100).toFixed(1)}% – {(summary.ci95.A[1] * 100).toFixed(1)}%
          </div>
        </div>
        
        <div style={{
          padding: '1rem',
          background: summary.winner === 'B' ? '#e8f5e9' : '#f5f5f5',
          borderRadius: '4px',
          border: summary.winner === 'B' ? '2px solid #4caf50' : '1px solid #ddd'
        }}>
          <div style={{ fontWeight: '600', marginBottom: '0.5rem' }}>{playerB}</div>
          <div style={{ fontSize: '1.3rem', fontWeight: 'bold', marginBottom: '0.25rem' }}>
            {(summary.proba.B * 100).toFixed(1)}%
          </div>
          <div style={{ fontSize: '0.85rem', color: '#666' }}>
            95% CI: {(summary.ci95.B[0] * 100).toFixed(1)}% – {(summary.ci95.B[1] * 100).toFixed(1)}%
          </div>
        </div>
      </div>
      
      {/* Explanation drivers */}
      <div style={{ marginBottom: '1.5rem' }}>
        <h3 style={{ fontSize: '1.1rem', marginBottom: '0.75rem', color: '#333' }}>
          Key Factors
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {explain.drivers.map((driver, idx) => (
            <div
              key={idx}
              style={{
                padding: '0.75rem',
                background: '#f8f9fa',
                borderRadius: '4px',
                borderLeft: '3px solid #667eea'
              }}
            >
              <div style={{ fontWeight: '600', marginBottom: '0.25rem', fontSize: '0.95rem' }}>
                {driver.feature}
                <span style={{
                  marginLeft: '0.5rem',
                  fontSize: '0.85rem',
                  color: driver.impact.includes('+') ? '#4caf50' : 
                         driver.impact.includes('-') ? '#f44336' : '#666',
                  fontWeight: 'normal'
                }}>
                  ({driver.impact})
                </span>
              </div>
              <div style={{ fontSize: '0.9rem', color: '#666' }}>
                {driver.note}
              </div>
            </div>
          ))}
        </div>
      </div>
      
      {/* Warnings */}
      {warnings && warnings.length > 0 && (
        <div style={{
          padding: '1rem',
          background: '#fff3cd',
          border: '1px solid #ffc107',
          borderRadius: '4px',
          marginBottom: '1rem'
        }}>
          <div style={{ fontWeight: '600', marginBottom: '0.5rem', fontSize: '0.95rem' }}>
            ⚠️ Warnings
          </div>
          <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.9rem' }}>
            {warnings.map((warning, idx) => (
              <li key={idx}>{warning}</li>
            ))}
          </ul>
        </div>
      )}
      
      {/* Sources */}
      {sources && sources.length > 0 && (
        <div style={{ fontSize: '0.85rem', color: '#666' }}>
          <details>
            <summary style={{ cursor: 'pointer', fontWeight: '500' }}>
              Data sources ({sources.length})
            </summary>
            <ul style={{ marginTop: '0.5rem', paddingLeft: '1.25rem' }}>
              {sources.map((source, idx) => (
                <li key={idx}>
                  <a href={source} target="_blank" rel="noopener noreferrer" style={{ color: '#667eea' }}>
                    {source}
                  </a>
                </li>
              ))}
            </ul>
          </details>
        </div>
      )}
    </div>
  );
}
