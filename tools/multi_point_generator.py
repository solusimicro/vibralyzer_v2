import time
import json
import numpy as np
import paho.mqtt.publish as publish

# =========================
# MQTT CONFIG
# =========================
BROKER = "localhost"
PORT = 1883
ASSET = "PUMP_01"

FS = 25600
WINDOW = 4096
BASE_RPM = 2980
FR = BASE_RPM / 60

POINTS = {
    "P1MT": "motor",
    "P2MT": "motor",
    "P3GX": "gearbox",
    "P4GX": "gearbox",
    "P5GX": "gearbox",
    "P6GX": "gearbox",
    "P7PP": "pump",
    "P8PP": "pump",
}


# =========================
# SIGNAL GENERATORS
# =========================
def motor_signal(t, severity):
    sig = 0.02 * np.sin(2 * np.pi * FR * t)
    sig += severity * 0.05 * np.sin(2 * np.pi * 2 * FR * t)
    sig += 0.01 * np.random.randn(len(t))
    return sig


def gearbox_signal(t, severity):
    gear_mesh = 20 * FR
    sig = 0.01 * np.sin(2 * np.pi * FR * t)
    sig += severity * 0.06 * np.sin(2 * np.pi * gear_mesh * t)
    sig += severity * 0.02 * np.random.randn(len(t))
    return sig


def pump_signal(t, severity):
    sig = 0.015 * np.sin(2 * np.pi * FR * t)
    sig += severity * 0.04 * np.random.randn(len(t))
    return sig


# =========================
# MAIN LOOP
# =========================
def main():
    t = np.arange(WINDOW) / FS
    severity = 0.0

    while True:
        severity = min(severity + 0.01, 1.0)

        for point, ptype in POINTS.items():
            if ptype == "motor":
                acc = motor_signal(t, severity)
            elif ptype == "gearbox":
                acc = gearbox_signal(t, severity)
            else:
                acc = pump_signal(t, severity)

            payload = {
                "timestamp": time.time(),
                "acceleration": acc.tolist(),
            }

            topic = f"vibration/raw/{ASSET}/{point}"
            publish.single(
                topic,
                json.dumps(payload),
                hostname=BROKER,
                port=PORT,
            )

            print(f"TX {topic} | severity={severity:.2f}")

        time.sleep(1)


if __name__ == "__main__":
    main()
