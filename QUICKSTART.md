# PSA Match Predictor - Quick Start Guide

## What You Get

A complete, production-ready PSA squash match prediction web application with:
- Real-time data fetching from PSA sources
- Ranking-aware ML model (never 50/50 for unequal ranks)
- Secure authentication
- Docker deployment ready
- React frontend with clean UI

## 5-Minute Local Test

```bash
# 1. Start backend
cd backend
pip install -r requirements.txt
python app.py
# Backend runs on http://localhost:8000

# 2. In new terminal, start frontend
cd frontend
npm install
npm run dev
# Frontend runs on http://localhost:5173

# 3. Test API directly
curl "http://localhost:8000/api/predict?playerA=Ali%20Farag&playerB=Paul%20Coll"

# 4. Open browser
# Go to http://localhost:5173
# Login: guest / squash2025!
```

## Production Deploy (Cloudflare Tunnel)

```bash
# 1. Get Cloudflare Tunnel token
# - Sign up at cloudflare.com
# - Go to Zero Trust > Access > Tunnels
# - Create tunnel, copy token

# 2. Configure
cd deploy
cp .env.example .env
nano .env  # Add your TUNNEL_TOKEN and domain

# 3. Build frontend
cd ../frontend
npm install
npm run build

# 4. Deploy
cd ../deploy
docker compose up -d --build

# 5. Access at your domain
# Login: guest / squash2025!
```

## Project Structure

```
psa-predictor/
├── backend/           # Python FastAPI backend
│   ├── app.py        # Main application
│   ├── predict/      # Prediction logic
│   └── auth/         # Authentication
├── frontend/         # React TypeScript frontend
│   └── src/          # Components and pages
├── deploy/           # Docker deployment
│   ├── docker-compose.yml
│   └── nginx.conf
└── README*.md        # Documentation
```

## Key Features

### Backend API
- `GET /api/health` - Health check
- `GET /api/predict` - Get match prediction
  - Query params: playerA, playerB, event_date (optional), no_cache, seed

### Model Guarantees
- **Never 50/50**: Unequal ranks always show clear favorite
- **Critical Test**: Top-3 vs #180 → Favorite ≥85%, Underdog ≤15%
- **Ranking Tiers**: 6-tier system (T1: 1-5, T2: 6-20, etc.)
- **Evidence Blending**: Combines ranking prior with Elo, form, H2H

### Security
- Password auth with Argon2id hashing
- Rate limiting on login (20/min, lockout after 6 fails)
- HttpOnly session cookies
- HTTPS via Cloudflare Tunnel or Caddy

## Common Use Cases

### 1. Simple Prediction
```bash
curl "http://localhost:8000/api/predict?playerA=Ali%20Farag&playerB=Paul%20Coll"
```

### 2. With Tournament Context
```bash
curl "http://localhost:8000/api/predict?playerA=Ali%20Farag&playerB=Paul%20Coll&event_date=2025-11-15"
```

### 3. Fresh Data (Bypass Cache)
```bash
curl "http://localhost:8000/api/predict?playerA=Ali%20Farag&playerB=Paul%20Coll&no_cache=true"
```

## Troubleshooting

### "Player not found"
- Check spelling (use exact PSA names)
- Try variations: "Mohamed ElShorbagy" or "Mohammed Elshorbagy"
- Known players in aliases: Ali Farag, Paul Coll, Nour El Sherbini

### Backend won't start
```bash
cd backend
pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

### Frontend shows blank page
```bash
cd frontend
rm -rf node_modules dist
npm install
npm run build
```

### Docker deployment issues
```bash
# Check logs
docker compose logs -f

# Rebuild from scratch
docker compose down -v
docker compose up -d --build
```

## Next Steps

1. **Change Password**: See README_DEPLOY.md for generating new Argon2id hash
2. **Customize**: Edit components in `frontend/src/components/`
3. **Add Data Sources**: Extend `backend/predict/fetch.py`
4. **Tune Model**: Adjust tiers/weights in `backend/predict/model.py`

## Testing

Run the critical test to verify model behavior:
```bash
cd backend
python tests/test_model.py
```

Should output:
```
✓ Critical test passed: Hapers 0.120 vs Farag 0.880
✓ All tests passed!
```

## Documentation

- `README.md` - Full project documentation
- `README_DEPLOY.md` - Detailed deployment guide
- API docs: http://localhost:8000/docs (when backend running)

## Default Credentials

**Username**: `guest`  
**Password**: `squash2025!`

⚠️ Change these for production! See README_DEPLOY.md

## Support

- Check logs: `docker compose logs -f`
- API health: `curl http://localhost:8000/api/health`
- Clear cache: `rm -rf backend/predict/.cache/psa/*`

---

**Ready to predict?** Start with the 5-minute local test above! 🎾
