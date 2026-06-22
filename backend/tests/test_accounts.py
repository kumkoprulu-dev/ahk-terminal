import pytest

import app.accounts.service as acc


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(acc, "DB_PATH", tmp_path / "users.sqlite")
    acc.init_db()


def test_register_login_me(db):
    r = acc.register("ahmet", "sifre1")
    assert r["token"] and r["username"] == "ahmet"
    u = acc.user_for_token(r["token"])
    assert u["username"] == "ahmet"


def test_duplicate_username(db):
    acc.register("ahmet", "sifre1")
    with pytest.raises(ValueError):
        acc.register("ahmet", "baska")


def test_wrong_password(db):
    acc.register("ahmet", "sifre1")
    with pytest.raises(ValueError):
        acc.login("ahmet", "yanlis")


def test_saved_items_crud(db):
    r = acc.register("ahmet", "sifre1")
    uid = acc.user_for_token(r["token"])["id"]
    acc.save_item(uid, "strategy", "S1", {"entry": "RSI<30"})
    acc.save_item(uid, "portfolio", "P1", {"symbols": ["A", "B"]})
    items = acc.list_items(uid)
    assert len(items) == 2
    strat = acc.list_items(uid, "strategy")
    assert len(strat) == 1 and strat[0]["data"]["entry"] == "RSI<30"
    # upsert
    acc.save_item(uid, "strategy", "S1", {"entry": "RSI<25"})
    assert len(acc.list_items(uid, "strategy")) == 1
    assert acc.list_items(uid, "strategy")[0]["data"]["entry"] == "RSI<25"
    # delete
    acc.delete_item(uid, strat[0]["id"])
    assert len(acc.list_items(uid, "strategy")) == 0


def test_token_isolation(db):
    a = acc.register("ahmet", "sifre1")
    b = acc.register("mehmet", "sifre2")
    uid_a = acc.user_for_token(a["token"])["id"]
    acc.save_item(uid_a, "strategy", "S1", {"x": 1})
    uid_b = acc.user_for_token(b["token"])["id"]
    assert len(acc.list_items(uid_b)) == 0  # b, a'nın kaydını görmez


def test_logout_invalidates(db):
    r = acc.register("ahmet", "sifre1")
    acc.logout(r["token"])
    assert acc.user_for_token(r["token"]) is None
