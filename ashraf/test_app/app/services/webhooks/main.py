from datetime import datetime, timezone
from uuid import uuid4
import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app=FastAPI(title="Webhook Delivery Service")
VENDORS_URL=os.getenv("VENDORS_URL","http://127.0.0.1:8103")
deliveries=[]
class Webhook(BaseModel):
    event:str
    resource_id:str
    endpoint:str=Field(default="https://merchant.example.test/webhooks", max_length=255)
    vendor_id:str

@app.get("/health")
def health(): return {"status":"ok", "service":"webhooks"}

@app.post("/webhooks/deliver", status_code=202)
async def deliver(data:Webhook):
    try:
        async with httpx.AsyncClient(base_url=VENDORS_URL,timeout=3) as client:
            vendor=await client.get(f"/vendors/{data.vendor_id}"); vendor.raise_for_status()
    except httpx.HTTPError as exc: raise HTTPException(503,"Vendor webhook configuration is unavailable") from exc
    item={"id":"whd_"+uuid4().hex[:10], **data.model_dump(), "status":"queued", "attempt":1,
          "created_at":datetime.now(timezone.utc).isoformat()}
    deliveries.append(item); return item

@app.get("/webhooks/deliveries")
def list_deliveries(): return {"deliveries":deliveries,"count":len(deliveries)}
