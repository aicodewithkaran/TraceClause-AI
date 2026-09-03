import os
from typing import List, Dict
from pydantic import BaseModel
from supabase import create_client, Client
from app.core.config import settings

def get_db_client() -> Client:
    # Use Admin Service Role Key first to guarantee DB inserts bypass RLS restrictions
    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
        return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    if settings.SUPABASE_URL and settings.SUPABASE_KEY:
        return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    return None

class UserIsolationService:
    """Service ensuring users can store and retrieve their own isolated contract reports."""

    @staticmethod
    def save_user_report(user_id: str, file_name: str, overall_score: str, summary_data: dict, clauses_data: list):
        client = get_db_client()
        if not client:
            print("No Supabase DB client available to save report.")
            return None

        try:
            res = client.table("contract_reports").insert({
                "user_id": user_id,
                "file_name": file_name,
                "overall_risk_score": overall_score,
                "summary_json": summary_data,
                "clauses_json": clauses_data
            }).execute()
            print(f"Successfully saved contract report to DB for user {user_id}: {file_name}")
            return res.data
        except Exception as e:
            print(f"Error saving report to DB: {e}")
            return None

    @staticmethod
    def get_user_reports(user_id: str) -> List[Dict]:
        client = get_db_client()
        if not client:
            return []

        try:
            res = client.table("contract_reports") \
                .select("*") \
                .eq("user_id", user_id) \
                .order("created_at", desc=True) \
                .execute()
            return res.data or []
        except Exception as e:
            print(f"Error fetching user reports: {e}")
            return []
