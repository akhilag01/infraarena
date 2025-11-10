from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Minimal FastAPI test"}

@app.get("/health")
def health():
    return {"status": "healthy"}

# Export for Vercel
from mangum import Mangum
handler = Mangum(app, lifespan="off")
