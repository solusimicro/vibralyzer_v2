# simulator/raw_publisher.py

import json
import time
import paho.mqtt.publish as publish

def publish_raw(cfg, acc):
    payload = {
        "asset": cfg["asset"],
        "point": cfg["point"],
        "acceleration": acc,
        "temperature": cfg["temp_base"],
        "timestamp": time.time()
    }

    publish.single(
        cfg["topic"],
        json.dumps(payload),
        hostname=cfg["broker"]
    )
