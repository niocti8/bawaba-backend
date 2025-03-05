from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import csv
import os
from datetime import datetime
from hashlib import sha256
from geopy.geocoders import Nominatim

app = FastAPI()

# CORS setup to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# File setup
VENDORS_FILE = "vendors.csv"
ITEMS_FILE = "items.csv"
ORDERS_FILE = "orders.csv"
UPLOADS_FILE = "uploads.csv"
for file, headers in [
    (VENDORS_FILE, ["vendor_name", "ogo_api_key", "knet_merchant_id", "vendor_wallet", "icon"]),
    (ITEMS_FILE, ["vendor_name", "item_name", "price_kwd", "description"]),
    (ORDERS_FILE, ["order_id", "vendor", "item", "address", "user_wallet", "lat", "lon", "timestamp"]),
    (UPLOADS_FILE, ["order_id", "vendor", "user_wallet", "timestamp", "item", "price_kwd", "category", "icon"])
]:
    if not os.path.exists(file):
        with open(file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
        if file == VENDORS_FILE:
            with open(file, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["FluxEats", "", "sim123", "0xVendor1", "🌌"])
                writer.writerow(["NebulaBites", "", "sim456", "0xVendor2", "☄️"])

def categorize_receipt(vendor):
    vendor = vendor.lower()
    if "mcdonald" in vendor or "burger" in vendor:
        return "Fast Food", "🍔"
    elif "healthy" in vendor or "salad" in vendor or "bowl" in vendor:
        return "Healthy", "🥗"
    else:
        return "Other", "🧾"

class Order(BaseModel):
    wallet_address: str
    vendor_name: str
    item: str
    delivery_address: str

class Receipt(BaseModel):
    wallet_address: str
    order_id: str
    vendor: str
    item: str
    price_kwd: float

@app.get("/vendors")
async def get_vendors():
    vendors = pd.read_csv(VENDORS_FILE).set_index("vendor_name").to_dict("index")
    return vendors

@app.get("/items")
async def get_items():
    items = pd.read_csv(ITEMS_FILE).to_dict("records")
    return items

@app.post("/order")
async def create_order(order: Order):
    if not all([order.wallet_address, order.vendor_name, order.item, order.delivery_address]):
        raise HTTPException(status_code=400, detail="Please fill in all fields")
    if not order.wallet_address.startswith("0x") or len(order.wallet_address) != 42:
        raise HTTPException(status_code=400, detail="Invalid wallet address")
    
    order_id = f"{order.vendor_name}-{sha256(order.item.encode()).hexdigest()[:8]}"
    geolocator = Nominatim(user_agent="bawaba_rewards")
    location = geolocator.geocode(order.delivery_address)
    lat, lon = (location.latitude, location.longitude) if location else (0, 0)
    with open(ORDERS_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([order_id, order.vendor_name, order.item, order.delivery_address, order.wallet_address, lat, lon, datetime.now().isoformat()])
    return {"status": "success", "order_id": order_id, "reward": 210000}

@app.post("/upload")
async def upload_receipt(receipt: Receipt, file: UploadFile = File(None)):
    if not all([receipt.wallet_address, receipt.order_id, receipt.vendor, receipt.item, receipt.price_kwd]):
        raise HTTPException(status_code=400, detail="Please fill in all fields")
    if not receipt.wallet_address.startswith("0x") or len(receipt.wallet_address) != 42:
        raise HTTPException(status_code=400, detail="Invalid wallet address")
    
    category, icon = categorize_receipt(receipt.vendor)
    with open(UPLOADS_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([receipt.order_id, receipt.vendor, receipt.wallet_address, datetime.now().isoformat(), receipt.item, receipt.price_kwd, category, icon])
    return {"status": "success", "reward": 100000}

@app.get("/market")
async def get_market():
    df_uploads = pd.read_csv(UPLOADS_FILE)
    return df_uploads.to_dict("records")
