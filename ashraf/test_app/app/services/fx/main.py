from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException

app = FastAPI(title="FX Quote Service")
RATES_TO_USD = {"USD": 1.0, "CAD": 0.74, "EUR": 1.08}

@app.get("/health")
def health(): return {"status":"ok", "service":"fx"}

@app.get("/fx/quote")
def quote(amount: float, currency: str):
    if amount <= 0: raise HTTPException(400, "Amount must be positive")
    if currency not in RATES_TO_USD: raise HTTPException(422, "Unsupported settlement currency")
    rate = RATES_TO_USD[currency]
    return {"source_amount":round(amount, 2), "source_currency":currency, "settlement_amount":round(amount * rate, 2),
            "settlement_currency":"USD", "rate":rate, "quoted_at":datetime.now(timezone.utc).isoformat()}
