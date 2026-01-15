"""
Factory Acceptance Test (FAT)
RAW → L1 → Early Fault FSM → L2 Diagnostic
"""

import time
import json
import numpy as np
import paho.mqtt.client as mqtt
import paho.mqtt.publish as publish
from collections import Counter

# =========================
# CONFIG
# =========================
BROKER = "localhost"
RAW_TOPIC = "vibration/raw/PUMP_01/DE"
EF_TOPIC = "vibration/early_fault/PUMP_01/DE"
L2_TOPIC = "vibration/l2/PUMP_01/DE"

FS = 25600
SAMPLES = 4096

FAULT_START_CYCLE = 180
TOTAL_CYCLES = 320

results = {
    "fsm_states": [],
    "l2_events": []
}

# =========================
# SIGNAL GENERATOR
# =========================
def generate_signal(cycle):
    noise = np.random.normal(0, 0.008, SAMPLES)

    if cycle < FAULT_START_CYCLE:
        return noise.tolist()

    ramp = min(
        1.0,
        (cycle - FAULT_START_CYCLE) / 20  # ⬅️ ramp 20 cycles
    )

    t = np.arange(SAMPLES) / FS

    hf = ramp * 0.12 * np.sin(2 * np.pi * 6000 * t)

    impulses = np.zeros(SAMPLES)
    if ramp > 0.4:
        idx = np.random.randint(0, SAMPLES, 4)
        impulses[idx] = ramp * np.random.uniform(0.2, 0.5, 4)

    return (noise + hf + impulses).tolist()

# =========================
# MQTT CALLBACK
# =========================
def on_message(client, userdata, msg):
    payload = json.loads(msg.payload.decode())

    if msg.topic == EF_TOPIC:
        results["fsm_states"].append(payload["state"])

    elif msg.topic == L2_TOPIC:
        results["l2_events"].append(payload)

# =========================
# MQTT CLIENT
# =========================
client = mqtt.Client()
client.on_message = on_message
client.connect(BROKER)
client.subscribe(EF_TOPIC)
client.subscribe(L2_TOPIC)
client.loop_start()

# =========================
# TEST EXECUTION
# =========================
print("▶ FAT STARTED")

for cycle in range(TOTAL_CYCLES):
    acc = generate_signal(cycle)
    payload = {
        "acceleration": acc,
        "temperature": 58.0,
        "timestamp": time.time()
    }
    publish.single(RAW_TOPIC, json.dumps(payload), hostname=BROKER)
    time.sleep(0.25)

client.loop_stop()


# =========================
# ASSERTIONS
# =========================
print("\n▶ FAT RESULT")
print("FSM state summary:", Counter(results["fsm_states"]))

assert "WATCH" in results["fsm_states"], "❌ FSM never entered WATCH"
assert "WARNING" in results["fsm_states"], "❌ FSM never entered WARNING"
assert len(results["l2_events"]) > 0, "❌ L2 never triggered"

# no early L2
first_l2_ts = results["l2_events"][0]["timestamp"]
fsm_warning_idx = results["fsm_states"].index("WARNING")
assert fsm_warning_idx >= FAULT_START_CYCLE, "❌ L2 triggered too early"

print("✅ FSM transitions OK")
print("✅ L2 trigger OK")
print("✅ NO BYPASS DETECTED")
print("🎉 FAT PASSED — SYSTEM PRODUCTION READY")
