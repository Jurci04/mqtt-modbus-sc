.PHONY: help test test-django test-e2e run-ingestor run-client run-modbus-server run-modbus-client sub-telemetry certs broker-users plot

ifneq (,$(wildcard .env))
include .env
export
endif

help:
	@echo "Targets:"
	@echo "  test          Run MQTT unit tests"
	@echo "  test-django   Run Django API tests against local Postgres"
	@echo "  test-e2e      Run API smoke flow (quotes + MQTT stop/start)"
	@echo "  run-ingestor  Run MQTT ingestor process locally"
	@echo "  run-client    Run all 3 MQTT clients locally (BTC, ETH, LTC)"
	@echo "  run-modbus-server Run Modbus TLS quote server"
	@echo "  run-modbus-client Run Modbus TLS quote client"
	@echo "  certs         Create missing CA/service TLS certs and keys"
	@echo "  broker-users  Create/update mosquitto passwd users from .env"
	@echo "  sub-telemetry Subscribe to telemetry through the Mosquitto container"
	@echo "  plot          Render MQTT/Modbus trend charts from MongoDB"

test:
	uv run --extra dev pytest tests/test_mqtt_client.py tests/test_mqtt_ingestor.py tests/test_modbus_server.py tests/test_modbus_client.py -q

test-django:
	DJANGO_DB_HOST=localhost DJANGO_DB_PORT=5432 uv run --extra dev pytest tests/test_api_django.py -q

test-e2e:
	curl -sS "http://127.0.0.1:8000/api/mqtt/quotes/?limit=5&client_id=mqtt-client-1"; echo
	curl -sS "http://127.0.0.1:8000/api/mqtt/quotes/?limit=5&client_id=mqtt-client-2"; echo
	curl -sS "http://127.0.0.1:8000/api/mqtt/quotes/?limit=5&client_id=mqtt-client-3"; echo
	curl -sS -X POST "http://127.0.0.1:8000/api/service/mqtt-client-1/command/" -H "Content-Type: application/json" -d '{"command":"stop"}'; echo
	sleep 2
	curl -sS "http://127.0.0.1:8000/api/mqtt/quotes/?limit=5&client_id=mqtt-client-1"; echo
	curl -sS "http://127.0.0.1:8000/api/mqtt/quotes/?limit=5&client_id=mqtt-client-2"; echo
	curl -sS "http://127.0.0.1:8000/api/mqtt/quotes/?limit=5&client_id=mqtt-client-3"; echo
	curl -sS -X POST "http://127.0.0.1:8000/api/service/mqtt-client-1/command/" -H "Content-Type: application/json" -d '{"command":"start"}'; echo

run-ingestor:
	MQTT_HOST=localhost MONGO_HOST=localhost \
	MQTT_USERNAME="$(MQTT_INGESTOR_USERNAME)" MQTT_PASSWORD="$(MQTT_INGESTOR_PASSWORD)" \
	MQTT_TLS_CA_CERT=infra/certs/ca/ca.crt \
	MQTT_TLS_CLIENT_CERT=infra/certs/mqtt/ingestor.crt \
	MQTT_TLS_CLIENT_KEY=infra/certs/mqtt/ingestor.key \
	uv run python -c "from services.mqtt.ingestor.core import run; run()"

run-client:
	@set -e; \
	pids=""; \
	CLIENT_ID=mqtt-client-1 ASSET_ID=bitcoin SYMBOL=BTC MQTT_HOST=localhost \
		MQTT_USERNAME="$(MQTT_CLIENT_1_USERNAME)" MQTT_PASSWORD="$(MQTT_CLIENT_1_PASSWORD)" \
		MQTT_TLS_CA_CERT=infra/certs/ca/ca.crt \
		MQTT_TLS_CLIENT_CERT=infra/certs/mqtt/client1.crt \
		MQTT_TLS_CLIENT_KEY=infra/certs/mqtt/client1.key \
		.venv/bin/python -c "from services.mqtt.client.core import run; run()" & pids="$$pids $$!"; \
	CLIENT_ID=mqtt-client-2 ASSET_ID=ethereum SYMBOL=ETH MQTT_HOST=localhost \
		MQTT_USERNAME="$(MQTT_CLIENT_2_USERNAME)" MQTT_PASSWORD="$(MQTT_CLIENT_2_PASSWORD)" \
		MQTT_TLS_CA_CERT=infra/certs/ca/ca.crt \
		MQTT_TLS_CLIENT_CERT=infra/certs/mqtt/client2.crt \
		MQTT_TLS_CLIENT_KEY=infra/certs/mqtt/client2.key \
		.venv/bin/python -c "from services.mqtt.client.core import run; run()" & pids="$$pids $$!"; \
	CLIENT_ID=mqtt-client-3 ASSET_ID=litecoin SYMBOL=LTC MQTT_HOST=localhost \
		MQTT_USERNAME="$(MQTT_CLIENT_3_USERNAME)" MQTT_PASSWORD="$(MQTT_CLIENT_3_PASSWORD)" \
		MQTT_TLS_CA_CERT=infra/certs/ca/ca.crt \
		MQTT_TLS_CLIENT_CERT=infra/certs/mqtt/client3.crt \
		MQTT_TLS_CLIENT_KEY=infra/certs/mqtt/client3.key \
		.venv/bin/python -c "from services.mqtt.client.core import run; run()" & pids="$$pids $$!"; \
	trap 'kill $$pids 2>/dev/null || true' INT TERM EXIT; \
	wait

