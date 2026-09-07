# Rate Matrix for Nairobi & Environs (KES)[cite: 5]
DELIVERY_RATES = {
    "cbd": 200,
    "kirinyaga road": 0,
    "westlands": 300,
    "kilimani": 300,
    "upper hill": 300,
    "eastleigh": 250,
    "industrial area": 300,
    "parklands": 300,
    "thika road": 400,
    "kasarani": 400,
    "roysambu": 400,
    "ngong road": 350,
    "karen": 500,
    "ruaka": 450,
    "kitengela": 700,
    "ruiru": 600,
}

def calculate_delivery_fee(location_text: str) -> str:
    """Matches customer location against local rate matrix[cite: 5]."""
    if not location_text:
        return "Delivery pricing depends on your exact location in Nairobi."

    loc_lower = location_text.lower()
    for area, rate in DELIVERY_RATES.items():
        if area in loc_lower:
            if rate == 0:
                return "Free pickup available directly at our Kirinyaga Road store!"
            return f"Delivery to {area.title()} is KES {rate} via local courier."

    return "Delivery within Nairobi ranges between KES 200 - KES 500 depending on exact distance from Kirinyaga Road."