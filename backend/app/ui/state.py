import flet as ft


# backend/app/ui/state.py

API_BASE_URL = "https://ayutech-v2.onrender.com/api/v1"

# Global App State
cart = {}      # {id: {name, price, qty, image}}
wishlist = {}  # {id: {name, price, image}}
all_products = []
current_category = "All"
my_orders = []


all_products = [
    {"id": "1", "name": "5-Speed Gearbox Assembly", "price": 65000, "category": "Gear Parts", "image_url": ""},
    {"id": "2", "name": "Air Cleaner Housing 1KD Diesel", "price": 4500, "category": "Engine Parts", "image_url": ""},
    {"id": "3", "name": "Brake Lining 7L VBL", "price": 2500, "category": "Brake Parts", "image_url": ""},
    {"id": "4", "name": "Ceramic Front Brake Pads", "price": 4500, "category": "Brake Parts", "image_url": ""}
]

user_info = {
    "name": "Erickson",
    "email": "erickson@gmail.com",
    "phone": "0712345678"
}

API_BASE_URL = "http://127.0.0.1:8000/api/v1"