run-modbus-server:
	MODBUS_HOST=localhost \
	MODBUS_TLS_CA_CERT=infra/certs/ca/ca.crt \
	MODBUS_TLS_CLIENT_CERT=infra/certs/modbus/modbus-server.crt \
	MODBUS_TLS_CLIENT_KEY=infra/certs/modbus/modbus-server.key \
	uv run python -c "from services.modbus.server.core import run; run()"

run-modbus-client:
	MODBUS_HOST=localhost MONGO_HOST=localhost \
	MODBUS_TLS_CA_CERT=infra/certs/ca/ca.crt \
	MODBUS_TLS_CLIENT_CERT=infra/certs/modbus/modbus-client.crt \
	MODBUS_TLS_CLIENT_KEY=infra/certs/modbus/modbus-client.key \
	uv run python -c "from services.modbus.client.core import run; run()"

sub-telemetry:
	docker compose exec mosquitto mosquitto_sub -h localhost -p "$(MQTT_PORT)" \
		--cafile /mosquitto/certs/ca/ca.crt \
		--cert /mosquitto/certs/mqtt/ingestor.crt \
		--key /mosquitto/certs/mqtt/ingestor.key \
		-u "$(MQTT_INGESTOR_USERNAME)" -P "$(MQTT_INGESTOR_PASSWORD)" \
		-t 'easycon/clients/+/telemetry/crypto' -v

