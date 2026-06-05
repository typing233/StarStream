from fastapi import APIRouter, Depends, HTTPException

from app.models import User
from app.auth import get_current_admin
from app.services.plugin_manager import plugin_manager

router = APIRouter(prefix="/api/v1/admin/plugins", tags=["plugins"])


@router.get("")
def list_plugins(user: User = Depends(get_current_admin)):
    return plugin_manager.list_plugins()


@router.post("/{name}/enable")
def enable_plugin(name: str, user: User = Depends(get_current_admin)):
    available = [p["name"] for p in plugin_manager.discover()]
    if name not in available:
        raise HTTPException(status_code=404, detail="Plugin not found")
    success = plugin_manager.enable(name)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to load plugin")
    return {"message": f"Plugin '{name}' enabled"}


@router.post("/{name}/disable")
def disable_plugin(name: str, user: User = Depends(get_current_admin)):
    plugin_manager.disable(name)
    return {"message": f"Plugin '{name}' disabled"}
