from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Idempotency Service")
keys={}
class Reservation(BaseModel):
    key: str = Field(min_length=8, max_length=120)
    request_fingerprint: str = Field(min_length=8, max_length=128)

@app.get("/health")
def health(): return {"status":"ok", "service":"idempotency"}

@app.post("/idempotency/reserve")
def reserve(data: Reservation):
    existing=keys.get(data.key)
    if existing:
        if existing["request_fingerprint"] != data.request_fingerprint:
            raise HTTPException(409, "Idempotency key was already used for a different request")
        return {**existing, "replayed":True}
    record={"key":data.key, "request_fingerprint":data.request_fingerprint, "payment_id":None,
            "created_at":datetime.now(timezone.utc).isoformat(), "replayed":False}
    keys[data.key]=record
    return record

@app.post("/idempotency/{key}/complete")
def complete(key: str, payload: dict):
    if key not in keys: raise HTTPException(404, "Idempotency key not reserved")
    keys[key]["payment_id"]=payload.get("payment_id")
    return keys[key]
