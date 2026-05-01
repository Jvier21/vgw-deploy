# Referencia del Deployment

Este documento explica **cada campo** de los `deploy_*.json` (`multitenant/<env>/deploy_*.json`). Usar como guía cuando se modifique un manifest existente o se cree uno nuevo.

> Para los valores específicos por entorno (puertos, IPs, voces) ver [environments.md](environments.md).

## Bloque `metadata`

```json
{ "kind": "Deployment", "apiVersion": "apps/v1",
  "metadata": { "name": "vgw-<env>-multitenant-deployment" } }
```

| Campo | Por qué importa |
|---|---|
| `name` | Convención: `vgw-<env>-multitenant-deployment`. Tiene que ser único por namespace. Cambiar el nombre **rompe** el rolling update si ya está desplegado: `kubectl delete deploy <viejo>` antes. |

## Bloque `spec`

| Campo | Valor típico | Comentario |
|---|---|---|
| `replicas` | `1` | **Siempre 1**. VGW no es horizontalmente escalable en este modo (estado SIP en memoria). Para más capacidad: nuevo env con sus propios puertos. |
| `selector.matchLabels.service` | `vgw-multitenant` | Selector compartido por todos los envs — está OK porque el selector se acota al deployment, no se cruzan pods. |

## `template.metadata.labels`

```json
{ "service": "vgw-multitenant",
  "client": "demo",
  "tts_provider": "watson",
  "nlp_provider": "watson",
  "stt_provider": "watson" }
```

Labels usados por Prometheus / Grafana para filtrar métricas. `*_provider: watson` es el **protocolo** que habla VGW (Watson Speech compatible). El backend real (NVIDIA Riva, Azure TTS) se define en `tenantConfiguration.json`.

## `template.spec`

### `volumes`

```json
[ { "name": "recordings", "emptyDir": {} },
  { "name": "cfgmap", "configMap": { "name": "mrcp-config" } } ]
```

| Volumen | Rol |
|---|---|
| `recordings` | Buffer efímero de grabaciones de llamada. Solo se llena si `ENABLE_RECORDING=true`. Como es `emptyDir`, **se pierde al reiniciar el pod**. |
| `cfgmap` | Monta el `tenantConfiguration_*.json` desde un ConfigMap llamado `mrcp-config`. Hay que crearlo antes de aplicar el deploy. |

### `hostNetwork: true`

Crítico. Hace que ambos containers usen la red del nodo directamente (no la red de pods K8s):
- Los `hostPort` del manifest son los puertos reales del nodo.
- No se puede correr **dos envs en el mismo nodo con los mismos puertos**.
- El SBC apunta a la IP del nodo, no a una IP de cluster.

### `imagePullSecrets`

```json
[ { "name": "admin.registrykey" } ]
```

Secret K8s con credenciales para el registry IBM (donde viven `ibmcom/voice-gateway-mr` y `ibmcom/voice-gateway-so`). Si el pod se queda en `ImagePullBackOff`, revisar este secret.

---

## Container `vgw-mr` (media relay)

Solo está en `dev`, `cl`, `int`, `gen`. **No** está en `pipecat`.

### Imagen y nombre

| Campo | Valor |
|---|---|
| `name` | `vgw-<env>-multitenant-vgw-mr` |
| `image` | `ibmcom/voice-gateway-mr:latest` |
| `imagePullPolicy` | `Always` — fuerza pull en cada restart (versión `latest`). |

### `livenessProbe` (truco de restart semanal)

```json
"command": ["/bin/sh", "-ec",
  "cutoffdate=$(date +%u%H); testresult=$(test $cutoffdate -eq 307 && echo 1 || echo 0); exit $testresult"]
```

| Campo | Valor | Comentario |
|---|---|---|
| `initialDelaySeconds` | `3600` | Espera 1 hora antes de empezar a evaluar. Da tiempo a la inicialización. |
| `periodSeconds` | `60` | Evalúa cada minuto. |
| `failureThreshold` | `1` | Una sola falla → restart. |

**Lógica del comando**: `date +%u%H` = `<día_semana><hora>` (ej. domingo 07h = `307`). Si coincide con `307`, el `test` pasa, `testresult=1`, `exit 1` → liveness falla → K8s reinicia el pod. Es decir: **restart programado todos los domingos a las 07:00 UTC**. Recomendado por IBM para liberar memoria/sesiones acumuladas.

### `ports`

| `containerPort` / `hostPort` | Protocolo | Para qué |
|---|---|---|
| `6200`–`6203` | TCP | WebSocket MRCP local (vgw-so → vgw-mr). El número exacto depende del env. |
| `5555`–`5558` | TCP/UDP | SIP signaling interno entre vgw-so y vgw-mr (no expuesto al SBC). |

### `lifecycle.preStop`

