# backend/app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.endpoints import (
    admin,
    orders,
    payments,
    products,
    whatsapp,
    ai
)

app = FastAPI(
    title="AyuTech Motors API",
    version="2.0.0",
    description="Backend services for Ayutech Motors Limited e-commerce and store operations."
)

# Enable CORS for local Flet client and web portals
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Endpoints
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin Portal"])
app.include_router(orders.router, prefix="/api/v1/orders", tags=["Customer Orders"])
app.include_router(payments.router, prefix="/api/v1/payments", tags=["M-Pesa Daraja"])
app.include_router(products.router, prefix="/api/v1/products", tags=["Product Catalog"])
app.include_router(whatsapp.router, prefix="/api/v1/whatsapp", tags=["WhatsApp Automation"])
app.include_router(ai.router, prefix="/api/v1/ai", tags=["AI Assistant"])
from app.routers import auth
app.include_router(auth.router, prefix="/api/v1", tags=["Auth"])
@app.get("/")
def root():
    return {
        "service": "AyuTech Motors API",
        "status": "Online",
        "version": "2.0.0"
    }
@app.get("/health", status_code=200)
@app.head("/health", status_code=200)
async def health_check():
    return "ok"
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)