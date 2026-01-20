import numpy as np 
from scipy.signal import hilbert, detrend 
from core.signal_utils import (
    rms,
    peak_to_peak,
    bandpass_energy,
)


class L1FeaturePipeline:
    """
    L1 Feature Pipeline (FINAL – LOCKED)
    ===================================
    CORE RAW-DOMAIN FEATURES

    Design rules:
    - No NULL output
    - Physically meaningful units
    - ISO / SCADA / FSM safe
    - Deterministic & auditable
    """

    def __init__(self, fs: float, rpm: float):
        self.fs = fs
        self.rpm = rpm

    def compute(self, window):
        """
        window: np.ndarray
        Acceleration signal in g
        """
        acc = np.asarray(window, dtype=float)

        # -----------------------------
        # BASIC SIGNAL GUARD
        # -----------------------------
        if acc.size == 0:
            return self._zero_features()

        # -----------------------------
        # CORE ACC FEATURES
        # -----------------------------
        acc_rms = rms(acc)
        acc_peak = peak_to_peak(acc) / 2.0

        # -----------------------------
        # HIGH-FREQUENCY RMS (BEARING)
        # -----------------------------
        hf_energy = bandpass_energy(
            acc,
            self.fs,
            low=3000,
            high=10000,
        )

        # Convert energy → RMS-like magnitude
        acc_hf_rms = np.sqrt(hf_energy / acc.size) if hf_energy > 0 else 0.0

        # -----------------------------
        # CREST FACTOR
        # -----------------------------
        crest_factor = acc_peak / acc_rms if acc_rms > 0 else 0.0

        # -----------------------------
        # ENVELOPE RMS (BEARING DEFECT)
        # -----------------------------
        envelope = np.abs(hilbert(acc))
        envelope_rms = rms(envelope)

        # -----------------------------
        # VELOCITY RMS (ISO 10816 / 20816)
        # acc[g] → m/s² → integrate → detrend → mm/s
        # -----------------------------
        acc_ms2 = acc * 9.80665
        vel_m_s = np.cumsum(acc_ms2) / self.fs
        vel_m_s = detrend(vel_m_s, type="constant")

        overall_vel_rms_mm_s = rms(vel_m_s) * 1000.0

        # -----------------------------
        # SUPPORTING ENERGY FEATURES
        # -----------------------------
        energy_low = bandpass_energy(
            acc,
            self.fs,
            low=10,
            high=100,
        )

        energy_high = bandpass_energy(
            acc,
            self.fs,
            low=1000,
            high=5000,
        )

        return {
            # --- SCADA / FSM ---
            "acc_rms_g": float(acc_rms),
            "acc_peak_g": float(acc_peak),
            "acc_hf_rms_g": float(acc_hf_rms),
            "crest_factor": float(crest_factor),
            "envelope_rms": float(envelope_rms),
            "overall_vel_rms_mm_s": float(overall_vel_rms_mm_s),

            # --- ENGINEERING SUPPORT ---
            "energy_low": float(energy_low),
            "energy_high": float(energy_high),
        }

    # =============================
    # SAFE FALLBACK (NEVER NULL)
    # =============================
    def _zero_features(self):
        return {
            "acc_rms_g": 0.0,
            "acc_peak_g": 0.0,
            "acc_hf_rms_g": 0.0,
            "crest_factor": 0.0,
            "envelope_rms": 0.0,
            "overall_vel_rms_mm_s": 0.0,
            "energy_low": 0.0,
            "energy_high": 0.0,
        }


