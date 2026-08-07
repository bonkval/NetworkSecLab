"""Local detection-rule engine for the network security lab."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.store import EventStore


RULES = [
    {"rule_id": "AUTH-BRUTE-001", "title": "Single-account brute force", "description": "Five failures against one account from one source in 30 seconds.", "severity": "critical", "attack_id": "T1110.001", "tactic": "Credential Access", "technique": "Password Guessing", "config": {"threshold": 5, "window_seconds": 30, "group_by": ["source", "username"]}},
    {"rule_id": "AUTH-SPRAY-001", "title": "Password spraying", "description": "One password attempted against several accounts.", "severity": "critical", "attack_id": "T1110.003", "tactic": "Credential Access", "technique": "Password Spraying", "config": {"minimum_accounts": 5, "window_seconds": 60}},
    {"rule_id": "AUTH-STUFF-001", "title": "Credential stuffing", "description": "Several username and password pairs attempted in rapid succession.", "severity": "critical", "attack_id": "T1110.004", "tactic": "Credential Access", "technique": "Credential Stuffing", "config": {"minimum_pairs": 5, "window_seconds": 60}},
    {"rule_id": "AUTH-DIST-001", "title": "Distributed password attack", "description": "One account targeted from several source addresses.", "severity": "critical", "attack_id": "T1110", "tactic": "Credential Access", "technique": "Brute Force", "config": {"minimum_sources": 5, "window_seconds": 60}},
    {"rule_id": "NIDS-SURI-001", "title": "Suricata signature alert", "description": "A Suricata EVE alert record matched an IDS signature and requires analyst mapping.", "severity": "critical", "attack_id": "Unmapped", "tactic": "Requires triage", "technique": "Signature Alert", "config": {"event_type": "alert"}},
]


RESPONSE_GUIDANCE = {
    "AUTH-BRUTE-001": ["Temporarily block or rate-limit the source address.", "Review successful logins for the targeted account.", "Reset credentials if compromise is suspected.", "Preserve authentication events and session records."],
    "AUTH-SPRAY-001": ["Identify every targeted account.", "Block the shared source and password pattern.", "Require password resets for accounts using weak or exposed passwords.", "Review identity-provider logs for successful attempts."],
    "AUTH-STUFF-001": ["Revoke sessions for successfully accessed accounts.", "Force resets for exposed credentials.", "Check the credential pairs against internal reuse policy without exposing passwords.", "Enable MFA and monitor follow-on activity."],
    "AUTH-DIST-001": ["Apply account-focused throttling rather than relying only on IP blocks.", "Review geographic and network diversity of sources.", "Lock or protect the targeted account temporarily.", "Search for a successful login within the attack window."],
    "NIDS-SURI-001": ["Validate the signature and inspect related flow metadata.", "Locate the referenced packet in the PCAP when available.", "Review destination host activity around the alert time.", "Contain the affected endpoint if malicious activity is confirmed."],
}


@dataclass
class DetectionResult:
    incident_id: int | None
    matched: bool
    rule_id: str


class DetectionEngine:
    def __init__(self, store: EventStore):
        self.store = store
        for rule in RULES:
            self.store.upsert_rule(rule)

    def rule(self, rule_id: str) -> dict[str, Any] | None:
        return next((rule for rule in self.store.rules() if rule["rule_id"] == rule_id), None)

    def create_incident(
        self, rule_id: str, source: str, summary: str, event_ids: list[int], evidence: dict[str, Any]
    ) -> DetectionResult:
        rule = self.rule(rule_id)
        if not rule or not rule["enabled"]:
            return DetectionResult(None, False, rule_id)
        incident_id = self.store.create_incident(
            rule, source, summary, event_ids, RESPONSE_GUIDANCE[rule_id]
        )
        evidence_record = {
            "rule_id": rule_id,
            "source": source,
            "summary": summary,
            "event_ids": event_ids,
            "evidence": evidence,
        }
        self.store.add_evidence(incident_id, "detection_snapshot", json.dumps(evidence_record, sort_keys=True))
        return DetectionResult(incident_id, True, rule_id)

    def correlate_credentials(self, attack_type: str, event_ids: list[int]) -> DetectionResult:
        events = [event for event_id in event_ids if (event := self.store.event(event_id))]
        sources = {event["source"] for event in events}
        usernames = {event["metadata"].get("username") for event in events}
        fingerprints = {event["metadata"].get("password_fingerprint") for event in events}
        pairs = {(event["metadata"].get("username"), event["metadata"].get("password_fingerprint")) for event in events}
        matches = {
            "brute_force": len(events) >= 5 and len(sources) == 1 and len(usernames) == 1,
            "password_spray": len(events) >= 5 and len(usernames) >= 5 and len(fingerprints) == 1,
            "credential_stuffing": len(events) >= 5 and len(pairs) >= 5,
            "distributed": len(events) >= 5 and len(sources) >= 5 and len(usernames) == 1,
        }
        rule_ids = {
            "brute_force": "AUTH-BRUTE-001",
            "password_spray": "AUTH-SPRAY-001",
            "credential_stuffing": "AUTH-STUFF-001",
            "distributed": "AUTH-DIST-001",
        }
        rule_id = rule_ids[attack_type]
        if not matches[attack_type]:
            return DetectionResult(None, False, rule_id)
        rule = self.rule(rule_id)
        summary = f"{rule['title']} correlated from {len(events)} authentication events across {len(sources)} source(s) and {len(usernames)} account(s)."
        return self.create_incident(
            rule_id,
            next(iter(sources)) if len(sources) == 1 else f"{len(sources)} distributed sources",
            summary,
            event_ids,
            {"event_count": len(events), "source_count": len(sources), "account_count": len(usernames), "pair_count": len(pairs)},
        )
