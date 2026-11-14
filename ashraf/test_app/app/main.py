"""API gateway for the PayFlow microservices demo."""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from app.dependency_graph import SERVICE_DEPENDENTS

WEB_DIR = Path(__file__).parent / "static"
URLS = {
    "payments": os.getenv("PAYMENTS_URL", "http://127.0.0.1:8101"),
    "customers": os.getenv("CUSTOMERS_URL", "http://127.0.0.1:8102"),
    "vendors": os.getenv("VENDORS_URL", "http://127.0.0.1:8103"),
    "risk": os.getenv("RISK_URL", "http://127.0.0.1:8104"),
    "ledger": os.getenv("LEDGER_URL", "http://127.0.0.1:8105"),
    "notifications": os.getenv("NOTIFICATIONS_URL", "http://127.0.0.1:8106"),
    "reporting": os.getenv("REPORTING_URL", "http://127.0.0.1:8107"),
    "fx": os.getenv("FX_URL", "http://127.0.0.1:8108"),
    "fraud": os.getenv("FRAUD_URL", "http://127.0.0.1:8109"),
    "idempotency": os.getenv("IDEMPOTENCY_URL", "http://127.0.0.1:8110"),
    "settlement": os.getenv("SETTLEMENT_URL", "http://127.0.0.1:8111"),
    "disputes": os.getenv("DISPUTES_URL", "http://127.0.0.1:8112"),
    "webhooks": os.getenv("WEBHOOKS_URL", "http://127.0.0.1:8113"),
    "audit": os.getenv("AUDIT_URL", "http://127.0.0.1:8114"),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.clients = {name: httpx.AsyncClient(base_url=url, timeout=4.0) for name, url in URLS.items()}
    yield
    for client in app.state.clients.values():
        await client.aclose()


app = FastAPI(title="PayFlow API Gateway", description="Gateway for mock payment microservices", version="2.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


class PaymentRequest(BaseModel):
    order_id: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    customer_name: str = Field(min_length=2, max_length=100)
    customer_email: EmailStr
    customer_phone: str | None = Field(default=None, max_length=24)
    amount: Decimal = Field(gt=0, le=100000)
    currency: str = Field(default="USD", pattern="^(USD|CAD|EUR)$")
    vendor: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=240)
    payment_method: str = Field(default="card", pattern="^(card|bank_transfer)$")
    capture_method: str = Field(default="automatic", pattern="^(automatic|manual)$")
    card_number: str | None = None
    card_exp_month: int | None = Field(default=None, ge=1, le=12)
    card_exp_year: int | None = Field(default=None, ge=2026, le=2045)
    card_cvc: str | None = None
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=120)

    @field_validator("amount")
    @classmethod
    def cents_precision(cls, value):
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("amount must have at most two decimal places")
        return value

    @field_validator("card_number")
    @classmethod
    def only_valid_test_pan(cls, value):
        if value:
            digits = "".join(char for char in value if char.isdigit())
            if not 12 <= len(digits) <= 19:
                raise ValueError("card number must contain 12 to 19 digits")
            checksum = sum((d * 2 - 9 if d * 2 > 9 else d * 2) if i % 2 else d
                           for i, d in enumerate(map(int, reversed(digits))))
            if checksum % 10:
                raise ValueError("card number checksum is invalid")
            value = digits
        return value

    @field_validator("card_cvc")
    @classmethod
    def valid_cvc(cls, value):
        if value is not None and (not value.isdigit() or len(value) not in (3, 4)):
            raise ValueError("security code must be 3 or 4 digits")
        return value

    @model_validator(mode="after")
    def card_details_are_consistent(self):
        details = (self.card_number, self.card_exp_month, self.card_exp_year, self.card_cvc)
        if self.payment_method == "bank_transfer" and any(details):
            raise ValueError("card details must be omitted for bank transfer")
        if self.payment_method == "card" and self.card_number:
            if not all((self.card_exp_month, self.card_exp_year, self.card_cvc)):
                raise ValueError("card expiry and security code are required with a card number")
            current = datetime.now(timezone.utc)
            if (self.card_exp_year, self.card_exp_month) < (current.year, current.month):
                raise ValueError("card has expired")
        elif self.payment_method == "card" and any(details[1:]):
            raise ValueError("expiry and security code require a card number")
        return self


async def call(service: str, method: str, path: str, **kwargs):
    try:
        response = await app.state.clients[service].request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        raise HTTPException(503, f"{service.title()} service is unavailable") from exc
    if response.status_code >= 400:
        detail = response.json().get("detail", f"{service.title()} request failed")
        raise HTTPException(response.status_code, detail)
    return response.json()


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/health")
async def health():
    status = {}
    for name in URLS:
        try:
            result = await call(name, "GET", "/health")
            status[name] = result["status"]
        except HTTPException:
            status[name] = "unavailable"
    return {"status": "ok" if all(value == "ok" for value in status.values()) else "degraded", "services": status}


@app.get("/api/dependencies")
def service_dependencies():
    return {"dependents": {name: sorted(targets) for name, targets in SERVICE_DEPENDENTS.items()}}


@app.get("/api/payments")
async def list_payments(status: str | None = None, vendor: str | None = None, q: str | None = None,
                        limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0)):
    params = {key: value for key, value in {"status": status, "vendor": vendor, "q": q, "limit": limit, "offset": offset}.items() if value is not None}
    return await call("payments", "GET", "/payments", params=params)


@app.get("/api/payments/{payment_id}")
async def get_payment(payment_id: str):
    return await call("payments", "GET", f"/payments/{payment_id}")


