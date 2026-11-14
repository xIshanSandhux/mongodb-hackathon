from uuid import uuid4
from fastapi import FastAPI
from pydantic import BaseModel, EmailStr, Field

app = FastAPI(title="Customer Service")
records = {}

class VerifyRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone: str | None = None

@app.get("/health")
def health(): return {"status": "ok", "service": "customers"}

@app.post("/customers/verify")
def verify(data: VerifyRequest):
    key = str(data.email).lower()
    item = records.setdefault(key, {"customer_id": "cus_" + uuid4().hex[:10], "name": data.name.strip(), "email": key, "phone": data.phone})
    return item

@app.get("/customers")
def list_customers(q: str | None = None):
    values = list(records.values())
    if q: values = [c for c in values if q.casefold() in c["name"].casefold() or q.casefold() in c["email"]]
    return {"customers": values, "count": len(values)}

@app.get("/customers/lookup")
def lookup(email: EmailStr):
    item = records.get(str(email).lower())
    if not item: return {"customer_id": None, "email":str(email).lower()}
    return item
