

interface EventInfo {
  name: string;
  location: {
    city: string;
    country: string;
    venue: string;
  };
  start_date: string;
  end_date: string;
  tier: string;
}

interface RankingSnapshot {
  rank: number;
  points: number;
  snapshot: string;
}

interface MetaBlockProps {
  event?: EventInfo;
  rankingA: RankingSnapshot;
  rankingB: RankingSnapshot;
  playerA: string;
  playerB: string;
}

export default function MetaBlock({ event, rankingA, rankingB, playerA, playerB }: MetaBlockProps) {
  return (
    <div style={{
      background: 'white',
      padding: '1.5rem',
      borderRadius: '8px',
      boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
      marginBottom: '2rem'
    }}>
      {event && (
        <div style={{ marginBottom: '1.5rem', paddingBottom: '1.5rem', borderBottom: '1px solid #eee' }}>
          <h3 style={{ margin: '0 0 0.75rem 0', color: '#667eea', fontSize: '1.1rem' }}>
            Tournament Context
          </h3>
          <div style={{ fontSize: '0.95rem' }}>
            <div style={{ marginBottom: '0.25rem' }}>
              <strong>{event.name}</strong> ({event.tier})
            </div>
            <div style={{ color: '#666' }}>
              {event.location.city}, {event.location.country}
              {event.location.venue !== '—' && ` • ${event.location.venue}`}
            </div>
            <div style={{ color: '#666', fontSize: '0.9rem', marginTop: '0.25rem' }}>
              {event.start_date} to {event.end_date}
            </div>
          </div>
        </div>
      )}
      
      <div>
        <h3 style={{ margin: '0 0 0.75rem 0', color: '#667eea', fontSize: '1.1rem' }}>
          Current Rankings
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          <div style={{
            padding: '1rem',
            background: '#f8f9fa',
            borderRadius: '4px'
          }}>
            <div style={{ fontWeight: '600', marginBottom: '0.5rem' }}>{playerA}</div>
            <div style={{ fontSize: '0.9rem', color: '#666' }}>
              <div>Rank: <strong>#{rankingA.rank}</strong></div>
              <div>Points: {rankingA.points.toLocaleString()}</div>
              <div style={{ fontSize: '0.85rem', marginTop: '0.25rem' }}>
                As of {rankingA.snapshot}
              </div>
            </div>
          </div>
          
          <div style={{
            padding: '1rem',
            background: '#f8f9fa',
            borderRadius: '4px'
          }}>
            <div style={{ fontWeight: '600', marginBottom: '0.5rem' }}>{playerB}</div>
            <div style={{ fontSize: '0.9rem', color: '#666' }}>
              <div>Rank: <strong>#{rankingB.rank}</strong></div>
              <div>Points: {rankingB.points.toLocaleString()}</div>
              <div style={{ fontSize: '0.85rem', marginTop: '0.25rem' }}>
                As of {rankingB.snapshot}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
