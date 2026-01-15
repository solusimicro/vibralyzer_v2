# simulator/config.py

SIM_CONFIG = {
    "asset": "PUMP_01",
    "point": "DE",

    # ======================
    # Sampling
    # ======================
    "fs": 25600,
    "samples": 4096,

    # ======================
    # Baseline vibration
    # ======================
    "base_noise": 0.008,

    # ======================
    # Fault injection (bearing-like)
    # ======================
    "fault_start_cycle": 150,
    "fault_ramp_cycles": 15,   # ⬅️ PENTING (FSM needs this)

    "hf_freq": 6000,
    "hf_gain": 0.12,           # ⬅️ 0.03 terlalu kecil utk FSM

    "fault_noise": 0.04,

    # impulsive component (bearing defect)
    "impulse_rate": 6,
    "impulse_min": 0.25,
    "impulse_max": 0.6,

    # ======================
    # Temperature
    # ======================
    "temp_base": 58.0,
    "temp_drift_per_cycle": 0.05,

    # ======================
    # Timing
    # ======================
    "cycle_sec": 0.3,

    # ======================
    # MQTT
    # ======================
    "broker": "localhost",
    "topic": "vibration/raw/PUMP_01/DE",
}

