"""Hesap ve kayıtlı öğe uç noktaları."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.accounts import service

router = APIRouter(prefix="/api", tags=["accounts"])


def _token(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1]
    return None


def current_user(authorization: str = Header(None)) -> dict:
    user = service.user_for_token(_token(authorization))
    if not user:
        raise HTTPException(401, "Giriş gerekli.")
    return user


class Creds(BaseModel):
    username: str
    password: str


@router.post("/auth/register")
def register(c: Creds):
    try:
        return service.register(c.username, c.password)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/auth/login")
def login(c: Creds):
    try:
        return service.login(c.username, c.password)
    except ValueError as e:
        raise HTTPException(401, str(e))


@router.get("/auth/me")
def me(user: dict = Depends(current_user)):
    return {"username": user["username"]}


@router.post("/auth/logout")
def logout(authorization: str = Header(None)):
    tok = _token(authorization)
    if tok:
        service.logout(tok)
    return {"ok": True}


class SaveReq(BaseModel):
    kind: str
    name: str
    data: dict


@router.post("/saved")
def save_item(req: SaveReq, user: dict = Depends(current_user)):
    try:
        return service.save_item(user["id"], req.kind, req.name, req.data)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/saved")
def list_items(kind: str | None = None, user: dict = Depends(current_user)):
    return {"items": service.list_items(user["id"], kind)}


@router.delete("/saved/{item_id}")
def delete_item(item_id: int, user: dict = Depends(current_user)):
    service.delete_item(user["id"], item_id)
    return {"ok": True}
