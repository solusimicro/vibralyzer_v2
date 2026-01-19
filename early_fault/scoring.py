import time
from enum import Enum


class EarlyFaultState(Enum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    WARNING = "WARNING"
    ALARM = "ALARM"


class EarlyFaultResult:
    def __init__(self, state, confidence, dominant_feature=None):
        self.state = state
        self.confidence = confidence
        self.dominant_feature = dominant_feature
        self.timestamp = time.time()


class EarlyFaultFSM:
    def __init__(
        self,
        watch_persistence=3,
        warning_persistence=5,
        alarm_persistence=8,
        hysteresis_clear=3,
    ):
        self.watch_persistence = watch_persistence
        self.warning_persistence = warning_persistence
        self.alarm_persistence = alarm_persistence
        self.hysteresis_clear = hysteresis_clear

        self._state = {}
        self._clear_counter = {}

    def update(self, asset, point, trend, persistence):
        key = (asset, point)
        state = self._state.get(key, EarlyFaultState.NORMAL)

        clear = self._clear_counter.get(key, 0)

        # =========================
        # CRITICAL OVERRIDES (L3)
        # =========================
        if trend.temperature_alarm:
            state = EarlyFaultState.ALARM

        elif trend.velocity_zone == "D":
            state = EarlyFaultState.ALARM

        elif (
            trend.hf_high
            and trend.envelope_high
            and persistence >= self.alarm_persistence
        ):
            state = EarlyFaultState.ALARM

        # =========================
        # WARNING (L2)
        # =========================
        elif (
            trend.hf_high
            and trend.envelope_high
            and persistence >= self.warning_persistence
        ):
            state = EarlyFaultState.WARNING

        elif trend.velocity_zone == "C":
            state = EarlyFaultState.WARNING

        # =========================
        # WATCH (L1)
        # =========================
        elif trend.hf_high and persistence >= self.watch_persistence:
            state = EarlyFaultState.WATCH

        # =========================
        # CLEAR / DOWNGRADE
        # =========================
        elif trend.level == "NORMAL":
            clear += 1
            if clear >= self.hysteresis_clear:
                state = self._downgrade(state)
                clear = 0

        else:
            clear = 0

        self._state[key] = state
        self._clear_counter[key] = clear

        confidence = self._estimate_confidence(trend, persistence, state)

        return EarlyFaultResult(
            state=state,
            confidence=confidence,
            dominant_feature=trend.dominant_feature,
        )

    def _downgrade(self, state):
        if state == EarlyFaultState.ALARM:
            return EarlyFaultState.WARNING
        if state == EarlyFaultState.WARNING:
            return EarlyFaultState.WATCH
        return EarlyFaultState.NORMAL

    def _estimate_confidence(self, trend, persistence, state):
        severity_score = 0.0
        if trend.velocity_zone in ("C", "D"):
            severity_score = 1.0
        elif trend.envelope_high:
            severity_score = 0.7
        elif trend.hf_high:
            severity_score = 0.4

        persistence_score = min(1.0, persistence / self.alarm_persistence)

        state_score = {
            EarlyFaultState.NORMAL: 0.2,
            EarlyFaultState.WATCH: 0.5,
            EarlyFaultState.WARNING: 0.75,
            EarlyFaultState.ALARM: 1.0,
        }[state]

        confidence = (
            0.4 * severity_score +
            0.4 * persistence_score +
            0.2 * state_score
        )

        return round(min(1.0, confidence), 2)

