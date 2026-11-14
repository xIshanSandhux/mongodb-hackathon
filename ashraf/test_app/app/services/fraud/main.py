import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Fraud Screening Service")
VENDORS_URL=os.getenv("VENDORS_URL","http://127.0.0.1:8103")
class ScreeningRequest(BaseModel):
    amount: float = Field(gt=0)
    currency: str
    customer_email: str
    card_last4: str | None = None
    vendor_id: str

def assess(data: ScreeningRequest):
    flags=[]; score=0
    if data.amount >= 1000: flags.append("high_amount"); score += 45
    if data.card_last4 == "0002": flags.append("test_decline_card"); score += 100
    if data.customer_email.endswith(".invalid"): flags.append("invalid_email_domain"); score += 80
    decision="review" if score >= 45 else "allow"
    return {"decision":decision, "score":min(score,100), "flags":flags}

@app.get("/health")
def health(): return {"status":"ok", "service":"fraud"}

@app.post("/fraud/screen")
async def screen(data: ScreeningRequest):
    try:
        async with httpx.AsyncClient(base_url=VENDORS_URL,timeout=3) as client:
            vendor=await client.get(f"/vendors/{data.vendor_id}"); vendor.raise_for_status()
    except httpx.HTTPError as exc: raise HTTPException(503,"Merchant context is unavailable for screening") from exc
    return assess(data)
