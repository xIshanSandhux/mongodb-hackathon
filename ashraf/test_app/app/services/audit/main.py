from datetime import datetime, timezone
from uuid import uuid4
from fastapi import FastAPI
from pydantic import BaseModel

app=FastAPI(title="Audit Service")
events=[]
class AuditEvent(BaseModel):
    actor:str="system"
    action:str
    resource_type:str
    resource_id:str
    details:dict|None=None

@app.get("/health")
def health(): return {"status":"ok", "service":"audit"}

@app.post("/audit/events", status_code=201)
def record(data:AuditEvent):
    event={"id":"aud_"+uuid4().hex[:10],**data.model_dump(),"created_at":datetime.now(timezone.utc).isoformat()}
    events.append(event); return event

@app.get("/audit/events")
def list_events(): return {"events":events,"count":len(events)}
