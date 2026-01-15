# simulator/run_simulator.py

import time
from config import SIM_CONFIG
from signal_generator import generate_signal
from raw_publisher import publish_raw


def run():
    for cycle in range(400):
        acc = generate_signal(SIM_CONFIG, cycle)
        publish_raw(SIM_CONFIG, acc)

        print(f"[SIM] cycle={cycle}")
        time.sleep(SIM_CONFIG["cycle_sec"])


if __name__ == "__main__":
    run()
