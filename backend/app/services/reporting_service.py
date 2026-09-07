from datetime import datetime
from app.db.supabase_client import supabase

async def generate_daily_failure_report() -> dict:
    """Aggregates system errors and lists high-demand out-of-stock items for restock planning."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0).isoformat()
    
    try:
        # Fetch high demand restock wishlist items
        wishlist_res = supabase.table("stock_wishlist")\
            .select("part_name, request_count")\
            .order("request_count", desc=True)\
            .limit(5)\
            .execute()

        # Query failed vision attempts
        failed_vision = supabase.table("system_logs")\
            .select("*")\
            .eq("event_type", "VISION_FAILURE")\
            .gte("created_at", today_start)\
            .execute()

        report = {
            "date": str(datetime.utcnow().date()),
            "top_out_of_stock_restock_items": wishlist_res.data or [],
            "total_vision_failures": len(failed_vision.data or []),
            "health_status": "HEALTHY"
        }
        
        print(f"📊 Daily Inventory & System Report: {report}")
        return report
    except Exception as e:
        print(f"⚠️ Reporting Error: {e}")
        return {"date": str(datetime.utcnow().date()), "status": "ERROR", "details": str(e)}