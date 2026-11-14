from fastapi import FastAPI, HTTPException, Query

app = FastAPI(title="Vendor Service")
VENDORS = [{"id":"ven_northstar", "name":"Northstar Goods"}, {"id":"ven_morrow", "name":"Morrow Home"},
           {"id":"ven_juniper", "name":"Juniper Supply"}, {"id":"ven_acme", "name":"Acme Store"}]

@app.get("/health")
def health(): return {"status":"ok", "service":"vendors"}

@app.get("/vendors")
def vendors(): return {"vendors":VENDORS}

@app.get("/vendors/{vendor_id}")
def get_vendor(vendor_id: str):
    result = next((v for v in VENDORS if v["id"] == vendor_id), None)
    if not result: raise HTTPException(404, "Vendor not found")
    return result

@app.get("/vendors/resolve")
def resolve(name: str = Query()):
    result = next((v for v in VENDORS if v["name"].casefold() == name.casefold()), None)
    if not result: raise HTTPException(404, "Vendor not found")
    return result
