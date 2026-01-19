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
    # HEARTBEAT
    # =========================
    heartbeat = Heartbeat(service_name="vibralyzer")
    last_heartbeat_ts = time.time()
    HEARTBEAT_INTERVAL = config.get("heartbeat", {}).get("interval_sec", 10)

    # =========================
    # BASELINE
    # =========================
    baseline = AdaptiveBaseline(
        alpha=config.get("baseline", {}).get("alpha", 0.01),
        min_samples=config.get("baseline", {}).get("min_samples", 100),
    )

    # =========================
    # L2 SYSTEM
    # =========================
    l2_cooldown = L2CooldownManager(
        warning_sec=config["l2"]["cooldown_warning_sec"],
        alarm_sec=config["l2"]["cooldown_alarm_sec"],
    )

    l2_queue = L2JobQueue(maxsize=10)
    l2_queue.start(l2_worker)

    # =========================
    # CORE PIPELINE
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

        # ---- WINDOW ----
        window = ring_buffers.get_window(asset_id, point)

        # ---- L1 FEATURES ----
        heartbeat.mark_l1_exec()
        l1_features = l1_pipeline.compute(window)

        l1_snapshot = {
            "asset": asset_id,
            "point": point,
            "features": l1_features,
            "timestamp": time.time(),
        }

        # ---- TREND (RAW SPACE) ----
        raw_trend = trend_detector.update(
            asset_id,
            point,
            l1_features,
        )

        # ---- BASELINE UPDATE ----
        baseline.update(
            asset_id,
            point,
            l1_features,
            allow_update=(raw_trend.level == "NORMAL"),
        )

        # ---- PERSISTENCE ----
        persistence = persistence_checker.update(
            asset_id,
            point,
            raw_trend,
        )

        # ---- EARLY FAULT FSM ----
        heartbeat.mark_early_fault_exec()
        early_fault = early_fault_fsm.update(
            asset=asset_id,
            point=point,
            trend=raw_trend,
            persistence=persistence,
        )

        early_fault_event = {
            "asset": asset_id,
            "point": point,
            "early_fault": early_fault.state.value in ("WARNING", "ALARM"),
            "state": early_fault.state.value,
            "confidence": early_fault.confidence,
            "dominant_feature": early_fault.dominant_feature,
            "timestamp": early_fault.timestamp,
        }
        
        # ---- SCADA SNAPSHOT ----
        scada_payload = {
            "asset": asset_id,
            "point": point,

            # --- ACC ---
            "acceleration_rms_g": l1_features["acc_rms_g"],
            "acc_peak_g": l1_features["acc_peak_g"],
            "acc_hf_rms_g": l1_features["acc_hf_rms_g"],
            "crest_factor": l1_features["crest_factor"],
            "envelope_rms": l1_features["envelope_rms"],

            # --- VELOCITY (ISO) ---
            "overall_vel_rms_mm_s": l1_features["overall_vel_rms_mm_s"],

            # --- TEMP (EXT / OPTIONAL) ---
            "temperature_c": raw_payload.get("temperature"),

            # --- FSM ---
            "early_fault": early_fault.state.value in ("WARNING", "ALARM"),
            "state": early_fault.state.value,
            "confidence": early_fault.confidence,

            "timestamp": time.time(),
        }

        # ---- PUBLISH SCADA ----   
        publisher.publish_scada(asset_id, point, scada_payload)

        # ---- PUBLISH EARLY FAULT ----
        publisher.publish_early_fault(
            asset_id,
            point,
            early_fault_event,
        )

        # ---- L2 TRIGGER ----
        if config["l2"]["enable"] and early_fault.state.value in ("WARNING", "ALARM"):
            if l2_cooldown.can_trigger(asset_id, point, early_fault.state.value):
                job = {
                    "asset": asset_id,
                    "point": point,
                    "window": window,
                    "l1_snapshot": l1_snapshot,
                    "early_fault_event": early_fault_event,
                    "publisher": publisher,
                }

                if l2_queue.enqueue(job):
                    heartbeat.mark_l2_exec()
                    l2_cooldown.mark_triggered(asset_id, point)

        # ---- HEARTBEAT ----
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


