# PSA Match Predictor

A real-time squash match prediction system that fetches live data from PSA World Tour and other reputable sources to predict match outcomes using a ranking-aware machine learning model.

## Features

- **Real-time Data**: Fetches player profiles, rankings, match histories, and tournament schedules at runtime
- **Ranking-Aware Model**: Uses tiered ranking priors with evidence blending - never returns 50/50 for unequal ranks
- **Head-to-Head Analysis**: Incorporates recent H2H records with time decay
- **Event Context**: Shows tournament information when event date is provided
- **Confidence Intervals**: Bootstrap-based 95% confidence intervals for predictions
- **Plain English Explanations**: Key prediction drivers explained without technical jargon
- **Polite Scraping**: Respects robots.txt, 24-hour caching, rate limiting (~1 req/sec)
- **Secure Authentication**: Password-protected with Argon2id hashing
- **Docker Deployment**: Easy deployment with Cloudflare Tunnel or Caddy

## Architecture

### Backend
- **Framework**: FastAPI (Python 3.10+)
- **Data Sources**: PSA World Tour, SquashInfo (runtime scraping)
- **Model**: Custom ranking-aware predictor with Elo ratings, recent form, H2H, and fatigue metrics
- **Caching**: 24-hour on-disk cache with configurable bypass
- **Authentication**: Single predefined credential with session cookies

### Frontend
- **Framework**: React 18 + Vite (TypeScript)
- **Features**: Clean UI for predictions, results visualization, event context display
- **Auth Flow**: Login page → Session check → Protected app

### Deployment
- **Docker Compose**: Multi-container setup
- **Options**: Cloudflare Tunnel (recommended) or Caddy with public IP
- **Security**: Rate limiting, login lockout, HTTPS

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Node.js 18+ (for local development)
- Domain name (for Cloudflare Tunnel) or public IP

### Local Development

1. **Backend**
   ```bash
   cd backend
   pip install -r requirements.txt
   python app.py
   # Runs on http://localhost:8000
   ```

2. **Frontend**
   ```bash
   cd frontend
   npm install
   npm run dev
   # Runs on http://localhost:5173
   ```

3. **Test API**
   ```bash
   curl "http://localhost:8000/api/health"
   curl "http://localhost:8000/api/predict?playerA=Ali%20Farag&playerB=Paul%20Coll"
   ```

### Production Deployment

See [README_DEPLOY.md](README_DEPLOY.md) for detailed deployment instructions.

**Quick Deploy:**
```bash
cd frontend && npm install && npm run build
cd ../deploy
cp .env.example .env
# Edit .env with your configuration
docker compose up -d --build
```

**Default Login:**
- Username: `guest`
- Password: `squash2025!`

## API Documentation

### Endpoints

#### GET `/api/health`
Health check endpoint.

**Response:**
```json
{
  "status": "ok"
}
```

#### GET `/api/predict`
Predict match outcome between two players.

**Query Parameters:**
- `playerA` (required): Name of player A
- `playerB` (required): Name of player B
- `event_date` (optional): Event date in YYYY-MM-DD format
- `no_cache` (optional): Set to `true` to bypass cache
- `seed` (optional): Random seed for reproducibility (default: 42)

**Example Request:**
```bash
curl "http://localhost:8000/api/predict?playerA=Ali%20Farag&playerB=Joeri%20Hapers&event_date=2025-11-10"
```

**Example Response:**
```json
{
  "playerA": "Ali Farag",
  "playerB": "Joeri Hapers",
  "resolved": {
    "A": {
      "canonical": "Ali Farag",
      "profile_url": "https://psaworldtour.com/players/ali-farag"
    },
    "B": {
      "canonical": "Joeri Hapers",
      "profile_url": "https://psaworldtour.com/players/joeri-hapers"
    }
  },
  "event": {
    "name": "London Open",
    "location": {
      "city": "London",
      "country": "UK",
      "venue": "—"
    },
    "start_date": "2025-11-10",
    "end_date": "2025-11-15",
    "tier": "Bronze"
  },
  "ranking": {
    "A": {
      "rank": 2,
      "points": 12345,
      "snapshot": "2025-10-01"
    },
    "B": {
      "rank": 180,
      "points": 1234,
      "snapshot": "2025-10-01"
    }
  },
  "summary": {
    "winner": "A",
    "proba": {
      "A": 0.88,
      "B": 0.12
    },
    "ci95": {
      "A": [0.83, 0.92],
      "B": [0.08, 0.17]
    }
  },
  "explain": {
    "drivers": [
      {
        "feature": "Ranking gap",
        "impact": "+ strong",
        "note": "Top-3 vs #180 favors A"
      },
      {
        "feature": "Recent form",
        "impact": "+ mild",
        "note": "A steady vs strong opponents"
      },
      {
        "feature": "Head-to-head",
        "impact": "neutral",
        "note": "No official meetings in 24 months"
      }
    ]
  },
  "sources": [
    "https://psaworldtour.com/players/ali-farag",
    "https://psaworldtour.com/players/joeri-hapers"
  ],
  "warnings": []
}
```

