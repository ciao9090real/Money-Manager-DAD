from __future__ import annotations

import json

from app.sync.pairing_qr import pairing_payload, pairing_qr_image


def test_pairing_qr_contains_only_the_required_connection_details():
    details = {
        "url": "https://192.168.1.20:8765",
        "code": "123456",
        "fingerprint": "a" * 64,
        "protocol_version": 1,
        "expires_in_seconds": 600,
    }

    payload = json.loads(pairing_payload(details))

    assert payload == {
        "type": "money_manager_pairing",
        "protocol_version": 1,
        "url": details["url"],
        "code": details["code"],
        "fingerprint": details["fingerprint"],
    }
    image = pairing_qr_image(details)
    assert not image.isNull()
    assert image.width() == image.height()
