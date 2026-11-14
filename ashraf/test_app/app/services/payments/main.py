from datetime import datetime, timezone
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Query

app = FastAPI(title="Payments Service")
now = lambda: datetime.now(timezone.utc).isoformat()
data = {}
seed = [
    ("ord_1048","Maya Chen","maya@example.test",84.50,"succeeded","Northstar Goods","Visa","4242"),
    ("ord_1047","Noah Patel","noah@example.test",129.00,"processing","Morrow Home","Mastercard","1881"),
    ("ord_1046","Ava Martin","ava@example.test",42.25,"refunded","Northstar Goods","Amex","3009"),
    ("ord_1045","Leo Kim","leo@example.test",215.75,"failed","Juniper Supply",None,None),
    ("ord_1044","Isla Brown","isla@example.test",19.99,"succeeded","Morrow Home","Visa","7782"),
]
for i, (order, name, email, amount, status, vendor, brand, last4) in enumerate(seed, 1):
    data[f"pay_demo_{i}"] = {"id":f"pay_demo_{i}", "order_id":order, "customer_name":name,"customer_email":email,
        "amount":amount,"currency":"USD","status":status,"vendor":vendor,"vendor_id":"ven_demo",
        "description":f"Order {order}","payment_method":"card","capture_method":"automatic",
        "card_brand":brand,"card_last4":last4,"card_exp_month":12 if brand else None,"card_exp_year":2028 if brand else None,
        "refunded_amount":amount if status == "refunded" else 0,"created_at":now(),"updated_at":now(),"refunded_at":now() if status == "refunded" else None,
        "failure_code":"generic_decline" if status == "failed" else None}

@app.get("/health")
def health(): return {"status":"ok", "service":"payments"}

@app.get("/payments")
def list_payments(status: str | None = None, vendor: str | None = None, q: str | None = None,
                  limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    values = sorted(data.values(), key=lambda p:p["created_at"], reverse=True)
    if status: values = [p for p in values if p["status"] == status]
    if vendor: values = [p for p in values if p.get("vendor", "").casefold() == vendor.casefold()]
    if q:
        term=q.casefold()
        values=[p for p in values if any(term in str(p.get(k, "")).casefold() for k in ("id","order_id","customer_name","customer_email","vendor"))]
    return {"payments":values[offset:offset+limit],"count":len(values),"limit":limit,"offset":offset}

@app.get("/payments/{payment_id}")
def get_payment(payment_id: str):
    if payment_id not in data: raise HTTPException(404,"Payment not found")
    return data[payment_id]

@app.post("/payments", status_code=201)
def create_payment(payload: dict):
    timestamp=now(); digits=payload.get("card_number") or ""
    status="failed" if payload.get("risk_decision") == "declined" else ("processing" if payload.get("fraud_decision") == "review" or payload["capture_method"] == "manual" else "succeeded")
    brand="Visa" if digits.startswith("4") else "Amex" if digits.startswith(("34","37")) else "Mastercard" if digits.startswith(("51","52","53","54","55")) else "Discover" if digits.startswith(("6011","65")) else "Unknown" if digits else None
    item={"id":"pay_"+uuid4().hex[:12],"order_id":payload["order_id"],"customer_id":payload.get("customer_id"),
        "customer_name":payload["customer_name"],"customer_email":payload["customer_email"],"customer_phone":payload.get("customer_phone"),
        "vendor":payload["vendor"],"vendor_id":payload.get("vendor_id"),"description":payload.get("description") or f"Order {payload['order_id']}",
        "amount":float(payload["amount"]),"currency":payload["currency"],"status":status,"payment_method":payload["payment_method"],
        "capture_method":payload["capture_method"],"card_brand":brand,"card_last4":digits[-4:] if digits else None,
        "card_exp_month":payload.get("card_exp_month"),"card_exp_year":payload.get("card_exp_year"),
        "refunded_amount":0,"refund_reason":None,"failure_code":"generic_decline" if status=="failed" else None,
        "fraud_decision":payload.get("fraud_decision"), "fraud_score":payload.get("fraud_score"),
        "review_reason":"fraud_review" if payload.get("fraud_decision") == "review" else None,
        "fx_quote":payload.get("fx_quote"), "idempotency_key":payload.get("idempotency_key"),
        "created_at":timestamp,"updated_at":timestamp,"refunded_at":None}
    # PAN and CVC are deliberately absent from the stored payment document.
    data[item["id"]]=item
    return item

@app.post("/payments/{payment_id}/capture")
def capture(payment_id: str):
    item=get_payment(payment_id)
    if item["status"]!="processing" or item["capture_method"]!="manual": raise HTTPException(409,"Only manually authorized payments can be captured")
    item.update(status="succeeded",captured_at=now(),updated_at=now()); return item

@app.post("/payments/{payment_id}/refund")
def refund(payment_id: str, payload: dict | None = None):
    item=get_payment(payment_id); payload=payload or {}
    if item["status"] not in ("succeeded","partially_refunded"): raise HTTPException(409,"Only captured payments can be refunded")
    remaining=round(item["amount"]-item["refunded_amount"],2); amount=float(payload.get("amount") or remaining)
    if amount<=0 or amount>remaining: raise HTTPException(400,f"Refund exceeds remaining refundable amount ({remaining:.2f})")
    item["refunded_amount"]=round(item["refunded_amount"]+amount,2)
    item.update(status="refunded" if item["refunded_amount"]>=item["amount"] else "partially_refunded",refund_reason=payload.get("reason","requested_by_customer"),updated_at=now())
    if item["status"]=="refunded": item["refunded_at"]=now()
    return item
