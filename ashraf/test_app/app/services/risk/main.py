from datetime import datetime, timezone
import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Risk and Authorization Service")
VENDORS_URL = os.getenv("VENDORS_URL", "http://127.0.0.1:8103")
class Authorization(BaseModel):
    amount: float = Field(gt=0, le=100000)
    currency: str
    card_number: str | None = None
    vendor_id: str

def decision_for(card_number: str | None) -> dict:
    declined = bool(card_number and card_number.endswith("0002"))
    return {"decision":"declined" if declined else "approved", "code":"generic_decline" if declined else "approved"}

@app.get("/health")
def health(): return {"status":"ok", "service":"risk"}

@app.post("/risk/authorize")
async def authorize(data: Authorization):
    try:
        async with httpx.AsyncClient(base_url=VENDORS_URL, timeout=3) as client:
            vendor = await client.get(f"/vendors/{data.vendor_id}")
            vendor.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Vendor validation is unavailable") from exc
    return {**decision_for(data.card_number), "vendor_id":vendor.json()["id"], "checked_at":datetime.now(timezone.utc).isoformat()}
