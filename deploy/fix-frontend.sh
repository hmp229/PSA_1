#!/bin/bash

echo "🔧 Fixing frontend build issues..."

# Check if frontend directory exists
if [ ! -d "../frontend" ]; then
    echo "❌ Frontend directory not found. Creating basic frontend structure..."
    mkdir -p ../frontend/src
fi

# Create essential frontend files
echo "📁 Creating essential frontend files..."

# Create basic files
cat > ../frontend/package.json << 'EOF'
{
  "name": "psa-predictor-frontend",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "axios": "^1.5.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.1.0",
    "typescript": "^5.0.0",
    "vite": "^4.4.0"
  }
}
EOF

cat > ../frontend/vite.config.ts << 'EOF'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000
  },
  build: {
    outDir: 'dist',
    sourcemap: true
  }
})
EOF

cat > ../frontend/index.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>PSA Match Predictor</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
EOF

# Create src directory structure
mkdir -p ../frontend/src

cat > ../frontend/src/main.tsx << 'EOF'
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
EOF

cat > ../frontend/src/index.css << 'EOF'
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background-color: #f5f5f5;
}
EOF

# Create a simple App component
cat > ../frontend/src/App.tsx << 'EOF'
import React, { useState } from 'react'
import axios from 'axios'
import './App.css'

function App() {
  const [playerA, setPlayerA] = useState('')
  const [playerB, setPlayerB] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const handlePredict = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      const response = await axios.get('/api/predict', {
        params: { playerA, playerB, no_cache: false }
      })
      setResult(response.data)
    } catch (error) {
      console.error('Prediction failed:', error)
      alert('Prediction failed. Check console for details.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
      <h1>🎯 PSA Match Predictor</h1>
      <form onSubmit={handlePredict} style={{ marginBottom: '2rem' }}>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            type="text"
            value={playerA}
            onChange={(e) => setPlayerA(e.target.value)}
            placeholder="Player A"
            style={{ padding: '0.5rem', flex: 1 }}
          />
          <span>VS</span>
          <input
            type="text"
            value={playerB}
            onChange={(e) => setPlayerB(e.target.value)}
            placeholder="Player B"
            style={{ padding: '0.5rem', flex: 1 }}
          />
          <button type="submit" disabled={loading}>
            {loading ? 'Predicting...' : 'Predict'}
          </button>
        </div>
      </form>

      {result && (
        <div style={{ background: 'white', padding: '1rem', borderRadius: '8px' }}>
          <h3>Prediction Result</h3>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}

export default App
EOF

cat > ../frontend/src/App.css << 'EOF'
button {
  padding: 0.5rem 1rem;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

button:disabled {
  background: #6c757d;
  cursor: not-allowed;
}

input {
  border: 1px solid #ddd;
  border-radius: 4px;
}
EOF

echo "✅ Frontend files created successfully!"
echo "🐳 Rebuilding frontend..."

# Rebuild the frontend
cd ..
docker-compose -f deploy/docker-compose.simple.yml build frontend

echo "🚀 Starting services..."
docker-compose -f deploy/docker-compose.simple.yml up -d

echo "⏳ Waiting for services to start..."
sleep 15

echo "🌐 Your app should now be available at: http://localhost:3000"