from pydantic import BaseModel
from typing import List, Optional

class OrderItemSchema(BaseModel):
    product_id: str
    quantity: int
    unit_price: float

class CheckoutRequest(BaseModel):
    customer_name: str
    phone_number: str
    shipping_address: str
    items: List[OrderItemSchema]