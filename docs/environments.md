# Matriz de entornos

Este documento concentra los valores específicos de cada `env` para que no haya que abrir 5 JSONs cuando se busca un puerto o una IP.

## Resumen

| Env | Propósito | Pod name | Tenants |
|---|---|---|---|
| `dev` | Pruebas internas / staging | `vgw-dev-multitenant-deployment` | 1 (`5012Test`) |
| `cl` | Producción Chile (Ufinet) | `vgw-multitenant-deployment` | 3 (`SmartIA 20056 CHL`, `SmartIA 20056-2 CHL`, `SmartIA 5012 CHL`) |
| `int` | Producción internacional (8 países) | `vgw-int-multitenant-deployment` | 9 (`Test`, EC, CR, CO, GT, PE, MX, PA, SV) |
| `gen` | Bots generativos / Azure TTS | `vgw-gen-multitenant-deployment` | 5 (`SmartIA Gen 5006`, `MX Gen 5027`, `CO Gen 5024`, `SmartIA Azure TTS`, `SmartIA TTS Test`) |
| `pipecat` | Variante con media relay externo pipecat | `vgw-pipecat-multitenant-deployment` | 1 (`5012Test`) |

## Puertos por env (host = nodo K8s)

| Recurso | dev | cl | int | gen | pipecat |
|---|---|---|---|---|---|
| **SIP** (TCP+UDP) | 30200 | **30201** | 30202 | 30203 | 30191 |
| **MRCP/WS** (TCP) | 6200 | 6201 | 6202 | 6203 | _externo_ |
| **vgw-mr SIP** (TCP+UDP) | 5555 | 5556 | 5557 | 5558 | _no aplica_ |
| **JMS** | 7276 | 7277 | 7278 | 7279 | 7280 |
| **JMS SSL** | 7286 | 7287 | 7288 | 7289 | 7290 |
| **HTTP métricas** | 9080 | **9081** | 9082 | 9083 | 9089 |
| **HTTPS** | 9443 | 9444 | 9445 | 9446 | 9449 |
| **RTP UDP range** | 7000-8000 | 26001-35000 | 15000-25000 | 35001-40000 | _externo_ |

> **`cl` es el único en producción real con tráfico Ufinet** — su `SIP_PORT 30201` y `HTTP_PORT 9081` son los que importa monitorear primero.

## IPs anunciadas (`SDP_ADDRESS` / `SIP_HOST`)

| Env | Valor | Nota |
|---|---|---|
| `dev` | `128.24.57.99` | IP del nodo dev |
| `cl` | **`172.16.220.51`** | IP **interna** del nodo prod CL. **No usar la NAT pública** `200.62.8.140` — ver [operations.md](operations.md#incidente-rtp-truncado-por-nat-2026-04-30) |
| `int` | **`172.16.220.51`** | Mismo nodo que `cl` |
| `gen` | `128.24.57.99` | Mismo nodo que `dev` |
| `pipecat` | `128.24.57.99` | Mismo nodo que `dev` |

## `HTTP_HOST` (donde escucha `/metrics/`)

| Env | Valor | Coincide con scrape config |
|---|---|---|
| `dev` | `10.0.0.6` | `monitoring/prometheus-vgw-monitoring.yaml` apunta a `172.16.220.51:9080` — **inconsistencia detectada**: el deploy escucha en `10.0.0.6:9080` pero el scrape va contra `172.16.220.51:9080`. Validar antes de usar dev. |
| `cl` | `172.16.220.51` | OK (`172.16.220.51:9081`) |
| `int` | `172.16.220.51` | OK (`172.16.220.51:9082`) |
| `gen` | `10.0.0.6` | scrape va a `172.16.220.51:9083` — misma inconsistencia que dev |
| `pipecat` | `10.0.0.6` | sin scrape definido aún |

> Si Prometheus muestra los targets `vgw-dev` y `vgw-gen` en `DOWN`, casi seguro es esta discrepancia. Cuadrar `HTTP_HOST` del deploy con el target del scrape.

## Recursos (CPU / RAM) — `vgw-so`

| Env | requests | limits |
|---|---|---|
| `dev` | 0.2 / 0.5Gi | 0.5 / 1Gi |
| `cl` | 1 / 2Gi | 1.5 / 5Gi |
| `int` | 1 / 2Gi | 1.5 / 5Gi |
| `gen` | (default) | (default) |
| `pipecat` | 0.2 / 0.5Gi | 0.5 / 1Gi |

`vgw-mr` no declara `resources` en ningún env.

## Logs

| Env | `LOG_MAX_FILES` | `LOG_LEVEL` | `MEDIA_RELAY_LOG_LEVEL` |
|---|---|---|---|
| `dev` | 7 | all | DEBUG |
| `cl` | 14 | all | DEBUG |
| `int` | 14 | all | DEBUG |
| `gen` | 7 | all | DEBUG |
| `pipecat` | 7 | all | _N/A_ |

## NLP / Conversation por env

| Env | URL | Workspace |
|---|---|---|
| `dev` | `generic-nlp-adapter.services.smartia-ai.com/dialogflow` | placeholder |
| `cl` | `generic-nlp-adapter.services3.smartia-ai.com/dialogflow` | placeholder (Ufinet) |
| `int` | `generic-nlp-adapter.services.smartia-ai.com/dialogflow` | placeholder |
| `gen` | mezcla: `genbot-nlp-adapter…`, `generic-nlp-adapter…`, `mrcp-transfer-nlp-adapter…/user/10103/dialogflow` | varía por tenant |
| `pipecat` | `generic-nlp-adapter.services.smartia-ai.com/dialogflow` | placeholder |

## STT/TTS backend por env

| Env | STT backend | TTS backend | Voz |
|---|---|---|---|
| `dev` | `stt-multitenant-ts-2.nvidiaservices…` | `tts-multitenant-ts-2.nvidiaservices…` | `tts_spanish.111` |
| `cl` | `172.16.220.46:3002` o `:3003` | `172.16.220.46:3000` o `:3001` | `tts_spanish.56` |
| `int` | `172.16.220.46:3003` | `172.16.220.46:3001` | `tts_spanish.111` |
| `gen` | `stt-multitenant-ts.nvidiaservices2…` | `10.0.0.11:8001` (Azure) o `:8002` | (Azure default) |
| `pipecat` | `stt-multitenant-ts-2.nvidiaservices…` | `tts-multitenant-ts-2.nvidiaservices…` | `tts_spanish.111` |

## Variables de control de calidad (solo en algunos envs)

| Variable | Envs | Comentario |
|---|---|---|
| `RTCP_MAX_PACKET_LOSS_THRESHOLD=1` | `cl`, `int` (en `vgw-mr`) | No declarado en `dev`, `gen`, `pipecat` (queda default IBM) |
| `STT_TRACK_LATENCY=true` | todos los `vgw-mr` | — |
| `DISABLE_STT_DURING_PLAYBACK=true` | todos | Quitarlo solo si se quiere barge-in |

## Backups históricos (`multitenant/bk/`)

| Archivo | Origen |
|---|---|
| `aladino_deploy.json` | Snapshot del deployment del cliente Aladino — referencia histórica |
| `deploy.json.bak2024-10-24rigo` | Backup de `cl/deploy.json` previo a la migración del 2024-10-24 (autor: rigo) |

No se aplican; solo sirven como diff de referencia si hay que comparar configuraciones.