certs:
	@set -e; \
	command -v openssl >/dev/null || { echo "openssl is required"; exit 1; }; \
	mkdir -p infra/certs/ca infra/certs/mqtt infra/certs/modbus; \
	[ -f infra/certs/mqtt/mosquitto.conf ] || { echo "Missing committed file: infra/certs/mqtt/mosquitto.conf"; exit 1; }; \
	[ -f infra/certs/modbus/modbus-server.conf ] || { echo "Missing committed file: infra/certs/modbus/modbus-server.conf"; exit 1; }; \
	if [ ! -f infra/certs/ca/ca.crt ] || [ ! -f infra/certs/ca/ca.key ]; then \
		openssl req -x509 -newkey rsa:4096 -keyout infra/certs/ca/ca.key -out infra/certs/ca/ca.crt -sha256 -days 3650 -nodes \
			-config infra/certs/ca/ca.cnf; \
	fi; \
	[ -f infra/certs/mqtt/mosquitto.key ] || openssl genrsa -out infra/certs/mqtt/mosquitto.key 2048; \
	[ -f infra/certs/mqtt/mosquitto.csr ] || openssl req -new -key infra/certs/mqtt/mosquitto.key -out infra/certs/mqtt/mosquitto.csr -config infra/certs/mqtt/mosquitto.conf; \
	[ -f infra/certs/mqtt/mosquitto.crt ] || openssl x509 -req -in infra/certs/mqtt/mosquitto.csr -CA infra/certs/ca/ca.crt -CAkey infra/certs/ca/ca.key -CAcreateserial -out infra/certs/mqtt/mosquitto.crt -days 825 -sha256 -extensions req_ext -extfile infra/certs/mqtt/mosquitto.conf; \
	for c in client1 client2 client3 ingestor django; do \
		[ -f infra/certs/mqtt/$$c.key ] || openssl genrsa -out infra/certs/mqtt/$$c.key 2048; \
		[ -f infra/certs/mqtt/$$c.csr ] || openssl req -new -key infra/certs/mqtt/$$c.key -out infra/certs/mqtt/$$c.csr -subj "/C=CZ/ST=Prague/L=Prague/O=Easycon/OU=Dev/CN=$$c"; \
		[ -f infra/certs/mqtt/$$c.crt ] || openssl x509 -req -in infra/certs/mqtt/$$c.csr -CA infra/certs/ca/ca.crt -CAkey infra/certs/ca/ca.key -CAcreateserial -out infra/certs/mqtt/$$c.crt -days 825 -sha256; \
	done; \
	[ -f infra/certs/modbus/modbus-server.key ] || openssl genrsa -out infra/certs/modbus/modbus-server.key 2048; \
	[ -f infra/certs/modbus/modbus-server.csr ] || openssl req -new -key infra/certs/modbus/modbus-server.key -out infra/certs/modbus/modbus-server.csr -config infra/certs/modbus/modbus-server.conf; \
	[ -f infra/certs/modbus/modbus-server.crt ] || openssl x509 -req -in infra/certs/modbus/modbus-server.csr -CA infra/certs/ca/ca.crt -CAkey infra/certs/ca/ca.key -CAcreateserial -out infra/certs/modbus/modbus-server.crt -days 825 -sha256 -extensions req_ext -extfile infra/certs/modbus/modbus-server.conf; \
	[ -f infra/certs/modbus/modbus-client.key ] || openssl genrsa -out infra/certs/modbus/modbus-client.key 2048; \
	[ -f infra/certs/modbus/modbus-client.csr ] || openssl req -new -key infra/certs/modbus/modbus-client.key -out infra/certs/modbus/modbus-client.csr -config infra/certs/modbus/modbus-client.conf; \
	[ -f infra/certs/modbus/modbus-client.crt ] || openssl x509 -req -in infra/certs/modbus/modbus-client.csr -CA infra/certs/ca/ca.crt -CAkey infra/certs/ca/ca.key -CAcreateserial -out infra/certs/modbus/modbus-client.crt -days 825 -sha256; \
	chmod 755 infra/certs infra/certs/ca infra/certs/mqtt infra/certs/modbus; \
	chmod 600 infra/certs/ca/ca.key infra/certs/mqtt/*.key infra/certs/modbus/*.key; \
	chmod 644 infra/certs/mqtt/mosquitto.key; \
	chmod 644 infra/certs/ca/ca.crt infra/certs/mqtt/*.crt infra/certs/modbus/*.crt; \
	echo "certs: OK"

broker-users:
	@set -e; \
	command -v mosquitto_passwd >/dev/null || { echo "mosquitto_passwd is required"; exit 1; }; \
	[ -n "$(MQTT_CLIENT_1_USERNAME)" ] && [ -n "$(MQTT_CLIENT_1_PASSWORD)" ] || { echo "Missing MQTT_CLIENT_1_* env vars"; exit 1; }; \
	[ -n "$(MQTT_CLIENT_2_USERNAME)" ] && [ -n "$(MQTT_CLIENT_2_PASSWORD)" ] || { echo "Missing MQTT_CLIENT_2_* env vars"; exit 1; }; \
	[ -n "$(MQTT_CLIENT_3_USERNAME)" ] && [ -n "$(MQTT_CLIENT_3_PASSWORD)" ] || { echo "Missing MQTT_CLIENT_3_* env vars"; exit 1; }; \
	[ -n "$(MQTT_INGESTOR_USERNAME)" ] && [ -n "$(MQTT_INGESTOR_PASSWORD)" ] || { echo "Missing MQTT_INGESTOR_* env vars"; exit 1; }; \
	[ -n "$(MQTT_DJANGO_USERNAME)" ] && [ -n "$(MQTT_DJANGO_PASSWORD)" ] || { echo "Missing MQTT_DJANGO_* env vars"; exit 1; }; \
	mkdir -p infra/mosquitto; \
	if [ ! -f infra/mosquitto/passwd ]; then \
		mosquitto_passwd -b -c infra/mosquitto/passwd "$(MQTT_CLIENT_1_USERNAME)" "$(MQTT_CLIENT_1_PASSWORD)"; \
	else \
		mosquitto_passwd -b infra/mosquitto/passwd "$(MQTT_CLIENT_1_USERNAME)" "$(MQTT_CLIENT_1_PASSWORD)"; \
	fi; \
	mosquitto_passwd -b infra/mosquitto/passwd "$(MQTT_CLIENT_2_USERNAME)" "$(MQTT_CLIENT_2_PASSWORD)"; \
	mosquitto_passwd -b infra/mosquitto/passwd "$(MQTT_CLIENT_3_USERNAME)" "$(MQTT_CLIENT_3_PASSWORD)"; \
	mosquitto_passwd -b infra/mosquitto/passwd "$(MQTT_INGESTOR_USERNAME)" "$(MQTT_INGESTOR_PASSWORD)"; \
	mosquitto_passwd -b infra/mosquitto/passwd "$(MQTT_DJANGO_USERNAME)" "$(MQTT_DJANGO_PASSWORD)"; \
	chmod 644 infra/mosquitto/passwd; \
	echo "broker-users: OK (restart mosquitto to apply)"

plot:
	PYTHONPATH=. uv run --extra plot python scripts/plot_flows.py
