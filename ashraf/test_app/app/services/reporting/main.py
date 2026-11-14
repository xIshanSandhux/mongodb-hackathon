import os
import httpx
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Reporting Service")
PAYMENTS_URL = os.getenv("PAYMENTS_URL", "http://127.0.0.1:8101")
LEDGER_URL = os.getenv("LEDGER_URL", "http://127.0.0.1:8105")
NOTIFICATIONS_URL = os.getenv("NOTIFICATIONS_URL", "http://127.0.0.1:8106")

@app.get("/health")
def health(): return {"status":"ok", "service":"reporting"}

@app.get("/reports/summary")
async def summary():
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            payments_response, ledger_response, notices_response = await __import__("asyncio").gather(
                client.get(f"{PAYMENTS_URL}/payments", params={"limit":100}),
                client.get(f"{LEDGER_URL}/ledger/entries"),
                client.get(f"{NOTIFICATIONS_URL}/notifications"))
            payments_response.raise_for_status(); ledger_response.raise_for_status(); notices_response.raise_for_status()
            payments = payments_response.json()["payments"]
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Payments service unavailable for report") from exc
    by_status = {status: sum(float(p["amount"]) for p in payments if p["status"] == status)
                 for status in ("succeeded", "processing", "failed", "refunded", "partially_refunded")}
    refunded = sum(float(p.get("refunded_amount", 0)) for p in payments)
    return {"payment_count":len(payments), "successful_volume":round(by_status["succeeded"], 2),
            "refunded_volume":round(refunded, 2), "by_status":by_status,
            "vendors":len({p.get("vendor") for p in payments if p.get("vendor")}),
            "ledger_entries":ledger_response.json()["count"], "notification_events":notices_response.json()["count"]}
