# Monitoreo (Prometheus)

## Archivo principal

`monitoring/prometheus-vgw-monitoring.yaml` define los **scrape jobs adicionales** que se cargan en el `Prometheus` operado por `kube-prometheus-stack` en el namespace `observability`.

## Scrape jobs

| Job | Target | Path | Interval |
|---|---|---|---|
| `vgw-dev` | `172.16.220.51:9080` | `/metrics` | 1s |
| `vgw-cl` | `172.16.220.51:9081` | `/metrics/` | 1s |
| `vgw-int` | `172.16.220.51:9082` | `/metrics/` | 1s |
| `vgw-gen` | `172.16.220.51:9083` | `/metrics/` | 1s |
| `nvidia-gpu-monitoring` | `10.0.0.5:8740` | `/metrics` | 1s |
| `nvidia-node-monitoring` | `10.0.0.5:9100` | `/metrics` | 1s |

> **Inconsistencia conocida**: los deploys de `dev` y `gen` ponen `HTTP_HOST=10.0.0.6` pero el scrape va contra `172.16.220.51`. En CL/INT está OK. Ver nota en [environments.md](environments.md#http_host-donde-escucha-metrics).

> Hay jobs **comentados** en el YAML (`backend-bot-gen`, `discador-monitoring`, `asterisk-monitoring`) — son scraping de servicios fuera del cluster que se desactivaron pero quedaron como referencia.

## Cómo se carga (procedimiento original del README)

El procedimiento que usa el repo (transcrito de `monitoring/README.md`):

```bash
# 1. Editar el scrape config si hace falta
vim vgw_deploy/monitoring/prometheus-vgw-monitoring.yaml

# 2. Generar el secret en formato dry-run
kubectl create secret generic additional-scrape-configs \
  --from-file=vgw_deploy/monitoring/prometheus-vgw-monitoring.yaml \
  --dry-run=client -oyaml > additional-scrape-configs.yaml

# 3. Aplicarlo en el namespace observability
kubectl apply -f additional-scrape-configs.yaml -n observability

# 4. Verificar
kubectl -n observability get secrets | grep scrape

# 5. Editar el CR Prometheus para que use el secret
kubectl -n observability edit prometheus
```

En el `edit` se agrega/asegura este bloque al `spec`:

```yaml
additionalScrapeConfigs:
  name: additional-scrape-configs
  key: prometheus-vgw-monitoring.yaml
```

El operator detecta el cambio y regenera el `ConfigMap` que monta el Prometheus. Toma ~30s en aparecer los nuevos targets.

## Verificación rápida

```bash
# Targets activos
kubectl -n observability port-forward svc/kube-prom-stack-kube-prome-prometheus 9090:9090
# luego abrir http://localhost:9090/targets y filtrar "vgw-"

# Métricas crudas desde fuera del cluster
curl http://172.16.220.51:9081/metrics/ | grep -E '^vgw_'
```

## Métricas clave de VGW

Las que valen la pena alertar (sin pretender ser exhaustivo):

| Métrica | Qué medir |
|---|---|
| `vgw_active_calls` | Llamadas concurrentes — si llega cerca del límite del nodo, hay que sacar tenants a otro env |
| `vgw_call_setup_time_seconds` | Tiempo de setup SIP — picos = problema de red al SBC |
| `vgw_stt_latency_*` | Habilitada por `STT_TRACK_LATENCY=true` — vigilar p95 |
| `vgw_tts_latency_*` | Idem TTS |
| `vgw_rtcp_packet_loss` | Pérdida RTCP — si supera el `RTCP_MAX_PACKET_LOSS_THRESHOLD` la llamada se corta |

## Scripts de latencia ad-hoc

Cuando hay duda de latencia *fuera* de Prometheus (ej. después de un cambio de red), los scripts en la raíz hacen pings HTTP simples:

- `latency_avg.py` — mide los 4 endpoints NVIDIA TTS/STT internos (`172.16.220.46:3000-3003`).
- `one_latency_avg.py` — mide endpoints alternativos (NLP adapter, Azure TTS, etc.).

Edita la lista `endpoints = [...]` y ejecuta `python latency_avg.py`. Hace 100 / 1000 GETs por endpoint y devuelve el promedio en ms.

## Auditoría manual de peticiones (`petitionsCMD/cmd.sh`)

One-liners awk para `trace-mr.log`. **Hay que ajustar la fecha** (`2024-09-30` en el script) antes de usarlo:

```bash
# Peticiones por minuto
cat trace-mr.log.0 | grep "<YYYY-MM-DD>" \
  | grep -E "<tenant1>|<tenant2>" \
  | grep -E "<TTS-host1>|<TTS-host2>" \
  | awk '{match($0, /<YYYY-MM-DD>T[0-9]{2}:[0-9]{2}/); print substr($0, RSTART, RLENGTH)}' \
  | sort | uniq -c | awk '{print $2, $1}'

# Peticiones por hora
# (mismo pero con T[0-9]{2} en el regex)
```

Útil para post-mortem cuando Prometheus no estaba activo o falla.
