# TLS cert layout used by docker-compose

Expected files:

- `infra/certs/ca/ca.crt`
- `infra/certs/mqtt/mosquitto.crt`
- `infra/certs/mqtt/mosquitto.key`
- `infra/certs/mqtt/client1.crt`
- `infra/certs/mqtt/client1.key`
- `infra/certs/mqtt/client2.crt`
- `infra/certs/mqtt/client2.key`
- `infra/certs/mqtt/client3.crt`
- `infra/certs/mqtt/client3.key`
- `infra/certs/mqtt/ingestor.crt`
- `infra/certs/mqtt/ingestor.key`
- `infra/certs/mqtt/django.crt`
- `infra/certs/mqtt/django.key`
- `infra/certs/modbus/modbus-server.crt`
- `infra/certs/modbus/modbus-server.key`
- `infra/certs/modbus/modbus-client.crt`
- `infra/certs/modbus/modbus-client.key`

All cert directories are mounted read-only as `/certs` in Python service containers and as
`/mosquitto/certs` in the mosquitto container.
