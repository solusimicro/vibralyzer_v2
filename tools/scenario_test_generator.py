import time
import json
import numpy as np
import paho.mqtt.publish as publish

BROKER = "localhost"
PORT = 1883
ASSET = "PUMP_01"

FS = 25600
WINDOW = 4096
RPM = 2980
FR = RPM / 60

POINTS = {
    "P1MT": "unbalance",
    "P2MT": "misalignment",
    "P3GX": "gear_wear",
    "P4GX": "bearing_outer",
    "P5GX": "bearing_advanced",
    "P6GX": "gear_severe",
    "P7PP": "cavitation",
    "P8PP": "hydraulic",
}


# =========================
# FAULT MODELS
# =========================
def unbalance(t, s):
    return 0.02*np.sin(2*np.pi*FR*t) + s*0.05*np.sin(2*np.pi*FR*t)

def misalignment(t, s):
    return 0.02*np.sin(2*np.pi*FR*t) + s*0.04*np.sin(2*np.pi*2*FR*t)

def gear_wear(t, s):
    gm = 20 * FR
    return 0.01*np.sin(2*np.pi*FR*t) + s*0.06*np.sin(2*np.pi*gm*t)

def bearing_outer(t, s):
    return s * 0.03 * np.random.randn(len(t))

def bearing_advanced(t, s):
    return s * 0.08 * np.random.randn(len(t))

def gear_severe(t, s):
    gm = 20 * FR
    return s*0.1*np.sin(2*np.pi*gm*t) + s*0.05*np.random.randn(len(t))

def cavitation(t, s):
    return s*0.04*np.random.randn(len(t))

def hydraulic(t, s):
    return 0.02*np.sin(2*np.pi*FR*t) + s*0.03*np.random.randn(len(t))


FAULT_MAP = {
    "unbalance": unbalance,
    "misalignment": misalignment,
    "gear_wear": gear_wear,
    "bearing_outer": bearing_outer,
    "bearing_advanced": bearing_advanced,
    "gear_severe": gear_severe,
    "cavitation": cavitation,
    "hydraulic": hydraulic,
}


# =========================
# SCENARIO PHASES
# =========================
SCENARIO = [
    ("NORMAL", 0.0, 20),
    ("WATCH", 0.2, 20),
    ("WARNING", 0.5, 20),
    ("ALARM", 1.0, 20),
    ("CLEAR", 0.1, 20),
]


def main():
    t = np.arange(WINDOW) / FS

    for phase, severity, duration in SCENARIO:
        print(f"\n=== PHASE {phase} (severity={severity}) ===")

        for _ in range(duration):
            for point, fault in POINTS.items():
                acc = FAULT_MAP[fault](t, severity)
                acc += 0.005 * np.random.randn(len(t))  # noise floor

                payload = {
                    "timestamp": time.time(),
                    "acceleration": acc.tolist(),
                }

                topic = f"vibration/raw/{ASSET}/{point}"
                publish.single(topic, json.dumps(payload),
                               hostname=BROKER, port=PORT)

            time.sleep(1)


if __name__ == "__main__":
    main()
