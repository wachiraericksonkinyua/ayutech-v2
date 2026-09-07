import os
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.db.supabase_client import supabase
from app.api.v1.endpoints.whatsapp import send_whatsapp_message

scheduler = AsyncIOScheduler()

async def check_uncontacted_leads_and_followup():
    """Runs periodically to send re-engagement messages to pending leads."""
    print("⏰ Running 24-hour lead follow-up check...")
    try:
        time_threshold = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        
        res = supabase.table("leads")\
            .select("*")\
            .eq("status", "pending_contact")\
            .lte("created_at", time_threshold)\
            .execute()

        # res may be None or a simple boolean on failure; guard access to .data
        leads = getattr(res, "data", None) or []
        for lead in leads:
            phone = str(lead.get("customer_phone"))
            notes = lead.get("notes", "your inquiry")
            
            followup_text = (
                f"Mambo! Karibu tena Ayutech Motors. "
                f"Tulipokea maombi yako kuhusu ({notes}). "
                f"Je, bado unahitaji usaidizi au ungetaka tukutumie part hii leo?"
            )
            
            await send_whatsapp_message(phone, followup_text)
            lead_id = lead.get("id")
            if not lead_id:
                print(f"⚠️ Skipping update, missing lead id for phone: {phone}")
                continue
            supabase.table("leads").update({"status": "followup_sent"}).eq("id", lead_id).execute()
            print(f"📩 Sent 24h follow-up to: {phone}")
            
    except Exception as e:
        print(f"⚠️ Scheduler Error: {e}")

def start_scheduler():
    """Starts the background scheduler loop."""
    scheduler.add_job(check_uncontacted_leads_and_followup, 'interval', hours=12)
    scheduler.start()
    print("⏰ Background Lead Scheduler Active")