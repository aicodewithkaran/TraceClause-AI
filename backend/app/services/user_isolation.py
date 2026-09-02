import os
from typing import List, Dict
from pydantic import BaseModel
from supabase import create_client, Client
from app.core.config import settings

supabase_client: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY) if settings.SUPABASE_URL else None

class UserIsolationService:
    """Service ensuring users can only read and store their own contract reports."""

    @staticmethod
    def save_user_report(user_id: str, file_name: str, overall_score: str, summary_data: dict, clauses_data: list):
        if not supabase_client:
            return None

        try:
            res = supabase_client.table("contract_reports").insert({
                "user_id": user_id,
                "file_name": file_name,
                "overall_risk_score": overall_score,
                "summary_json": summary_data,
                "clauses_json": clauses_data
            }).execute()
            return res.data
        except Exception as e:
            print(f"Error saving report to DB: {e}")
            return None

    @staticmethod
    def get_user_reports(user_id: str) -> List[Dict]:
        if not supabase_client:
            return []

        try:
            res = supabase_client.table("contract_reports") \
                .select("*") \
                .eq("user_id", user_id) \
                .order("created_at", desc=True) \
                .execute()
            return res.data or []
        except Exception as e:
            print(f"Error fetching user reports: {e}")
            return []
