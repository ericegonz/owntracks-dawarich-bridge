# OwnTracks to Dawarich Bridge

Small Python service that subscribes to OwnTracks MQTT messages and forwards location updates to Dawarich.

## What It Does

- Subscribes to an OwnTracks MQTT topic such as `owntracks/#`
- Filters for OwnTracks location events
- Forwards those events to Dawarich's OwnTracks-compatible API
- Runs as a small Docker container with no database or local state

## Environment Variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `MQTT_HOST` | No | `mosquitto` | MQTT broker hostname |
| `MQTT_PORT` | No | `1883` | MQTT broker port |
| `MQTT_USERNAME` | No | `recorder` | MQTT username |
| `MQTT_PASSWORD` | Yes | - | MQTT password |
| `MQTT_TOPIC` | No | `owntracks/#` | Topic subscription pattern |
| `DAWARICH_URL` | Yes | - | Base URL for Dawarich |
| `DAWARICH_API_KEY` | Yes | - | Dawarich API key |
| `LOG_LEVEL` | No | `INFO` | Python log level |
| `REQUEST_TIMEOUT` | No | `10` | HTTP timeout in seconds |

## Quick Start

1. Copy the example environment file.

```bash
cp .env.example .env
```

2. Edit `.env` with your MQTT and Dawarich settings.

3. Build and start the bridge.

```bash
docker compose up -d --build
```

4. Follow the logs.

```bash
docker compose logs -f
```

## Example Compose Usage

The included `docker-compose.yml` is intentionally generic. It assumes the bridge can reach your MQTT broker and Dawarich instance using the hostnames or URLs from `.env`.

If your MQTT broker and Dawarich run in a different Docker Compose project, you have two common options:

1. Put all services on a shared external Docker network.
2. Point `MQTT_HOST` and `DAWARICH_URL` at routable hostnames or IPs.

## Local Development

Run the script directly:

```bash
pip install -r requirements.txt
cp .env.example .env
python bridge.py
```

## Build the Container Manually

```bash
docker build -t ericegonz/owntracks-dawarich-bridge:local .
```

## Publish to Docker Hub

```bash
docker build -t ericegonz/owntracks-dawarich-bridge:tagname .
docker push ericegonz/owntracks-dawarich-bridge:tagname
```

## Notes

- The bridge only forwards OwnTracks messages where `_type` is `location`.
- The forwarded payload includes the original MQTT topic as `topic`.
- No location data is stored locally by the bridge.