**Error Responses:**

- **400 Player Not Found:**
  ```json
  {
    "error": {
      "code": "PLAYER_NOT_FOUND",
      "message": "Player 'X' not found on PSA-related sources."
    }
  }
  ```

- **400 Player Ambiguous:**
  ```json
  {
    "error": {
      "code": "PLAYER_AMBIGUOUS",
      "message": "Multiple matches; refine query.",
      "suggestions": [
        {
          "name": "Mohamed ElShorbagy",
          "url": "https://..."
        }
      ]
    }
  }
  ```

- **503 Upstream Unavailable:**
  ```json
  {
    "error": {
      "code": "UPSTREAM_UNAVAILABLE",
      "message": "Unable to reach PSA data sources"
    }
  }
  ```

## Model Details

### Ranking Prior
- Uses 6-tier ranking system (1-5, 6-20, 21-50, 51-100, 101-200, 200+)
- Calculates underdog cap based on tier gap
- Never returns 0.5 for clearly unequal ranks

### Evidence Model
- Elo ratings with 180-day time decay
- Recent form (last 20 matches): win rate, game differential
- Opponent strength analysis
- Fatigue metrics (matches in last 14/30 days)

### H2H Integration
- Uses last 24 months of head-to-head matches
- Time-weighted effective sample size
- Bounded effect based on sample quality

### Guardrails
- Large tier gaps (≥3) with weak H2H data are capped
- Override conditions allow exceptions for strong evidence
- Monotonicity: better rank must be favorite

### Critical Test Case
**Joeri Hapers (~#180) vs Ali Farag (top-3), no H2H:**
- Underdog (Hapers) capped at ≤ 0.15
- Favorite (Farag) ≥ 0.85
- Never returns ~0.50

## Project Structure

```
psa-predictor/
├── backend/
│   ├── app.py                 # FastAPI application
│   ├── predict/
│   │   ├── players.py         # Player name resolution
│   │   ├── fetch.py           # Runtime data fetching
│   │   ├── events.py          # Tournament lookup
│   │   ├── features.py        # Feature extraction
│   │   ├── model.py           # Prediction model
│   │   ├── schemas.py         # Pydantic models
│   │   └── cache.py           # Caching system
│   ├── auth/
│   │   ├── baked_credential.py # Auth credentials
│   │   ├── auth_basic.py       # Login/logout
│   │   └── middleware.py       # Auth middleware
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── PredictionForm.tsx
│   │   │   ├── ResultCard.tsx
│   │   │   └── MetaBlock.tsx
│   │   ├── pages/
│   │   │   └── Login.tsx
│   │   ├── lib/
│   │   │   └── auth.ts
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── deploy/
│   ├── docker-compose.yml
│   ├── nginx.conf
│   ├── Caddyfile
│   └── .env.example
├── README.md
└── README_DEPLOY.md
```

## Development

### Adding New Data Sources
1. Add scraping logic to `backend/predict/fetch.py`
2. Update player resolution in `backend/predict/players.py`
3. Respect robots.txt and use polite rate limiting

### Modifying the Model
- Edit `backend/predict/model.py`
- Adjust ranking tiers, evidence weights, or guardrails
- Update tests to verify behavior

### Frontend Customization
- Modify components in `frontend/src/components/`
- Update styling in component style objects
- Add new features to `App.tsx`

## Testing

### Backend Tests
```bash
cd backend
pytest tests/
```

### Critical Test Cases
1. **Unknown player** → 400 PLAYER_NOT_FOUND
2. **Ambiguous player** → 400 with suggestions
3. **Large ranking gap** → Underdog ≤ 0.15 (Hapers vs Farag test)
4. **Event lookup** → Event block present when date provided
5. **Upstream failure** → 503 UPSTREAM_UNAVAILABLE

## Security

- **Authentication**: Argon2id password hashing
- **Rate Limiting**: Configurable login rate limiting and lockout
- **Session Management**: Secure HttpOnly cookies
- **HTTPS**: Automatic with Cloudflare Tunnel or Caddy
- **Input Validation**: Strict player name validation before prediction

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- PSA World Tour for official rankings and tournament data
- SquashInfo for comprehensive match statistics
- Open source community for excellent libraries

## Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check [README_DEPLOY.md](README_DEPLOY.md) for deployment help
- Review API documentation above for usage examples
