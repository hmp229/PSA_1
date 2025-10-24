import { useState } from 'react';  // Remove React import
import PredictionForm from './components/PredictionForm';
import ResultCard from './components/ResultCard';
import MetaBlock from './components/MetaBlock';

export default function App() {
  const [prediction, setPrediction] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const API_URL = import.meta.env.VITE_API_URL || '';
  const handlePrediction = async (data: {
  playerA: string;
  playerB: string;
  eventDate?: string;
  noCache: boolean;
}) => {
  setLoading(true);
  setError('');
  setPrediction(null);

  try {
    const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
    const params = new URLSearchParams({
      playerA: data.playerA,
      playerB: data.playerB,
      no_cache: data.noCache.toString(),
    });

    if (data.eventDate) {
      params.append('event_date', data.eventDate);
    }

    const url = `${API_URL}/api/predict?${params}`;
    console.log('🔍 Making request to:', url);

    const response = await fetch(url);
    console.log('🔍 Response status:', response.status);

    // Get the response as text first to see what we're getting
    const responseText = await response.text();
    console.log('🔍 Response text (first 500 chars):', responseText.substring(0, 500));

    // Check if we got HTML instead of JSON
    if (responseText.includes('<!DOCTYPE html>') || responseText.includes('<html')) {
      throw new Error(`Backend returned HTML instead of JSON. This means:
1. Backend is not running on port 8001
2. Or the /api/predict endpoint doesn't exist
3. Or there's a server configuration issue

Check the browser console for the full URL and test it directly.`);
    }

    // If we got JSON, parse it
    const result = JSON.parse(responseText);
    setPrediction(result);

  } catch (err: any) {
    console.error('🔍 Full error details:', err);
    setError(err.message);
  } finally {
    setLoading(false);
  }
};

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      padding: '2rem 1rem'
    }}>
      <div style={{
        maxWidth: '900px',
        margin: '0 auto'
      }}>
        <div style={{
          background: 'white',
          padding: '1rem 1.5rem',
          borderRadius: '8px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
          marginBottom: '2rem'
        }}>
          <h1 style={{ margin: 0, fontSize: '1.5rem', color: '#333' }}>
            PSA Match Predictor
          </h1>
        </div>

        <PredictionForm onSubmit={handlePrediction} loading={loading} />

        {error && (
          <div style={{
            background: 'white',
            padding: '1.5rem',
            borderRadius: '8px',
            boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
            marginBottom: '2rem',
            border: '2px solid #f44336',
            color: '#c33'
          }}>
            <strong>Error:</strong> {error}
          </div>
        )}

        {prediction && (
          <>
            <MetaBlock
              event={prediction.event}
              rankingA={prediction.ranking.A}
              rankingB={prediction.ranking.B}
              playerA={prediction.playerA}
              playerB={prediction.playerB}
            />
            <ResultCard result={prediction} />
          </>
        )}
      </div>
    </div>
  );
}