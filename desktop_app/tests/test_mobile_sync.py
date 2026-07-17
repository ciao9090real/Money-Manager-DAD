from __future__ import annotations

import json
import ssl
import urllib.request
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.database import connect, unit_of_work
from app.services.account_service import AccountService
from app.services.investment_service import InvestmentService
from app.services.sync_service import SyncService
from app.services.transaction_service import TransactionService
from app.sync.server import LocalSyncServer


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("MONEY_MANAGER_DAD_DATA_DIR", str(tmp_path))
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()


def paired_sync(db):
    service = SyncService(db)
    device_id = str(uuid4())
    pairing = service.pair_device(device_id, "Android phone", "sha256:test")
    assert service.authenticate(device_id, pairing["auth_token"])
    return service, device_id


def test_initial_mobile_sync_returns_portable_snapshot(db):
    account = AccountService(db).create_account(
        "Everyday", "current_account", opening_balance="100"
    )
    TransactionService(db).add_expense(account.id, "12.50", "2026-07-17", "Lunch")
    sync, device_id = paired_sync(db)

    response = sync.exchange(device_id, 0)

    assert response["snapshot"] is True
    assert response["cursor"] >= 2
    entities = {change["entity"] for change in response["changes"]}
    assert {"accounts", "transactions"}.issubset(entities)
    transaction = next(
        change for change in response["changes"] if change["entity"] == "transactions"
    )
    assert transaction["payload"]["amount_cents"] == -1250


def test_mobile_command_is_idempotent_across_retries(db):
    account = AccountService(db).create_account("Everyday", "current_account")
    sync, device_id = paired_sync(db)
    command = {
        "id": str(uuid4()),
        "type": "create_income",
        "payload": {
            "account_id": account.id,
            "amount_cents": 2599,
            "date": "2026-07-17",
            "description": "Mobile income",
        },
    }

    first = sync.exchange(device_id, 0, [command])
    second = sync.exchange(device_id, first["cursor"], [command])

    assert first["commands"][0]["status"] == "accepted"
    assert second["commands"][0] == first["commands"][0]
    assert db.execute(
        "SELECT COUNT(*) FROM transactions WHERE description = 'Mobile income'"
    ).fetchone()[0] == 1
    assert AccountService(db).account_balance(account.id) == Decimal("25.99")


def test_mobile_transfer_keeps_net_worth_and_rejects_same_account(db):
    accounts = AccountService(db)
    source = accounts.create_account("Current", "current_account", opening_balance="80")
    target = accounts.create_account("Savings", "savings_account", opening_balance="20")
    sync, device_id = paired_sync(db)
    transfer = {
        "id": str(uuid4()),
        "type": "create_transfer",
        "payload": {
            "source_account_id": source.id,
            "target_account_id": target.id,
            "amount_cents": 3000,
            "date": "2026-07-17",
            "description": "Move to savings",
        },
    }
    invalid = {
        **transfer,
        "id": str(uuid4()),
        "payload": {**transfer["payload"], "target_account_id": source.id},
    }

    response = sync.exchange(device_id, 0, [transfer, invalid])

    assert [item["status"] for item in response["commands"]] == ["accepted", "rejected"]
    assert accounts.account_balance(source.id) == Decimal("50.00")
    assert accounts.account_balance(target.id) == Decimal("50.00")


def test_investment_value_logs_are_revisioned_and_tombstoned(db):
    source = AccountService(db).create_account(
        "Current", "current_account", opening_balance="100"
    )
    investments = InvestmentService(db)
    snapshot = investments.create_investment(
        "Index", "etf", source.id, "10", "2026-07-17", "10"
    )
    investment = snapshot.investment
    with unit_of_work(db):
        point = investments.investments.record_value(
            investment.id, "2026-07-17", Decimal("12")
        )

    with unit_of_work(db):
        investments.investments.update_value_point(investment.id, point.id, Decimal("13"))
    with unit_of_work(db):
        investments.investments.delete_value_point(investment.id, point.id)

    stored = db.execute(
        "SELECT revision, deleted_at FROM investment_value_history WHERE id = ?",
        (point.id,),
    ).fetchone()
    assert stored["revision"] == 3
    assert stored["deleted_at"].endswith("Z")
    assert db.execute(
        """
        SELECT COUNT(*) FROM change_log
        WHERE entity_type = 'investment_value_history' AND entity_id = ?
        """,
        (point.id,),
    ).fetchone()[0] == 3


def test_local_https_server_pairs_and_syncs(db):
    AccountService(db).create_account("Everyday", "current_account")
    server = LocalSyncServer(host="127.0.0.1", port=0)
    details = server.start()
    base_url = f"https://127.0.0.1:{server.port}"
    context = ssl._create_unverified_context()
    device_id = str(uuid4())
    try:
        with urllib.request.urlopen(
            f"{base_url}/v1/hello", context=context, timeout=5
        ) as response:
            hello = json.load(response)
        assert hello["protocol_version"] == 1
        assert hello["certificate_fingerprint"] == details["fingerprint"]

        pair_request = urllib.request.Request(
            f"{base_url}/v1/pair",
            data=json.dumps(
                {
                    "code": details["code"],
                    "device_id": device_id,
                    "display_name": "Test phone",
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(pair_request, context=context, timeout=5) as response:
            pairing = json.load(response)

        sync_request = urllib.request.Request(
            f"{base_url}/v1/sync",
            data=json.dumps(
                {"device_id": device_id, "cursor": 0, "commands": []}
            ).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {pairing['auth_token']}",
            },
        )
        with urllib.request.urlopen(sync_request, context=context, timeout=5) as response:
            synced = json.load(response)
        assert synced["snapshot"] is True
        assert any(change["entity"] == "accounts" for change in synced["changes"])
    finally:
        server.stop()
