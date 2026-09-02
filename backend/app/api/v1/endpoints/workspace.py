from fastapi import APIRouter, Depends, HTTPException, Body
from app.core.dependencies import require_feature, get_current_profile
from app.core.security import supabase_client

router = APIRouter(dependencies=[Depends(require_feature("workspace_management"))])

@router.get("/")
async def get_my_workspaces(current_profile: dict = Depends(get_current_profile)):
    """Fetch workspaces where the authenticated user is an owner or member."""
    user_id = current_profile["id"]
    try:
        res = supabase_client.table("workspaces").select("*, workspace_members(*)").eq("owner_id", user_id).execute()
        return {"workspaces": res.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch workspaces: {str(e)}")

@router.post("/")
async def create_workspace(
    name: str = Body(..., embed=True),
    current_profile: dict = Depends(get_current_profile)
):
    """Create a new team workspace (Team tier only)."""
    user_id = current_profile["id"]
    try:
        # Create workspace
        ws_res = supabase_client.table("workspaces").insert({
            "owner_id": user_id,
            "name": name,
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
        raise HTTPException(status_code=500, detail="Failed to insert workspace record.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workspace creation error: {str(e)}")
