"""Extensible alert delivery channels."""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class Alert:
    source: str
    severity: str
    message: str


class ConsoleChannel:
    def send(self, alert: Alert) -> None:
        print(f"[{alert.severity.upper()}] {alert.source}: {alert.message}", flush=True)


class WebhookChannel:
    def __init__(self, url: str):
        self.url = url

    def send(self, alert: Alert) -> None:
        request = urllib.request.Request(
            self.url,
            data=json.dumps(alert.__dict__).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5):
            pass


def notify(alert: Alert) -> None:
    channels = [ConsoleChannel()]
    if os.environ.get("ALERT_WEBHOOK_URL"):
        channels.append(WebhookChannel(os.environ["ALERT_WEBHOOK_URL"]))
    for channel in channels:
        try:
            channel.send(alert)
        except Exception as exc:
            print(f"[WARNING] alert channel failed: {exc}", flush=True)
