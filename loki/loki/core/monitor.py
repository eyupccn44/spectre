import time
from typing import Callable, List, Optional
from datetime import datetime

from loki.core import canary as canary_mod
from loki.core.canary import CanaryTrigger
from loki.db.storage import Storage


def watch(
    storage: Storage,
    on_trigger: Callable[[str, CanaryTrigger], None],
    interval: int = 15,
    trap_id: Optional[str] = None,
) -> None:
    """
    Poll all active traps (or a specific one) for new canary triggers.
    Calls on_trigger(trap_id, trigger) for each new hit.
    Runs until KeyboardInterrupt.
    """
    seen: dict[str, set] = {}

    traps = storage.get_traps(active_only=True)
    if trap_id:
        traps = [t for t in traps if t["id"] == trap_id]

    for trap in traps:
        seen[trap["id"]] = set()

    while True:
        for trap in storage.get_traps(active_only=True):
            tid = trap["id"]
            token_uuid = trap.get("canary_uuid")
            if not token_uuid:
                continue
            if tid not in seen:
                seen[tid] = set()

            triggers = canary_mod.get_triggers(token_uuid)
            for trigger in triggers:
                if trigger.request_id not in seen[tid]:
                    seen[tid].add(trigger.request_id)
                    storage.save_trigger(tid, trigger)
                    on_trigger(tid, trigger)

        time.sleep(interval)
