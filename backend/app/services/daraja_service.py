import os
import base64
from datetime import datetime
import httpx
from dotenv import load_dotenv

load_dotenv()

# --- DARAJA API CONFIGURATION ---
CONSUMER_KEY = os.getenv("DARAJA_CONSUMER_KEY", "")
CONSUMER_SECRET = os.getenv("DARAJA_CONSUMER_SECRET", "")
BUSINESS_SHORT_CODE = os.getenv("DARAJA_BUSINESS_SHORTCODE", "174379")
PASSKEY = os.getenv("DARAJA_PASSKEY", "")
CALLBACK_URL = os.getenv("DARAJA_CALLBACK_URL", "https://example.com/api/v1/payments/callback")

IS_SANDBOX = os.getenv("DARAJA_IS_SANDBOX", "true").lower() == "true"
BASE_URL = "https://sandbox.safaricom.co.ke" if IS_SANDBOX else "https://api.safaricom.co.ke"


class DarajaService:
    @staticmethod
    async def get_access_token() -> str:
        """Fetch OAuth Bearer Access Token from Safaricom API."""
        url = f"{BASE_URL}/oauth/v1/generate?grant_type=client_credentials"
        
        key = CONSUMER_KEY.strip()
        secret = CONSUMER_SECRET.strip()

        keys = f"{key}:{secret}"
        encoded_keys = base64.b64encode(keys.encode()).decode("utf-8")
        headers = {"Authorization": f"Basic {encoded_keys}"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                return res.json().get("access_token", "")
            
            error_body = res.text or res.reason_phrase
            raise Exception(f"Daraja Auth Failed [{res.status_code}]: {error_body}")

    @staticmethod
    def generate_password(timestamp: str) -> str:
        """Generate base64 encoded password using Shortcode + Passkey + Timestamp."""
        raw_password = f"{BUSINESS_SHORT_CODE.strip()}{PASSKEY.strip()}{timestamp}"
        return base64.b64encode(raw_password.encode()).decode("utf-8")

    @classmethod
    async def initiate_stk_push(
        cls, 
        phone_number: str, 
        amount: float, 
        account_reference: str, 
        transaction_desc: str = "Payment"
    ) -> dict:
        """Send STK Push prompt to user's phone number."""
        access_token = await cls.get_access_token()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = cls.generate_password(timestamp)

        # Standardize Kenyan phone format (2547XXXXXXXX or 2541XXXXXXXX)
        formatted_phone = phone_number.strip().replace("+", "")
        if formatted_phone.startswith("0"):
            formatted_phone = f"254{formatted_phone[1:]}"

        payload = {
            "BusinessShortCode": BUSINESS_SHORT_CODE.strip(),
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": formatted_phone,
            "PartyB": BUSINESS_SHORT_CODE.strip(),
            "PhoneNumber": formatted_phone,
            "CallBackURL": CALLBACK_URL.strip(),
            "AccountReference": account_reference[:12],
            "TransactionDesc": transaction_desc[:30]
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        url = f"{BASE_URL}/mpesa/stkpush/v1/processrequest"
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(url, json=payload, headers=headers)
            return res.json()

    # --- Backward-Compatible Aliases ---
    @classmethod
    async def send_stk_push(cls, phone_number: str, amount: float, account_reference: str, transaction_desc: str = "Payment") -> dict:
        """Alias method to satisfy orders.py without breaking existing callers."""
        return await cls.initiate_stk_push(phone_number, amount, account_reference, transaction_desc)




# import os
# import base64
# from datetime import datetime
# import httpx
# from dotenv import load_dotenv

# load_dotenv()

# # --- DARAJA API CONFIGURATION ---
# CONSUMER_KEY = os.getenv("DARAJA_CONSUMER_KEY", "")
# CONSUMER_SECRET = os.getenv("DARAJA_CONSUMER_SECRET", "")
# BUSINESS_SHORT_CODE = os.getenv("DARAJA_BUSINESS_SHORTCODE", "174379")
# PASSKEY = os.getenv("DARAJA_PASSKEY", "")
# CALLBACK_URL = os.getenv("DARAJA_CALLBACK_URL", "https://example.com/api/v1/payments/callback")

# IS_SANDBOX = os.getenv("DARAJA_IS_SANDBOX", "true").lower() == "true"
# BASE_URL = "https://sandbox.safaricom.co.ke" if IS_SANDBOX else "https://api.safaricom.co.ke"


# class DarajaService:
#     @staticmethod
#     async def get_access_token() -> str:
#         """Fetch OAuth Bearer Access Token from Safaricom API."""
#         url = f"{BASE_URL}/oauth/v1/generate?grant_type=client_credentials"
        
#         # Clean credentials
#         key = CONSUMER_KEY.strip()
#         secret = CONSUMER_SECRET.strip()

#         keys = f"{key}:{secret}"
#         encoded_keys = base64.b64encode(keys.encode()).decode("utf-8")
#         headers = {"Authorization": f"Basic {encoded_keys}"}

#         async with httpx.AsyncClient() as client:
#             res = await client.get(url, headers=headers)
#             if res.status_code == 200:
#                 return res.json().get("access_token", "")
            
#             error_body = res.text or res.reason_phrase
#             raise Exception(f"Daraja Auth Failed [{res.status_code}]: {error_body}")

#     @staticmethod
#     def generate_password(timestamp: str) -> str:
#         """Generate base64 encoded password using Shortcode + Passkey + Timestamp."""
#         raw_password = f"{BUSINESS_SHORT_CODE.strip()}{PASSKEY.strip()}{timestamp}"
#         return base64.b64encode(raw_password.encode()).decode("utf-8")

#     @classmethod
#     async def initiate_stk_push(cls, phone_number: str, amount: float, account_reference: str):
#         """Send STK Push prompt to user's phone number."""
#         access_token = await cls.get_access_token()
#         timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
#         password = cls.generate_password(timestamp)

#         # Standardize Kenyan phone format (2547XXXXXXXX or 2541XXXXXXXX)
#         formatted_phone = phone_number.strip().replace("+", "")
#         if formatted_phone.startswith("0"):
#             formatted_phone = f"254{formatted_phone[1:]}"

#         payload = {
#             "BusinessShortCode": BUSINESS_SHORT_CODE.strip(),
#             "Password": password,
#             "Timestamp": timestamp,
#             "TransactionType": "CustomerPayBillOnline",
#             "Amount": int(amount),
#             "PartyA": formatted_phone,
#             "PartyB": BUSINESS_SHORT_CODE.strip(),
#             "PhoneNumber": formatted_phone,
#             "CallBackURL": CALLBACK_URL.strip(),
#             "AccountReference": account_reference[:12],
#             "TransactionDesc": f"Payment for Order {account_reference}"
#         }

#         headers = {
#             "Authorization": f"Bearer {access_token}",
#             "Content-Type": "application/json"
#         }

#         url = f"{BASE_URL}/mpesa/stkpush/v1/processrequest"
#         async with httpx.AsyncClient() as client:
#             res = await client.post(url, json=payload, headers=headers)
#             return res.json()