from __future__ import annotations

import json
from typing import Any

import qrcode
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter


PAIRING_QR_TYPE = "money_manager_pairing"


def pairing_payload(details: dict[str, Any]) -> str:
    return json.dumps(
        {
            "type": PAIRING_QR_TYPE,
            "protocol_version": int(details["protocol_version"]),
            "url": str(details["url"]),
            "code": str(details["code"]),
            "fingerprint": str(details["fingerprint"]),
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def pairing_qr_image(details: dict[str, Any], box_size: int = 5) -> QImage:
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        border=4,
    )
    qr.add_data(pairing_payload(details))
    qr.make(fit=True)
    matrix = qr.get_matrix()
    image_size = len(matrix) * box_size
    image = QImage(image_size, image_size, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)

    painter = QPainter(image)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(Qt.GlobalColor.black)
    for row_index, row in enumerate(matrix):
        for column_index, filled in enumerate(row):
            if filled:
                painter.drawRect(
                    column_index * box_size,
                    row_index * box_size,
                    box_size,
                    box_size,
                )
    painter.end()
    return image
