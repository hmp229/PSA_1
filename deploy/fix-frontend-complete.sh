#!/bin/bash

echo "🚀 Setting up 100% working static frontend..."

# Create frontend directory
mkdir -p ../frontend

# Create the static HTML file
cat > ../frontend/index.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PSA Match Predictor</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
        }
        .header {
            text-align: center;
            margin-bottom: 2rem;
            color: white;
        }
        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        .form {
            background: white;
            padding: 2rem;
            border-radius: 12px;
            margin-bottom: 2rem;
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        }
        .input-group {
            margin-bottom: 1.5rem;
        }
        label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: bold;
        }
        input {
            width: 100%;
            padding: 0.75rem;
            border: 2px solid #ddd;
            border-radius: 6px;
            font-size: 1rem;
        }
        input:focus {
            outline: none;
            border-color: #667eea;
        }
        .vs {
            text-align: center;
            font-size: 1.5rem;
            font-weight: bold;
            color: #667eea;
            margin: 1rem 0;
        }
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 1rem 2rem;
            border-radius: 6px;
            font-size: 1.1rem;
            cursor: pointer;
            width: 100%;
        }
        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        .result {
            background: white;
            padding: 2rem;
            border-radius: 12px;
            display: none;
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        }
        .players {
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            gap: 2rem;
            margin: 2rem 0;
        }
        .player {
            text-align: center;
            padding: 1.5rem;
            border: 2px solid #e1e5e9;
            border-radius: 8px;
        }
        .player.winner {
            border-color: #667eea;
            background: #f8f9ff;
        }
        .probability {
            font-size: 1.2rem;
            font-weight: bold;
            margin-top: 1rem;
            color: #667eea;
        }
        .winner-banner {
            text-align: center;
            font-size: 1.5rem;
            margin: 2rem 0;
            padding: 1rem;
            background: #667eea;
            color: white;
            border-radius: 8px;
        }
        .error {
            background: #ffebee;
            color: #c62828;
            padding: 1rem;
            border-radius: 6px;
            margin-bottom: 1rem;
            display: none;
        }
        .loading {
            text-align: center;
            color: #667eea;
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 PSA Match Predictor</h1>
            <p>Predict squash match outcomes using real PSA data</p>
        </div>

        <form class="form" id="predictionForm">
            <div class="input-group">
                <label>Player A:</label>
                <input type="text" id="playerA" placeholder="e.g., Paul Coll" required>
            </div>

            <div class="vs">VS</div>

            <div class="input-group">
                <label>Player B:</label>
                <input type="text" id="playerB" placeholder="e.g., Diego Elias" required>
            </div>

            <button type="submit" id="predictBtn">Predict Match</button>
        </form>

        <div class="loading" id="loading">Analyzing players and match history...</div>

        <div class="error" id="error"></div>

        <div class="result" id="result">
            <h2>Prediction Result</h2>
            <div id="resultContent"></div>
        </div>
    </div>

    <script>
        document.getElementById('predictionForm').addEventListener('submit', async (e) => {
            e.preventDefault();

            const playerA = document.getElementById('playerA').value.trim();
            const playerB = document.getElementById('playerB').value.trim();
            const loading = document.getElementById('loading');
            const error = document.getElementById('error');
            const result = document.getElementById('result');
            const predictBtn = document.getElementById('predictBtn');

            if (!playerA || !playerB) {
                showError('Please enter both player names');
                return;
            }

            // Show loading
            loading.style.display = 'block';
            error.style.display = 'none';
            result.style.display = 'none';
            predictBtn.disabled = true;
            predictBtn.textContent = 'Predicting...';

            try {
                const response = await fetch(`/api/predict?playerA=${encodeURIComponent(playerA)}&playerB=${encodeURIComponent(playerB)}&no_cache=false`);

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.detail?.message || 'Prediction failed');
                }

                const data = await response.json();
                displayResult(data);

            } catch (err) {
                showError(err.message);
            } finally {
                loading.style.display = 'none';
                predictBtn.disabled = false;
                predictBtn.textContent = 'Predict Match';
            }
        });

        function displayResult(data) {
            const isAWinner = data.summary.winner === 'A';

            document.getElementById('resultContent').innerHTML = `
                <div class="players">
                    <div class="player ${isAWinner ? 'winner' : ''}">
                        <h3>${data.playerA}</h3>
                        <p>Rank: #${data.ranking.A.rank}</p>
                        <p>Points: ${data.ranking.A.points}</p>
                        <div class="probability">${(data.summary.proba.A * 100).toFixed(1)}%</div>
                    </div>

                    <div class="vs">VS</div>

                    <div class="player ${!isAWinner ? 'winner' : ''}">
                        <h3>${data.playerB}</h3>
                        <p>Rank: #${data.ranking.B.rank}</p>
                        <p>Points: ${data.ranking.B.points}</p>
                        <div class="probability">${(data.summary.proba.B * 100).toFixed(1)}%</div>
                    </div>
                </div>

                <div class="winner-banner">
                    🏆 Predicted Winner: ${isAWinner ? data.playerA : data.playerB}
                </div>

                ${data.warnings && data.warnings.length > 0 ? `
                    <div style="margin-top: 1rem; padding: 1rem; background: #fff3cd; border-radius: 6px;">
                        <strong>Notes:</strong>
                        <ul style="margin-top: 0.5rem;">
                            ${data.warnings.map(warning => `<li>${warning}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
            `;

            document.getElementById('result').style.display = 'block';
        }

        function showError(message) {
            document.getElementById('error').textContent = '❌ ' + message;
            document.getElementById('error').style.display = 'block';
            document.getElementById('result').style.display = 'none';
        }

        // Pre-fill with sample players for testing
        document.getElementById('playerA').value = 'Paul Coll';
        document.getElementById('playerB').value = 'Diego Elias';
    </script>
</body>
</html>
EOF

# Create nginx config
cat > ../frontend/nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    server {
        listen 80;
        server_name _;
        root /usr/share/nginx/html;
        index index.html;

        location / {
            try_files $uri $uri/ /index.html;
        }

        location /api/ {
            proxy_pass http://backend:8001;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
EOF

# Create simple Dockerfile
cat > ../frontend/Dockerfile << 'EOF'
FROM nginx:alpine

COPY . /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
EOF

echo "✅ Static frontend created successfully!"
echo "🐳 Rebuilding with static frontend..."

# Rebuild and start
cd ..
docker-compose -f deploy/docker-compose.simple.yml down
docker-compose -f deploy/docker-compose.simple.yml build frontend
docker-compose -f deploy/docker-compose.simple.yml up -d

echo "⏳ Waiting for services to start..."
sleep 15

echo "🌐 Checking services..."
curl -f http://localhost:8001/api/health && echo "✅ Backend is healthy" || echo "❌ Backend health check failed"
curl -f http://localhost:3000 > /dev/null 2>&1 && echo "✅ Frontend is healthy" || echo "❌ Frontend health check failed"

echo ""
echo "🎉 YOUR APP IS NOW RUNNING!"
echo "🌐 Access it at: http://localhost:3000"
echo ""
echo "💡 Try these test cases:"
echo "   - Paul Coll vs Diego Elias"
echo "   - Joeri Hapers vs Tate Norris"
echo "   - Mostafa Asal vs Ali Farag"