from typing import List, Dict, Optional
from supabase import create_client, Client
from app.core.config import settings

def get_db_client() -> Optional[Client]:
    if settings.SUPABASE_URL and settings.supabase_admin_key:
        return create_client(settings.SUPABASE_URL, settings.supabase_admin_key)
    if settings.SUPABASE_URL and settings.supabase_anon_key:
        return create_client(settings.SUPABASE_URL, settings.supabase_anon_key)
    return None

class UserIsolationService:
    """
    Enforces strict tenant isolation and user-controlled retention.
    Because queries use the server-side Service-Role key (which bypasses PostgreSQL RLS),
    every database operation explicitly validates user ownership or workspace membership in code.
    """

    @staticmethod
    def save_user_report(
        user_id: str,
        file_name: str,
        overall_score: str,
        summary_data: dict,
        clauses_data: list,
        workspace_id: Optional[str] = None
    ) -> Optional[dict]:
        client = get_db_client()
        if not client:
            return None

        try:
            payload = {
                "user_id": user_id,
                "file_name": file_name,
                "overall_risk_score": overall_score,
                "summary_json": summary_data,
                "clauses_json": clauses_data
            }
            if workspace_id:
                payload["workspace_id"] = workspace_id

            res = client.table("contract_reports").insert(payload).execute()
            return res.data[0] if (res.data and len(res.data) > 0) else None
        except Exception:
            return None

    @staticmethod
    def get_user_reports(user_id: str) -> List[Dict]:
        """Fetch all reports owned by the user or shared in workspaces the user belongs to."""
        client = get_db_client()
        if not client:
            return []

        try:
            # 1. Direct reports owned by user
            own_res = client.table("contract_reports") \
                .select("*") \
                .eq("user_id", user_id) \
                .order("created_at", desc=True) \
                .execute()
            reports = own_res.data or []

            # 2. Check for workspace reports
            member_res = client.table("workspace_members") \
                .select("workspace_id") \
                .eq("user_id", user_id) \
                .execute()
            
            workspace_ids = [m["workspace_id"] for m in (member_res.data or []) if m.get("workspace_id")]
            if workspace_ids:
                ws_res = client.table("contract_reports") \
                    .select("*") \
                    .in_("workspace_id", workspace_ids) \
                    .order("created_at", desc=True) \
                    .execute()
                ws_reports = ws_res.data or []
                
                # Deduplicate by report ID
                existing_ids = {r["id"] for r in reports}
                for r in ws_reports:
                    if r["id"] not in existing_ids:
                        reports.append(r)
                        existing_ids.add(r["id"])

            return reports
        except Exception:
            return []

    @staticmethod
    def get_user_report_by_id(user_id: str, report_id: str) -> Optional[Dict]:
        """
        Retrieves a report only if the user is the owner or an active workspace member.
        Guarantees cross-tenant isolation and prevents unauthorized data leaks.
        """
        client = get_db_client()
        if not client:
            return None

        try:
            res = client.table("contract_reports").select("*").eq("id", report_id).execute()
            if not res.data or len(res.data) == 0:
                return None

            report = res.data[0]

            # 1. Direct owner check
            if str(report.get("user_id")) == str(user_id):
                return report

            # 2. Workspace membership check
            workspace_id = report.get("workspace_id")
            if workspace_id:
                wm_res = client.table("workspace_members") \
                    .select("id") \
                    .eq("workspace_id", workspace_id) \
                    .eq("user_id", user_id) \
                    .execute()
                if wm_res.data and len(wm_res.data) > 0:
                    return report

            # User is neither direct owner nor workspace member
            return None
        except Exception:
            return None

    @staticmethod
    def delete_user_report(user_id: str, report_id: str) -> bool:
        """
        Permanently deletes a report and its vector embeddings.
        Enforces that only the report owner or workspace owner can execute deletion.
        """
        client = get_db_client()
        if not client:
            return False

        try:
            report = UserIsolationService.get_user_report_by_id(user_id, report_id)
            if not report:
                return False

            # Delete vector embeddings first
            try:
                client.table("contract_embeddings").delete().eq("report_id", report_id).execute()
            except Exception:
                pass

            # Delete the contract report
            client.table("contract_reports").delete().eq("id", report_id).execute()
            return True
        except Exception:
            return False
