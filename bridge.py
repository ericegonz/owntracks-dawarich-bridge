#!/usr/bin/env python3
"""OwnTracks MQTT to Dawarich bridge."""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from typing import Any

import paho.mqtt.client as mqtt
import requests


LOGGER = logging.getLogger("owntracks-dawarich-bridge")
MQTT_CLIENT: mqtt.Client | None = None
HTTP_SESSION = requests.Session()
CONFIG: dict[str, Any] = {}
SHUTDOWN_REQUESTED = False


def configure_logging() -> None:
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def get_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} environment variable is required")
    return value


def load_config() -> dict[str, Any]:
    try:
        mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
    except ValueError as exc:
        raise ValueError("MQTT_PORT must be an integer") from exc

    try:
        request_timeout = float(os.getenv("REQUEST_TIMEOUT", "10"))
    except ValueError as exc:
        raise ValueError("REQUEST_TIMEOUT must be a number") from exc

    return {
        "mqtt_host": os.getenv("MQTT_HOST", "mosquitto"),
        "mqtt_port": mqtt_port,
        "mqtt_username": os.getenv("MQTT_USERNAME", "recorder"),
        "mqtt_password": get_required_env("MQTT_PASSWORD"),
        "mqtt_topic": os.getenv("MQTT_TOPIC", "owntracks/#"),
        "dawarich_url": os.getenv("DAWARICH_URL", "http://dawarich_app:3000").rstrip("/"),
        "dawarich_api_key": get_required_env("DAWARICH_API_KEY"),
        "request_timeout": request_timeout,
    }


def on_connect(client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:
    if reason_code == 0:
        LOGGER.info("Connected to MQTT broker at %s:%s", CONFIG["mqtt_host"], CONFIG["mqtt_port"])
        client.subscribe(CONFIG["mqtt_topic"])
        LOGGER.info("Subscribed to topic: %s", CONFIG["mqtt_topic"])
        return

    LOGGER.error("Failed to connect to MQTT broker, return code: %s", reason_code)


def on_disconnect(
    client: mqtt.Client,
    userdata: Any,
    disconnect_flags: Any,
    reason_code: Any,
    properties: Any,
) -> None:
    if SHUTDOWN_REQUESTED:
        LOGGER.info("Disconnected from MQTT broker")
        return

    LOGGER.warning("Unexpected disconnection from MQTT broker, return code: %s", reason_code)


def on_message(client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except json.JSONDecodeError as exc:
        LOGGER.warning("Failed to parse JSON from topic '%s': %s", msg.topic, exc)
        return
    except UnicodeDecodeError as exc:
        LOGGER.warning("Failed to decode payload from topic '%s': %s", msg.topic, exc)
        return

    if not isinstance(payload, dict):
        LOGGER.debug("Ignoring non-object payload on topic '%s'", msg.topic)
        return

    if payload.get("_type") != "location":
        LOGGER.debug("Ignoring non-location message type: %s", payload.get("_type", "unknown"))
        return

    forward_to_dawarich(msg.topic, payload)


def forward_to_dawarich(topic: str, location_data: dict[str, Any]) -> None:
    payload = dict(location_data)
    payload["topic"] = topic

    try:
        response = HTTP_SESSION.post(
            f"{CONFIG['dawarich_url']}/api/v1/owntracks/points",
            params={"api_key": CONFIG["dawarich_api_key"]},
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=CONFIG["request_timeout"],
        )
    except requests.exceptions.Timeout:
        LOGGER.error("Timeout while forwarding to Dawarich for topic '%s'", topic)
        return
    except requests.exceptions.ConnectionError as exc:
        LOGGER.error("Connection error while forwarding to Dawarich: %s", exc)
        return
    except requests.RequestException as exc:
        LOGGER.error("Request error while forwarding to Dawarich: %s", exc)
        return

    if response.status_code in (200, 201, 204):
        LOGGER.info(
            "Successfully forwarded location from topic '%s' to Dawarich (lat: %s, lon: %s, timestamp: %s)",
            topic,
            payload.get("lat"),
            payload.get("lon"),
            payload.get("tst"),
        )
        return

    LOGGER.error(
        "Failed to forward to Dawarich. Status: %s, Response: %s",
        response.status_code,
        response.text,
    )


def signal_handler(signum: int, frame: Any) -> None:
    del frame
    global SHUTDOWN_REQUESTED
    SHUTDOWN_REQUESTED = True
    LOGGER.info("Received signal %s, initiating graceful shutdown...", signum)
    if MQTT_CLIENT is not None:
        MQTT_CLIENT.disconnect()


def connect_with_retries(client: mqtt.Client, max_retries: int = 5, retry_delay: int = 5) -> None:
    for attempt in range(1, max_retries + 1):
        try:
            LOGGER.info("Connecting to MQTT broker (attempt %s/%s)...", attempt, max_retries)
            client.connect(CONFIG["mqtt_host"], CONFIG["mqtt_port"], keepalive=60)
            return
        except Exception as exc:
            LOGGER.error("Failed to connect to MQTT broker: %s", exc)
            if attempt == max_retries:
                raise
            LOGGER.info("Retrying in %s seconds...", retry_delay)
            time.sleep(retry_delay)


def main() -> int:
    global CONFIG, MQTT_CLIENT

    configure_logging()

    try:
        CONFIG = load_config()
    except ValueError as exc:
        LOGGER.error(str(exc))
        return 1

    LOGGER.info("Starting OwnTracks to Dawarich bridge...")
    LOGGER.info("MQTT Broker: %s:%s", CONFIG["mqtt_host"], CONFIG["mqtt_port"])
    LOGGER.info("MQTT Topic: %s", CONFIG["mqtt_topic"])
    LOGGER.info("Dawarich URL: %s", CONFIG["dawarich_url"])

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    MQTT_CLIENT = mqtt.Client(
        client_id="owntracks-dawarich-bridge",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    MQTT_CLIENT.username_pw_set(CONFIG["mqtt_username"], CONFIG["mqtt_password"])
    MQTT_CLIENT.on_connect = on_connect
    MQTT_CLIENT.on_disconnect = on_disconnect
    MQTT_CLIENT.on_message = on_message

    try:
        connect_with_retries(MQTT_CLIENT)
    except Exception:
        LOGGER.error("Max connection retries reached, exiting")
        return 1

    try:
        LOGGER.info("Bridge is running. Press Ctrl+C to stop.")
        MQTT_CLIENT.loop_forever()
    except KeyboardInterrupt:
        LOGGER.info("Keyboard interrupt received")
    finally:
        if MQTT_CLIENT is not None:
            MQTT_CLIENT.disconnect()
        HTTP_SESSION.close()
        LOGGER.info("Bridge stopped")

    return 0


if __name__ == "__main__":
    sys.exit(main())