class TrendResult:
    def __init__(
        self,
        level,
        score,
        dominant_feature=None,
        hf_high=False,
        envelope_high=False,
        velocity_zone="A",
        temperature_alarm=False,
    ):
        self.level = level
        self.score = score
        self.dominant_feature = dominant_feature

        # === FSM FLAGS (NEW) ===
        self.hf_high = hf_high
        self.envelope_high = envelope_high
        self.velocity_zone = velocity_zone
        self.temperature_alarm = temperature_alarm

class TrendDetector:
    def __init__(self, history_size=10):
        self._history = {}
        self.history_size = history_size

    def update(self, asset, point, features):
      key = (asset, point)

      if "acc_hf_rms_g" not in features:
          return TrendResult(level="NORMAL", score=0.0)

      hist = self._history.setdefault(key, [])
      hist.append(features)

      if len(hist) > self.history_size:
          hist.pop(0)

      # ============================
      # HF TREND
      # ============================
      hf = features["acc_hf_rms_g"]

      if hf < 0.05:
          level = "NORMAL"
      elif hf < 0.12:
          level = "WATCH"
      else:
          level = "WARNING"

      hf_high = hf >= 0.12

      # ============================
      # ENVELOPE CONFIRMATION
      # ============================
      envelope = features.get("envelope_rms", 0.0)
      envelope_high = envelope > 0.02   # example threshold

      # ============================
      # VELOCITY ISO ZONE
      # ============================
      vel = features.get("overall_vel_rms_mm_s", 0.0)
      if vel < 1.8:
          velocity_zone = "A"
      elif vel < 2.8:
          velocity_zone = "B"
      elif vel < 4.5:
          velocity_zone = "C"
      else:
          velocity_zone = "D"

      # ============================
      # TEMPERATURE
      # ============================
      temp = features.get("temperature_c", 0.0)
      temperature_alarm = temp >= 80.0

      dominant_feature = max(
          features,
          key=lambda k: abs(features[k])
      )

      return TrendResult(
          level=level,
          score=hf,
          dominant_feature=dominant_feature,
          hf_high=hf_high,
          envelope_high=envelope_high,
          velocity_zone=velocity_zone,
          temperature_alarm=temperature_alarm,
      )
