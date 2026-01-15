class TrendResult:
    def __init__(self, level, score, dominant_feature=None):
        self.level = level              # "NORMAL" | "WATCH" | "WARNING"
        self.score = score
        self.dominant_feature = dominant_feature


class TrendDetector:
    def __init__(self, history_size=10):
        self._history = {}
        self.history_size = history_size

    def update(self, asset, point, features):
        key = (asset, point)

        hist = self._history.setdefault(key, [])
        hist.append(features)

        if len(hist) > self.history_size:
            hist.pop(0)

        # ---- VERY SIMPLE TREND LOGIC (LOCKED VERSION) ----
        score = abs(features["acc_hf_rms_g"])

        if score < 0.05:
            level = "NORMAL"
        elif score < 0.12:
            level = "WATCH"
        else:
            level = "WARNING"

        dominant_feature = max(features, key=lambda k: abs(features[k]))

        return TrendResult(
            level=level,
            score=score,
            dominant_feature=dominant_feature,
        )

