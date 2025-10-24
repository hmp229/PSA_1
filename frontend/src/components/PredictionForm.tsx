import React, { useState } from 'react';

interface PredictionFormProps {
  onSubmit: (data: {
    playerA: string;
    playerB: string;
    eventDate?: string;
    noCache: boolean;
  }) => void;
  loading: boolean;
}

export default function PredictionForm({ onSubmit, loading }: PredictionFormProps) {
  const [playerA, setPlayerA] = useState('');
  const [playerB, setPlayerB] = useState('');
  const [eventDate, setEventDate] = useState('');
  const [noCache, setNoCache] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      playerA: playerA.trim(),
      playerB: playerB.trim(),
      eventDate: eventDate || undefined,
      noCache,
    });
  };

  return (
    <form onSubmit={handleSubmit} style={{
      background: 'white',
      padding: '2rem',
      borderRadius: '8px',
      boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
      marginBottom: '2rem'
    }}>
      <h2 style={{ marginTop: 0, marginBottom: '1.5rem', color: '#333' }}>
        Match Prediction
      </h2>
      
      <div style={{ marginBottom: '1rem' }}>
        <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
          Player A
        </label>
        <input
          type="text"
          value={playerA}
          onChange={(e) => setPlayerA(e.target.value)}
          placeholder="e.g., Ali Farag"
          required
          style={{
            width: '100%',
            padding: '0.5rem',
            border: '1px solid #ddd',
            borderRadius: '4px',
            fontSize: '1rem'
          }}
        />
      </div>
      
      <div style={{ marginBottom: '1rem' }}>
        <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
          Player B
        </label>
        <input
          type="text"
          value={playerB}
          onChange={(e) => setPlayerB(e.target.value)}
          placeholder="e.g., Paul Coll"
          required
          style={{
            width: '100%',
            padding: '0.5rem',
            border: '1px solid #ddd',
            borderRadius: '4px',
            fontSize: '1rem'
          }}
        />
      </div>
      
      <div style={{ marginBottom: '1rem' }}>
        <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
          Event Date (Optional)
        </label>
        <input
          type="date"
          value={eventDate}
          onChange={(e) => setEventDate(e.target.value)}
          style={{
            width: '100%',
            padding: '0.5rem',
            border: '1px solid #ddd',
            borderRadius: '4px',
            fontSize: '1rem'
          }}
        />
        <small style={{ color: '#666', fontSize: '0.85rem' }}>
          Include to show tournament context
        </small>
      </div>
      
      <div style={{ marginBottom: '1.5rem' }}>
        <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={noCache}
            onChange={(e) => setNoCache(e.target.checked)}
            style={{ marginRight: '0.5rem' }}
          />
          <span style={{ fontSize: '0.9rem' }}>Bypass cache (fetch fresh data)</span>
        </label>
      </div>
      
      <button
        type="submit"
        disabled={loading}
        style={{
          width: '100%',
          padding: '0.75rem',
          background: loading ? '#999' : '#667eea',
          color: 'white',
          border: 'none',
          borderRadius: '4px',
          fontSize: '1rem',
          fontWeight: '600',
          cursor: loading ? 'not-allowed' : 'pointer',
          transition: 'background 0.2s'
        }}
      >
        {loading ? 'Predicting...' : 'Predict Match'}
      </button>
    </form>
  );
}
