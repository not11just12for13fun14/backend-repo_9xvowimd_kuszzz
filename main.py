import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import create_document, get_documents, db
from schemas import Product as ProductSchema, Order as OrderSchema, OrderItem as OrderItemSchema

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProductOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    price: float
    category: str
    in_stock: bool
    image: Optional[str] = None
    rating: Optional[float] = None


class OrderOut(BaseModel):
    id: str
    total: float


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        # Check db object from database.py
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response


# Utility: convert Mongo document to API-friendly dict
from bson import ObjectId

def serialize_doc(doc: dict) -> dict:
    d = doc.copy()
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    # Coerce rating to float if present
    if "rating" in d and d["rating"] is not None:
        d["rating"] = float(d["rating"])
    return d


# Seed data used when the product collection is empty (first run convenience)
SEED_PRODUCTS: List[ProductSchema] = [
    ProductSchema(
        title="AeroMesh Sneakers",
        description="Breathable, lightweight trainers for all-day comfort",
        price=129.0,
        category="shoes",
        in_stock=True,
        image="https://images.unsplash.com/photo-1542291026-7eec264c27ff?q=80&w=1200&auto=format&fit=crop",
        rating=4.7,
    ),
    ProductSchema(
        title="Minimalist Backpack",
        description="Slim, water-resistant pack with padded laptop sleeve",
        price=89.0,
        category="bags",
        in_stock=True,
        image="https://images.unsplash.com/photo-1517433670267-08bbd4be890f?q=80&w=1200&auto=format&fit=crop",
        rating=4.6,
    ),
    ProductSchema(
        title="Supima Tee",
        description="Ultra-soft premium cotton crew neck",
        price=39.0,
        category="apparel",
        in_stock=True,
        image="https://images.unsplash.com/photo-1512436991641-6745cdb1723f?q=80&w=1200&auto=format&fit=crop",
        rating=4.6,
    ),
    ProductSchema(
        title="Smartwatch Pro",
        description="Fitness + notifications with 7-day battery",
        price=199.0,
        category="wearables",
        in_stock=True,
        image="https://images.unsplash.com/photo-1524805444758-089113d48a6d?q=80&w=1200&auto=format&fit=crop",
        rating=4.5,
    ),
]


@app.get("/api/products", response_model=List[ProductOut])
def list_products(limit: Optional[int] = Query(default=20, ge=1, le=100)):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    # Seed if empty for a smooth first-run experience
    count = db["product"].count_documents({})
    if count == 0:
        for p in SEED_PRODUCTS:
            create_document("product", p)

    docs = get_documents("product", {}, limit=limit)
    return [ProductOut(**serialize_doc(doc)) for doc in docs]


@app.post("/api/orders", response_model=OrderOut, status_code=201)
def create_order(order: OrderSchema):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    # Server-side total calculation to avoid trusting client totals
    subtotal = sum(item.price * item.quantity for item in order.items)
    shipping = max(0.0, float(order.shipping)) if order.shipping is not None else 0.0
    total = round(subtotal + shipping, 2)

    order_doc = order.model_dump()
    order_doc["subtotal"] = round(subtotal, 2)
    order_doc["shipping"] = round(shipping, 2)
    order_doc["total"] = total

    new_id = create_document("order", order_doc)
    return OrderOut(id=new_id, total=total)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
