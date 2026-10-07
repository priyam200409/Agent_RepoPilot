from fastapi import FastAPI

app = FastAPI(title="RepoPilot API")


@app.get("/api/health")
def health_check():
    return {"status": "ok"}