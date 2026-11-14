from datetime import datetime, timezone
from uuid import uuid4
import os
import asyncio
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app=FastAPI(title="Disputes Service")
PAYMENTS_URL=os.getenv("PAYMENTS_URL","http://127.0.0.1:8101")
LEDGER_URL=os.getenv("LEDGER_URL","http://127.0.0.1:8105")
disputes=[]
class Dispute(BaseModel):
    payment_id:str
    reason:str=Field(min_length=3, max_length=120)
    amount:float=Field(gt=0)

@app.get("/health")
def health(): return {"status":"ok", "service":"disputes"}

@app.post("/disputes", status_code=201)
async def open_dispute(data:Dispute):
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            payment, entries = await asyncio.gather(client.get(f"{PAYMENTS_URL}/payments/{data.payment_id}"), client.get(f"{LEDGER_URL}/ledger/entries", params={"payment_id":data.payment_id}))
            payment.raise_for_status(); entries.raise_for_status()
            if data.amount > payment.json()["amount"]: raise HTTPException(400,"Dispute amount exceeds payment amount")
            if not entries.json()["count"]: raise HTTPException(409,"A ledger entry is required to dispute a payment")
    except httpx.HTTPError as exc: raise HTTPException(503,"Dispute dependencies unavailable") from exc
    item={"id":"dsp_"+uuid4().hex[:10], **data.model_dump(), "status":"under_review", "created_at":datetime.now(timezone.utc).isoformat()}
    disputes.append(item); return item

@app.get("/disputes")
def list_disputes(payment_id:str|None=None):
    result=[d for d in disputes if not payment_id or d["payment_id"]==payment_id]
    return {"disputes":result,"count":len(result)}
