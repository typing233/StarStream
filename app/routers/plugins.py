import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import User, PluginRecord
from app.auth import get_admin_user
from app.services.plugin_manager import plugin_manager

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


class PluginConfigUpdate(BaseModel):
    config: dict


@router.get("")
def list_plugins(db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    discovered = plugin_manager.discover()
    records = {r.name: r for r in db.query(PluginRecord).all()}
    result = []
    for name in discovered:
        record = records.get(name)
        loaded = name in plugin_manager.plugins
        result.append({
            "name": name,
            "enabled": record.enabled if record else False,
            "loaded": loaded,
            "version": plugin_manager.plugins[name].version if loaded else (record.version if record else "0.1.0"),
            "description": plugin_manager.plugins[name].description if loaded else "",
        })
    return result


@router.post("/{name}/enable")
def enable_plugin(name: str, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    record = db.query(PluginRecord).filter(PluginRecord.name == name).first()
    if not record:
        raise HTTPException(status_code=404, detail="Plugin not found")
    record.enabled = True
    db.commit()
    plugin_manager.reload()
    return {"ok": True, "name": name, "enabled": True}


@router.post("/{name}/disable")
def disable_plugin(name: str, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    record = db.query(PluginRecord).filter(PluginRecord.name == name).first()
    if not record:
        raise HTTPException(status_code=404, detail="Plugin not found")
    record.enabled = False
    db.commit()
    plugin_manager.unload(name)
    return {"ok": True, "name": name, "enabled": False}


@router.get("/{name}/config")
def get_plugin_config(name: str, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    record = db.query(PluginRecord).filter(PluginRecord.name == name).first()
    if not record:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return {"name": name, "config": json.loads(record.config_json) if record.config_json else {}}


@router.put("/{name}/config")
def update_plugin_config(name: str, req: PluginConfigUpdate, db: Session = Depends(get_db), admin: User = Depends(get_admin_user)):
    record = db.query(PluginRecord).filter(PluginRecord.name == name).first()
    if not record:
        raise HTTPException(status_code=404, detail="Plugin not found")
    record.config_json = json.dumps(req.config)
    db.commit()
    if record.enabled:
        plugin_manager.reload()
    return {"ok": True, "name": name}
