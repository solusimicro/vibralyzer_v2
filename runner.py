import time

from raw_ingest.mqtt_listener import start_mqtt_listener
from core.ring_buffer import RingBufferManager
from core.l1_feature_pipeline import L1FeaturePipeline
from early_fault.trend_detector import TrendDetector
from early_fault.persistence import PersistenceChecker
from early_fault.scoring import EarlyFaultFSM
from early_fault.baseline import AdaptiveBaseline
from publish.mqtt_publisher import MQTTPublisher
from config.config_loader import load_config
from diagnostic_l2.cooldown import L2CooldownManager
from diagnostic_l2.l2_queue import L2JobQueue
from diagnostic_l2.worker import l2_worker
from utils.heartbeat import Heartbeat


def main():
    # =========================
    # LOAD CONFIG
    # =========================
    config = load_config()

    # =========================
    # INIT HEARTBEAT
    # =========================
    heartbeat = Heartbeat(service_name="vibralyzer")
    last_heartbeat_ts = time.time()
    HEARTBEAT_INTERVAL = config.get("heartbeat", {}).get("interval_sec", 10)

    # =========================
    # INIT ADAPTIVE BASELINE
    # =========================
    baseline = AdaptiveBaseline(
        alpha=config.get("baseline", {}).get("alpha", 0.01),
        min_samples=config.get("baseline", {}).get("min_samples", 100),
    )

    # =========================
    # INIT L2 COOLDOWN + QUEUE
    # =========================
    l2_cooldown = L2CooldownManager(
        warning_sec=config["l2"]["cooldown_warning_sec"],
        alarm_sec=config["l2"]["cooldown_alarm_sec"],
    )

    l2_queue = L2JobQueue(maxsize=10)
    l2_queue.start(l2_worker)

    # =========================
    # INIT CORE COMPONENTS
    # =========================
    ring_buffers = RingBufferManager(
        window_size=config["raw"]["window_size"]
    )

    l1_pipeline = L1FeaturePipeline(
        fs=config["l1_feature"]["sampling_rate"],
        rpm=config["l1_feature"]["rpm_default"],
    )

    trend_detector = TrendDetector()
    persistence_checker = PersistenceChecker()

    early_fault_fsm = EarlyFaultFSM(
        watch_persistence=config["early_fault"]["watch_persistence"],
        warning_persistence=config["early_fault"]["warning_persistence"],
        alarm_persistence=config["early_fault"]["alarm_persistence"],
        hysteresis_clear=config["early_fault"]["hysteresis_clear"],
    )

    publisher = MQTTPublisher(
        broker=config["mqtt"]["broker"],
        port=config["mqtt"]["port"],
    )

    # =========================
    # RAW CALLBACK
    # =========================
    def on_raw_data(asset_id, point, raw_payload):
        nonlocal last_heartbeat_ts

        # ---- RAW RX ----
        heartbeat.mark_raw_rx()
        ring_buffers.append(asset_id, point, raw_payload)

        if not ring_buffers.is_window_ready(asset_id, point):
            return

        heartbeat.mark_window_ready()

        # ---- BUFFER → WINDOW ----
        window = ring_buffers.get_window(asset_id, point)

        # ---- L1 FEATURE (RAW FEATURE SPACE) ----
        heartbeat.mark_l1_exec()
        l1_features = l1_pipeline.compute(window)

        # ---- TREND DETECTION (RAW SPACE) ----
        trend = trend_detector.update(
            asset_id,
            point,
            l1_features,
        )

        # ---- BASELINE UPDATE (ONLY WHEN NORMAL) ----
        baseline.update(
            asset_id,
            point,
            l1_features,
            allow_update=(trend.level == "NORMAL"),
        )

        # ---- NORMALIZE FEATURES ----
        normalized_features = baseline.normalize(
            asset_id,
            point,
            l1_features,
        )

        # ---- TREND DETECTION (NORMALIZED SPACE) ----
        raw_trend = trend_detector.update(
            asset_id,
            point,
            normalized_features,
        )

        # ---- PERSISTENCE ----
        persistence = persistence_checker.update(
            asset_id,
            point,
            trend,
        )

        # ---- EARLY FAULT FSM ----
        heartbeat.mark_early_fault_exec()
        early_fault = early_fault_fsm.update(
            asset=asset_id,
            point=point,
            trend=trend,
            persistence=persistence,
        )

        # ---- PUBLISH EARLY FAULT ----
        publisher.publish_early_fault(
            asset_id,
            point,
            {
                "state": early_fault.state.value,
                "confidence": early_fault.confidence,
                "dominant_feature": early_fault.dominant_feature,
                "timestamp": early_fault.timestamp,
            },
        )

        # ---- L2 TRIGGER (ASYNC + COOLDOWN) ----
        state = early_fault.state.value

        if config["l2"]["enable"] and state in ("WARNING", "ALARM"):
            if l2_cooldown.can_trigger(asset_id, point, state):
                job = {
                    "asset": asset_id,
                    "point": point,
                    "window": window,
                    "publisher": publisher,
                }

                if l2_queue.enqueue(job):
                    heartbeat.mark_l2_exec()
                    l2_cooldown.mark_triggered(asset_id, point)

        # ---- HEARTBEAT PUBLISH ----
        now = time.time()
        if now - last_heartbeat_ts >= HEARTBEAT_INTERVAL:
            publisher.publish_heartbeat(heartbeat.snapshot())
            last_heartbeat_ts = now

    # =========================
    # START MQTT LISTENER
    # =========================
    start_mqtt_listener(
        callback=on_raw_data,
        broker=config["mqtt"]["broker"],
        port=config["mqtt"]["port"],
        topic=config["mqtt"]["raw_topic"],
    )


if __name__ == "__main__":
    main()

