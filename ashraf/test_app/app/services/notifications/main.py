from datetime import datetime, timezone
import os
from uuid import uuid4
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr

app = FastAPI(title="Notification Service")
CUSTOMERS_URL = os.getenv("CUSTOMERS_URL", "http://127.0.0.1:8102")
events = []
class Notice(BaseModel):
    payment_id: str
    customer_email: EmailStr
    event: str

@app.get("/health")
def health(): return {"status":"ok", "service":"notifications"}

@app.post("/notifications", status_code=202)
async def notify(data: Notice):
    try:
        async with httpx.AsyncClient(base_url=CUSTOMERS_URL, timeout=3) as client:
            customer = await client.get("/customers/lookup", params={"email":str(data.customer_email)})
            customer.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Notification recipient could not be verified") from exc
    event = {"id":"evt_"+uuid4().hex[:10], **data.model_dump(), "created_at":datetime.now(timezone.utc).isoformat(), "delivery":"simulated"}
    events.append(event)
    return event

@app.get("/notifications")
def list_events(): return {"events":events, "count":len(events)}
