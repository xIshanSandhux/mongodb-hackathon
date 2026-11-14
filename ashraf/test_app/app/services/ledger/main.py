from datetime import datetime, timezone
import os
from uuid import uuid4
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Ledger Service")
PAYMENTS_URL = os.getenv("PAYMENTS_URL", "http://127.0.0.1:8101")
entries = []
class Entry(BaseModel):
    payment_id: str
    amount: float = Field(gt=0)
    currency: str
    type: str
    status: str

@app.get("/health")
def health(): return {"status":"ok", "service":"ledger"}

@app.post("/ledger/entries", status_code=201)
async def create_entry(data: Entry):
    try:
        async with httpx.AsyncClient(base_url=PAYMENTS_URL, timeout=3) as client:
            payment = await client.get(f"/payments/{data.payment_id}")
            payment.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Ledger could not verify the payment") from exc
    item = {"id":"led_"+uuid4().hex[:10], **data.model_dump(), "created_at":datetime.now(timezone.utc).isoformat()}
    entries.append(item)
    return item

@app.get("/ledger/entries")
def list_entries(payment_id: str | None = None):
    result = [e for e in entries if not payment_id or e["payment_id"] == payment_id]
    return {"entries":result, "count":len(result)}
