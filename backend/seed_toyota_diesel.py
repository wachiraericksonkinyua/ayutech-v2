# backend/seed_toyota_diesel.py

from app.db.supabase_client import supabase

toyota_diesel_parts = [
    # 1KD / 2KD D4D Components
    {
        "name": "Toyota 1KD Complete Cylinder Head (Hilux/Prado)",
        "category": "Engine Components",
        "price": 48000.0,
        "stock_quantity": 4,
        "image_url": "https://via.placeholder.com/300x200?text=1KD+Cylinder+Head"
    },
    {
        "name": "Toyota 2KD D4D Turbocharger CT16 (HiAce/Hilux)",
        "category": "Turbo & Induction",
        "price": 28500.0,
        "stock_quantity": 5,
        "image_url": "https://via.placeholder.com/300x200?text=2KD+CT16+Turbo"
    },
    {
        "name": "Toyota 1KD/2KD Fuel Injector Set (Denso OEM)",
        "category": "Fuel System",
        "price": 18500.0,
        "stock_quantity": 8,
        "image_url": "https://via.placeholder.com/300x200?text=1KD+2KD+Injectors"
    },

    # 3L / 5L Naturally Aspirated Diesel Components
    {
        "name": "Toyota 5L Complete Engine Cylinder Head (Hilux/HiAce Shark)",
        "category": "Engine Components",
        "price": 38000.0,
        "stock_quantity": 3,
        "image_url": "https://via.placeholder.com/300x200?text=5L+Cylinder+Head"
    },
    {
        "name": "Toyota 3L/5L Heavy Duty Clutch Kit (Pressure Plate & Disc)",
        "category": "Transmission",
        "price": 14500.0,
        "stock_quantity": 7,
        "image_url": "https://via.placeholder.com/300x200?text=3L+5L+Clutch+Kit"
    },
    {
        "name": "Toyota 5L Full Overhaul Gasket Set (Cherry Gasket)",
        "category": "Engine Components",
        "price": 6500.0,
        "stock_quantity": 12,
        "image_url": "https://via.placeholder.com/300x200?text=5L+Gasket+Kit"
    },

    # 7L / 9L Commercial Gear & Diesel Assemblies
    {
        "name": "Toyota 7L / 9L Diesel Heavy Duty Water Pump",
        "category": "Cooling System",
        "price": 5500.0,
        "stock_quantity": 6,
        "image_url": "https://via.placeholder.com/300x200?text=7L+9L+Water+Pump"
    },
    {
        "name": "Toyota 7L / 9L Diesel Starter Motor 12V/24V",
        "category": "Electrical",
        "price": 12500.0,
        "stock_quantity": 4,
        "image_url": "https://via.placeholder.com/300x200?text=7L+9L+Starter"
    },
    {
        "name": "Toyota 1KD/2KD/5L Timing Belt & Tensioner Kit",
        "category": "Engine Components",
        "price": 7500.0,
        "stock_quantity": 10,
        "image_url": "https://via.placeholder.com/300x200?text=Toyota+Timing+Kit"
    }
]

def run_seed():
    print("Seeding targeted Toyota diesel spare parts into Supabase...")
    for part in toyota_diesel_parts:
        try:
            supabase.table("products").insert(part).execute()
            print(f"Added: {part['name']}")
        except Exception as e:
            print(f"Error inserting {part['name']}: {e}")
    print("Seeding complete.")

if __name__ == "__main__":
    run_seed()