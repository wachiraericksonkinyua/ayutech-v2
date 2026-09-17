import os
import base64
from datetime import datetime
import httpx
from dotenv import load_dotenv

load_dotenv()


class DarajaService:
    @staticmethod
    def get_config() -> dict:
        """Fetch runtime environment variables dynamically."""
        is_sandbox = os.getenv("DARAJA_IS_SANDBOX", "true").lower() == "true"
        base_url = "https://sandbox.safaricom.co.ke" if is_sandbox else "https://api.safaricom.co.ke"

        # Safely resolve live Render callback URL with fallback
        callback_url = (
            os.getenv("DARAJA_CALLBACK_URL")
            or os.getenv("CALLBACK_URL")
            or "https://ayutech-v2.onrender.com/api/v1/payments/callback"
        ).strip()

        return {
            "consumer_key": os.getenv("DARAJA_CONSUMER_KEY", "").strip(),
            "consumer_secret": os.getenv("DARAJA_CONSUMER_SECRET", "").strip(),
            "shortcode": (os.getenv("DARAJA_BUSINESS_SHORTCODE") or os.getenv("DARAJA_SHORTCODE") or "174379").strip(),
            "passkey": os.getenv("DARAJA_PASSKEY", "").strip(),
            "callback_url": callback_url,
            "base_url": base_url,
        }

    @classmethod
    async def get_access_token(cls) -> str:
        """Fetch OAuth Bearer Access Token from Safaricom API."""
        cfg = cls.get_config()
        url = f"{cfg['base_url']}/oauth/v1/generate?grant_type=client_credentials"

        keys = f"{cfg['consumer_key']}:{cfg['consumer_secret']}"
        encoded_keys = base64.b64encode(keys.encode()).decode("utf-8")
        headers = {"Authorization": f"Basic {encoded_keys}"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(url, headers=headers)
            if res.status_code == 200:
                return res.json().get("access_token", "")

            error_body = res.text or res.reason_phrase
            raise Exception(f"Daraja Auth Failed [{res.status_code}]: {error_body}")

    @classmethod
    def generate_password(cls, timestamp: str) -> str:
        """Generate base64 encoded password using Shortcode + Passkey + Timestamp."""
        cfg = cls.get_config()
        raw_password = f"{cfg['shortcode']}{cfg['passkey']}{timestamp}"
        return base64.b64encode(raw_password.encode()).decode("utf-8")

    @classmethod
    async def initiate_stk_push(
        cls,
        phone_number: str,
        amount: float,
        account_reference: str,
        transaction_desc: str = "Payment",
    ) -> dict:
        """Send STK Push prompt to user's phone number with dynamic callback."""
        cfg = cls.get_config()
        access_token = await cls.get_access_token()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = cls.generate_password(timestamp)

        # Standardize Kenyan phone format (2547XXXXXXXX or 2541XXXXXXXX)
        formatted_phone = phone_number.strip().replace("+", "")
        if formatted_phone.startswith("0"):
            formatted_phone = f"254{formatted_phone[1:]}"

        payload = {
            "BusinessShortCode": cfg["shortcode"],
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": formatted_phone,
            "PartyB": cfg["shortcode"],
            "PhoneNumber": formatted_phone,
            "CallBackURL": cfg["callback_url"],
            "AccountReference": account_reference[:12],
            "TransactionDesc": transaction_desc[:30],
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        url = f"{cfg['base_url']}/mpesa/stkpush/v1/processrequest"
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(url, json=payload, headers=headers)
            return res.json()

    @classmethod
    async def query_stk_status(cls, checkout_request_id: str) -> dict:
        """Query the status of an STK transaction by CheckoutRequestID."""
        cfg = cls.get_config()
        access_token = await cls.get_access_token()
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = cls.generate_password(timestamp)

        payload = {
            "BusinessShortCode": cfg["shortcode"],
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id,
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        url = f"{cfg['base_url']}/mpesa/stkpushquery/v1/query"
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(url, json=payload, headers=headers)
            return res.json()

    @classmethod
    async def send_stk_push(
        cls,
        phone_number: str,
        amount: float,
        account_reference: str,
        transaction_desc: str = "Payment",
    ) -> dict:
        """Alias method to satisfy orders.py without breaking existing callers."""
        return await cls.initiate_stk_push(phone_number, amount, account_reference, transaction_desc)