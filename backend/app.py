from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "PSA Predictor API", "status": "running"}

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

@app.get("/api/predict")
async def predict_match(
    playerA: str = Query(..., description="Player A name"),
    playerB: str = Query(..., description="Player B name"),
    no_cache: bool = Query(False, description="Bypass cache")
):
    """Simple test endpoint"""
    return {
        "playerA": playerA,
        "playerB": playerB,
        "prediction": f"{playerA} vs {playerB}",
        "probability": 0.75,
        "winner": playerA,
        "no_cache": no_cache,
        "status": "test_mode"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)