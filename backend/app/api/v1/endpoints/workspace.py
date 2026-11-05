from fastapi import APIRouter, Depends, HTTPException, Body, status
from app.core.dependencies import require_feature, get_current_profile
from app.core.security import supabase_client

router = APIRouter(dependencies=[Depends(require_feature("workspace_management"))])

@router.get("/")
async def get_my_workspaces(current_profile: dict = Depends(get_current_profile)):
    """
    Fetch workspaces where the authenticated user is an owner OR a member.
    Enforces authorization in code since service-role queries bypass PostgreSQL RLS.
    """
    user_id = current_profile["id"]
    if not supabase_client:
        return {"workspaces": []}

    try:
        # 1. Fetch workspaces owned by user
        owned_res = supabase_client.table("workspaces") \
            .select("*, workspace_members(*)") \
            .eq("owner_id", user_id) \
            .execute()
        owned_workspaces = owned_res.data or []

        # 2. Fetch workspace IDs where user is a member
        member_res = supabase_client.table("workspace_members") \
            .select("workspace_id") \
            .eq("user_id", user_id) \
            .execute()
        member_ws_ids = [m["workspace_id"] for m in (member_res.data or []) if m.get("workspace_id")]

        workspaces_by_id = {ws["id"]: ws for ws in owned_workspaces}

        # 3. Fetch member workspaces not already in owned list
        remaining_ids = [wid for wid in member_ws_ids if wid not in workspaces_by_id]
        if remaining_ids:
            member_ws_res = supabase_client.table("workspaces") \
                .select("*, workspace_members(*)") \
                .in_("id", remaining_ids) \
                .execute()
            for ws in (member_ws_res.data or []):
                workspaces_by_id[ws["id"]] = ws

        return {"workspaces": list(workspaces_by_id.values())}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch workspaces: {str(e)}"
        )

@router.post("/")
async def create_workspace(
    name: str = Body(..., embed=True),
    current_profile: dict = Depends(get_current_profile)
):
    """Create a new team workspace (Team tier only)."""
    user_id = current_profile["id"]
    if not supabase_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable."
        )

    clean_name = name.strip()
    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workspace name cannot be empty."
        )

    try:
        ws_res = supabase_client.table("workspaces").insert({
            "owner_id": user_id,
            "name": clean_name,
            "seat_limit": 4
        }).execute()
        
        if ws_res.data and len(ws_res.data) > 0:
            ws = ws_res.data[0]
            # Add owner as workspace member
            supabase_client.table("workspace_members").insert({
                "workspace_id": ws["id"],
                "user_id": user_id,
                "role": "owner"
            }).execute()
            return {"status": "success", "workspace": ws}
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create workspace record."
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workspace creation error: {str(e)}"
        )
