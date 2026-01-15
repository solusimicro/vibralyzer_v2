# simulator/signal_generator.py
import numpy as np

def generate_signal(cfg, cycle):
    t = np.arange(cfg["samples"]) / cfg["fs"]

    # =========================
    # BASE NOISE (NORMAL)
    # =========================
    signal = np.random.normal(
        0,
        cfg["base_noise"],
        cfg["samples"]
    )

    # =========================
    # FAULT SEVERITY RAMP
    # =========================
    if cycle >= cfg["fault_start_cycle"]:
        severity = min(
            (cycle - cfg["fault_start_cycle"]) / cfg["fault_ramp_cycles"],
            1.0
        )

        # HF sinus (bearing frequency)
        hf = (
            cfg["hf_gain"]
            * severity
            * np.sin(2 * np.pi * cfg["hf_freq"] * t)
        )
        signal += hf

        # broadband fault noise
        signal += np.random.normal(
            0,
            cfg["fault_noise"] * severity,
            cfg["samples"]
        )

        # impulsive spikes (bearing defect)
        for _ in range(int(cfg["impulse_rate"] * severity)):
            idx = np.random.randint(0, cfg["samples"])
            signal[idx] += np.random.uniform(
                cfg["impulse_min"],
                cfg["impulse_max"]
            )

    return signal.tolist()

