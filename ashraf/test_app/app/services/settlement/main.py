from datetime import datetime, timezone
from uuid import uuid4
import os
import asyncio
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app=FastAPI(title="Settlement Service")
PAYMENTS_URL=os.getenv("PAYMENTS_URL","http://127.0.0.1:8101")
LEDGER_URL=os.getenv("LEDGER_URL","http://127.0.0.1:8105")
settlements=[]
class Settlement(BaseModel):
    payment_id:str
    amount:float=Field(gt=0)
    currency:str
    vendor_id:str
    status:str="pending"

@app.get("/health")
def health(): return {"status":"ok", "service":"settlement"}

@app.post("/settlements", status_code=201)
async def create(data:Settlement):
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            payment, entries = await asyncio.gather(client.get(f"{PAYMENTS_URL}/payments/{data.payment_id}"), client.get(f"{LEDGER_URL}/ledger/entries", params={"payment_id":data.payment_id}))
            payment.raise_for_status(); entries.raise_for_status()
            if payment.json()["status"] not in ("succeeded", "partially_refunded", "refunded"):
                raise HTTPException(409,"Only captured payments can be settled")
            if not entries.json()["count"]: raise HTTPException(409,"Ledger charge entry is required before settlement")
    except httpx.HTTPError as exc: raise HTTPException(503,"Settlement dependencies unavailable") from exc
    item={"id":"set_"+uuid4().hex[:10], **data.model_dump(), "created_at":datetime.now(timezone.utc).isoformat()}
    settlements.append(item); return item

@app.get("/settlements")
def list_settlements(): return {"settlements":settlements, "count":len(settlements)}