```json
"command": ["/opt/quiesce.sh"]
```

Ejecutado antes de matar el container. Da `terminationGracePeriodSeconds` (30s) para drenar llamadas activas. Crítico para no cortar audio en producción.

### Variables de entorno (`env`)

| Variable | Significado | Notas |
|---|---|---|
| `SDP_ADDRESS` | IP que VGW anuncia en el SDP del SIP 200 OK | **Debe ser alcanzable desde el SBC**. En `cl`/`int` usar la IP interna `172.16.220.51`. Ver incidente NAT en [operations.md](operations.md). |
| `ENABLE_RECORDING` | `false` | Activarlo solo en debug — los archivos se pierden al restart porque el volumen es `emptyDir`. |
| `RTP_UDP_PORT_RANGE` | `7000-8000` (dev), `26001-35000` (cl), `15000-25000` (int), `35001-40000` (gen) | Rango de puertos UDP que vgw-mr usa para terminar RTP. **Los rangos no deben solaparse entre envs del mismo nodo**. El firewall debe abrir todo el rango. |
| `CLUSTER_WORKERS` | `0` | `0` = un solo proceso Node.js. No tocar salvo escalado vertical. |
| `MEDIA_RELAY_LOG_LEVEL` | `DEBUG` | En producción podría bajarse a `INFO` para reducir I/O. |
| `MEDIA_RELAY_LOG_ROTATION_FILE_COUNT` | `7` (dev/gen) o `14` (cl/int) | Cantidad de archivos de log rotados que se conservan. |
| `MEDIA_RELAY_WS_PORT` | `6200`-`6203` | Debe coincidir con el `containerPort` MRCP. vgw-so se conecta acá vía `MEDIA_RELAY_HOST=localhost:<port>`. |
| `DISABLE_STT_DURING_PLAYBACK` | `true` | El bot **no escucha** mientras está hablando. Evita auto-feedback. Quitarlo si se quiere "barge-in" (interrupción del bot). |
| `STT_TRACK_LATENCY` | `true` | Adjunta métricas de latencia de STT a los eventos de transcripción. |
| `RTCP_MAX_PACKET_LOSS_THRESHOLD` | `1` | Solo en `cl`/`int`. Tolerancia de pérdida RTCP antes de cortar. Más bajo = más sensible. |

---

## Container `vgw-so` (SIP orchestrator)

Está en **todos** los envs, incluido `pipecat`.

### Imagen

```json
{ "name": "vgw-<env>-multitenant-vgw-so",
  "image": "ibmcom/voice-gateway-so:latest",
  "imagePullPolicy": "Always" }
```

### `livenessProbe`

Idéntico al de vgw-mr — restart semanal domingo 07:00 UTC.

### `ports`

| `containerPort` / `hostPort` | Protocolo | Para qué |
|---|---|---|
| `30200`–`30203`, `30191` | TCP/UDP | Puerto SIP **expuesto al SBC**. Es el puerto al que apunta el carrier/PBX. |

### Variables de entorno (`env`) — agrupadas por función

#### Red y media

| Variable | Significado |
|---|---|
| `SIP_HOST` | IP que vgw-so anuncia en headers `Contact:` y `Via:`. Igual a `SDP_ADDRESS` del vgw-mr. |
| `MEDIA_RELAY_HOST` | URL del vgw-mr. En `cl`/`dev`/`int`/`gen`: `localhost:<MEDIA_RELAY_WS_PORT>`. En `pipecat`: URL externa con path WS (`128.24.57.99:8768/ws`). |
| `SIP_PORT`, `SIP_PORT_TCP` | Puerto SIP. UDP y TCP usan el mismo número. |
| `JMS_PORT`, `JMS_PORT_SSL` | Puertos del bus JMS interno (eventos de auditoría). Solo importan si se conecta otro componente IBM al bus. |

#### Auditoría y logs

| Variable | Valor | Comentario |
|---|---|---|
| `ENABLE_AUDIT_MESSAGES` | `true` | Genera eventos CDR a `REPORTING_URL`. |
| `ENABLE_TRANSCRIPTION_AUDIT_MESSAGES` | `true` | Igual pero para transcripciones. |
| `LOG_LEVEL` | `all` | Nivel JSON de logs. Reducir a `info` en prod si la disco se llena. |
| `LOG_MAX_FILES` | `7` o `14` | Rotación. |
| `LOG_MAX_FILE_SIZE` | `500` (MB) | Tamaño antes de rotar. |

#### Headers SIP enviados al NLP

| Variable | Efecto |
|---|---|
| `SEND_SIP_CALL_ID_TO_CONVERSATION` | Inyecta el `Call-ID` SIP como contexto al NLP. Útil para correlacionar con CDR. |
| `SEND_SIP_REQUEST_URI_TO_CONVERSATION` | Inyecta la `Request-URI`. |
| `SEND_SIP_TO_URI_TO_CONVERSATION` | Inyecta el `To:` URI. |
| `SEND_SIP_FROM_URI_TO_CONVERSATION` | Inyecta el `From:` URI (caller ID). El NLP puede usarlo como variable. |