@app.post("/api/payments", status_code=201)
async def create_payment(request: PaymentRequest):
    payload = request.model_dump(mode="json")
    payload["idempotency_key"] = payload["idempotency_key"] or "idem_" + uuid4().hex
    fingerprint_data = {key:value for key,value in payload.items() if key not in {"card_number","card_cvc","idempotency_key"}}
    fingerprint = sha256(repr(sorted(fingerprint_data.items())).encode()).hexdigest()
    reservation = await call("idempotency", "POST", "/idempotency/reserve", json={"key":payload["idempotency_key"], "request_fingerprint":fingerprint})
    if reservation.get("replayed") and reservation.get("payment_id"):
        return await call("payments", "GET", f"/payments/{reservation['payment_id']}")
    # Orchestrate validations across bounded services before creating the payment.
    customer = await call("customers", "POST", "/customers/verify", json={
        "name": payload["customer_name"], "email": payload["customer_email"], "phone": payload["customer_phone"]})
    vendor = await call("vendors", "GET", "/vendors/resolve", params={"name": payload["vendor"]})
    fx = await call("fx", "GET", "/fx/quote", params={"amount":float(payload["amount"]), "currency":payload["currency"]})
    fraud = await call("fraud", "POST", "/fraud/screen", json={"amount":float(payload["amount"]), "currency":payload["currency"],
        "customer_email":payload["customer_email"], "card_last4":(payload["card_number"] or "")[-4:] or None, "vendor_id":vendor["id"]})
    risk = await call("risk", "POST", "/risk/authorize", json={
        "amount": float(payload["amount"]), "currency": payload["currency"], "card_number": payload["card_number"], "vendor_id": vendor["id"]})
    payload.update(customer_id=customer["customer_id"], vendor_id=vendor["id"], risk_decision=risk["decision"],
                   fraud_decision=fraud["decision"], fraud_score=fraud["score"], fx_quote=fx)
    payment = await call("payments", "POST", "/payments", json=payload)
    await call("ledger", "POST", "/ledger/entries", json={"payment_id": payment["id"], "amount": payment["amount"],
        "currency": payment["currency"], "type": "charge", "status": payment["status"]})
    await call("notifications", "POST", "/notifications", json={"payment_id": payment["id"],
        "customer_email": payment["customer_email"], "event": "payment." + payment["status"]})
    if payment["status"] == "succeeded":
        await call("settlement", "POST", "/settlements", json={"payment_id":payment["id"],"amount":fx["settlement_amount"],
            "currency":fx["settlement_currency"],"vendor_id":vendor["id"],"status":"pending"})
    await call("webhooks", "POST", "/webhooks/deliver", json={"event":"payment."+payment["status"],"resource_id":payment["id"],"vendor_id":vendor["id"]})
    await call("audit", "POST", "/audit/events", json={"action":"payment.created","resource_type":"payment","resource_id":payment["id"],
        "details":{"vendor_id":vendor["id"],"risk":risk["decision"],"fraud":fraud["decision"]}})
    await call("idempotency", "POST", f"/idempotency/{payload['idempotency_key']}/complete", json={"payment_id":payment["id"]})
    return payment


@app.post("/api/payments/{payment_id}/capture")
async def capture_payment(payment_id: str):
    payment = await call("payments", "POST", f"/payments/{payment_id}/capture")
    await call("ledger", "POST", "/ledger/entries", json={"payment_id": payment_id, "amount": payment["amount"],
        "currency": payment["currency"], "type": "capture", "status": payment["status"]})
    await call("notifications", "POST", "/notifications", json={"payment_id": payment_id,
        "customer_email": payment["customer_email"], "event": "payment.captured"})
    return payment


@app.post("/api/payments/{payment_id}/refund")
async def refund_payment(payment_id: str, payload: dict | None = None):
    payment = await call("payments", "POST", f"/payments/{payment_id}/refund", json=payload or {})
    await call("ledger", "POST", "/ledger/entries", json={"payment_id": payment_id,
        "amount": payment["refunded_amount"], "currency": payment["currency"], "type": "refund", "status": payment["status"]})
    await call("notifications", "POST", "/notifications", json={"payment_id": payment_id,
        "customer_email": payment["customer_email"], "event": "payment.refunded"})
    return payment


@app.get("/api/vendors")
async def vendors():
    return await call("vendors", "GET", "/vendors")


@app.get("/api/customers")
async def customers(q: str | None = None):
    return await call("customers", "GET", "/customers", params={"q": q} if q else {})


@app.get("/api/dashboard/summary")
async def dashboard_summary():
    return await call("reporting", "GET", "/reports/summary")


@app.get("/api/ledger")
async def ledger(payment_id: str | None = None):
    return await call("ledger", "GET", "/ledger/entries", params={"payment_id": payment_id} if payment_id else {})


@app.get("/api/disputes")
async def disputes(payment_id: str | None = None):
    return await call("disputes", "GET", "/disputes", params={"payment_id":payment_id} if payment_id else {})


@app.post("/api/disputes", status_code=201)
async def open_dispute(payload: dict):
    dispute = await call("disputes", "POST", "/disputes", json=payload)
    await call("audit", "POST", "/audit/events", json={"action":"dispute.opened","resource_type":"dispute","resource_id":dispute["id"]})
    await call("webhooks", "POST", "/webhooks/deliver", json={"event":"dispute.opened","resource_id":dispute["id"],"vendor_id":payload.get("vendor_id","ven_acme")})
    return dispute
