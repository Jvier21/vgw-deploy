# Arquitectura

## Componentes del pod

Cada `deploy_*.json` despliega **un único pod** con dos containers:

```
                  ┌──────────────────── Pod ────────────────────┐
SIP/UDP/TCP  ───► │  vgw-so   (SIP orchestrator)                │
(30200-30203)     │  ├─ Acepta INVITE                           │
                  │  ├─ Selecciona tenant por SIP URI           │
                  │  ├─ Habla MRCP/REST con TTS/STT/NLP         │
                  │  ├─ Emite CDR/conversación a vgw-reporting  │
                  │  └─ Métricas Prometheus en HTTP_PORT        │
                  │       │                                     │
                  │       │ MRCP/WS local (localhost:6200..3)   │
                  │       ▼                                     │
RTP/UDP      ───► │  vgw-mr   (media relay)                     │
(5555-5558)       │  ├─ Term  ina RTP/RTCP                      │
                  │  ├─ Re-streamea audio al STT                │
                  │  ├─ Reproduce audio del TTS                 │
                  │  └─ Graba si ENABLE_RECORDING=true          │
                  └─────────────────────────────────────────────┘
```

`hostNetwork: true` significa que ambos containers usan directamente la interfaz del nodo (sin red de pods K8s). Por eso los **puertos no pueden colisionar** entre envs y por eso los `containerPort == hostPort` en todos los manifests.

## Flujo de una llamada

1. **PBX / SBC** envía `INVITE` a `<SIP_HOST>:<SIP_PORT>` (ej. `172.16.220.51:30201` para `cl`).
2. **vgw-so** recibe el INVITE, lee la `Request-URI` y la matchea contra cualquier `URIs[].uri` del `tenantConfiguration.json` cargado vía `MULTI_TENANT_CONFIG_FILE`.
3. Encuentra el tenant correspondiente y abre tres sesiones:
   - **STT** → `tenant.stt.providers[0].credentials.url` (NVIDIA Riva con compatibilidad Watson).
   - **TTS** → `tenant.tts.providers[0].credentials.url`.
   - **Conversation/NLP** → `tenant.conversation.url` (Dialogflow adapter).
4. Negocia SDP anunciando `SDP_ADDRESS:<RTP_UDP_PORT_RANGE>` (ej. `172.16.220.51:26001-35000` en `cl`).
5. **vgw-mr** recibe el RTP, lo demultiplexa, manda audio al STT y reproduce el audio que devuelve el TTS.
6. Cada turn dispara eventos contra `REPORTING_URL` (`vgw-reporting.services.smartia-ai.com/vgw/report`) en los índices `cdr`, `conversation` y `transcription`.

## Routing multitenant

VGW selecciona el tenant **por SIP URI** (no por puerto, no por IP origen). El SBC debe enviar el INVITE con la `Request-URI` o el `To:` URI igual a uno de los `URIs[].uri` declarados en el `tenantConfiguration.json`. Ejemplo:

```
INVITE sip:smartia001chl@172.16.220.51:30201 SIP/2.0
```

…matchea el tenant `SmartIA 20056 Chile` (URI `smartia001chl`). Si no hay match, vgw-so responde `404 Not Found` o `488` según versión.

## Variante pipecat

`multitenant/pipecat/deploy_pipecat.json` **solo despliega vgw-so**, no vgw-mr. En su lugar, `MEDIA_RELAY_HOST` apunta a un media relay externo basado en pipecat:

```
MEDIA_RELAY_HOST = 128.24.57.99:8768/ws
```

Esto permite reemplazar el RTP de IBM por un pipeline pipecat (LLM-driven, streaming bidireccional). El resto del flujo SIP/NLP es idéntico.

## Red y puertos

El cluster se monta sobre la red privada del datacenter (`172.16.220.0/24`) con los servicios IA en otra subred (`10.0.0.0/24`):

| Recurso | Dirección |
|---|---|
| Nodo VGW (host) | `172.16.220.51` (IP interna) / `200.62.8.140` (IP NAT pública — **NO usar**) |
| Nodo gen/dev/pipecat (host alt) | `128.24.57.99` |
| NVIDIA TTS | `172.16.220.46:3000`, `172.16.220.46:3001` |
| NVIDIA STT | `172.16.220.46:3002`, `172.16.220.46:3003` |
| Azure TTS adapter | `10.0.0.11:8001`, `10.0.0.11:8002` |
| GPU exporter | `10.0.0.5:8740` |
| Node exporter | `10.0.0.5:9100` |
| Reporting endpoint | `vgw-reporting.services.smartia-ai.com` |
| NLP adapter | `generic-nlp-adapter.services.smartia-ai.com` |

> Detalle del incidente NAT (commit `fd64633`, 2026-04-30) en [operations.md](operations.md#incidente-rtp-truncado-por-nat-2026-04-30).