#### Reporting

| Variable | Valor |
|---|---|
| `REPORTING_URL` | `http://vgw-reporting.services.smartia-ai.com/vgw/report` |
| `REPORTING_CDR_EVENT_INDEX` | `cdr` |
| `REPORTING_CONVERSATION_EVENT_INDEX` | `conversation` |
| `REPORTING_TRANSCRIPTION_EVENT_INDEX` | `transcription` |

Estos índices se traducen a Elasticsearch indexes en el lado de `vgw-reporting`.

#### Multitenancy

| Variable | Valor |
|---|---|
| `MULTI_TENANT_CONFIG_FILE` | `/mnt/tenantConfiguration_<env>.json` |
| `CONVERSATION_FAILED_REPLY_MESSAGE` | Texto que el bot dice cuando el NLP falla: *"Lo volveremos a llamar. Disculpe las molestias."* |

El path debe coincidir con el `volumeMounts.mountPath` (ver más abajo).

#### Métricas Prometheus

| Variable | Valor |
|---|---|
| `METRICS_SAMPLING_INTERVAL` | `1` (segundos) |
| `ENABLE_METRICS_AUTH` | `false` — métricas sin auth. OK porque escucha solo en la red interna. |
| `HTTP_HOST` | IP donde escucha el endpoint `/metrics/`. En `cl`/`int` = IP del nodo (`172.16.220.51`). En `dev`/`gen`/`pipecat` = `10.0.0.6` (otro nodo). |
| `HTTP_PORT` | `9080` (dev), `9081` (cl), `9082` (int), `9083` (gen), `9089` (pipecat). |
| `HTTPS_PORT` | `9443`-`9449`. |

> Estos puertos son los que escrapea el Prometheus configurado en `monitoring/prometheus-vgw-monitoring.yaml` — ver [monitoring.md](monitoring.md).

#### Admin API

```json
{ "ADMIN_USERNAME": "None", "ADMIN_PASSWORD": "None" }
```

Cadenas literales `"None"` → la API admin queda **deshabilitada**. Usar `kubectl exec` para inspeccionar.

### `resources`

| Env | requests | limits |
|---|---|---|
| `dev`, `pipecat` | `0.2 CPU / 0.5Gi` | `0.5 CPU / 1Gi` |
| `cl`, `int` | `1 CPU / 2Gi` | `1.5 CPU / 5Gi` |
| `gen` | sin límite (default cluster) | sin límite |

vgw-mr no declara `resources` en ninguno (deja que K8s aplique los defaults del namespace).

### `volumeMounts`

```json
[ { "name": "cfgmap",
    "mountPath": "/mnt/tenantConfiguration_<env>.json",
    "subPath": "tenantConfiguration_<env>.json" } ]
```

`subPath` es importante: el ConfigMap `mrcp-config` puede contener varios archivos; solo se monta el del env correspondiente.

> **Convención no obvia**: el `key` del ConfigMap **debe** llamarse igual que el archivo (`tenantConfiguration_dev.json`, etc.), porque el `subPath` lo busca por nombre exacto.

---

## Diferencias clave entre envs

| Punto | dev | cl (prod CL) | int | gen | pipecat |
|---|---|---|---|---|---|
| `vgw-mr` presente | sí | sí | sí | sí | **no** |
| `SDP_ADDRESS`/`SIP_HOST` | `128.24.57.99` | `172.16.220.51` | `172.16.220.51` | `128.24.57.99` | `128.24.57.99` |
| `SIP_PORT` | 30200 | 30201 | 30202 | 30203 | 30191 |
| `MEDIA_RELAY_WS_PORT` | 6200 | 6201 | 6202 | 6203 | — |
| `MEDIA_RELAY_HOST` | localhost:6200 | localhost:6201 | localhost:6202 | localhost:6203 | `128.24.57.99:8768/ws` |
| `RTP_UDP_PORT_RANGE` | 7000-8000 | 26001-35000 | 15000-25000 | 35001-40000 | (delegado a pipecat) |
| `HTTP_PORT` (métricas) | 9080 | 9081 | 9082 | 9083 | 9089 |
| `HTTPS_PORT` | 9443 | 9444 | 9445 | 9446 | 9449 |
| `LOG_MAX_FILES` | 7 | 14 | 14 | 7 | 7 |
| Limits CPU/RAM (so) | 0.5/1Gi | 1.5/5Gi | 1.5/5Gi | default | 0.5/1Gi |

> Mismo cuadro pero ampliado en [environments.md](environments.md).
