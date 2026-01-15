from diagnostic_l2.fault_rules import run_rules

def run_diagnostic(l1_snapshot: dict, early_fault_event: dict):
    """
    L2 Diagnostic MUST be gated by Early Fault
    """

    # HARD GATE 1 — Early Fault only
    if not early_fault_event.get("early_fault", False):
        return []

    # HARD GATE 2 — Asset consistency
    if l1_snapshot["asset"] != early_fault_event["asset"]:
        return []

    if l1_snapshot["point"] != early_fault_event["point"]:
        return []

    # HARD GATE 3 — Time order
    if early_fault_event["timestamp"] < l1_snapshot["timestamp"]:
        return []

    # OK → Run L2 rules
    return run_rules(l1_snapshot)

