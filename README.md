# vgw-deploy

Manifiestos Kubernetes y herramientas auxiliares para desplegar **IBM Voice Gateway (VGW) multitenant** sobre el cluster `smartia-vgw`. El gateway recibe llamadas SIP, las puentea contra **NVIDIA Riva** (TTS/STT) y un **NLP adapter** (Dialogflow), y emite eventos CDR/conversación/transcripción al servicio de reporting.

## Estructura del repo

```
vgw-deploy/
├── multitenant/
│   ├── dev/             # entorno dev   (SIP 30200, métricas 9080)
│   ├── cl/              # producción Chile (SIP 30201, métricas 9081)
│   ├── int/             # internacional (SIP 30202, métricas 9082)
│   ├── gen/             # generic / azure-tts (SIP 30203, métricas 9083)
│   ├── pipecat/         # variante con media relay externo pipecat (SIP 30191)
│   └── bk/              # backups históricos
├── monitoring/
│   ├── prometheus-vgw-monitoring.yaml   # scrape config de los SO
│   └── README.md                        # cómo cargarlo como secret
├── petitionsCMD/
│   └── cmd.sh           # one-liners awk para auditoría de trace-mr.log
├── latency_avg.py       # latencia promedio multi-endpoint (TTS/STT/NLP)
├── one_latency_avg.py   # variante con endpoints alternativos
└── docs/                # documentación detallada (este directorio)
```

Cada entorno expone dos pods: `vgw-mr` (media relay) y `vgw-so` (SIP orchestrator). Los puertos se separan por env para que coexistan con `hostNetwork: true` en el mismo nodo.

## Documentación

| Tema | Ruta | Cuándo consultarlo |
|---|---|---|
| Arquitectura general (SIP, MRCP, RTP, multitenant routing) | [docs/architecture.md](docs/architecture.md) | Para entender cómo encajan vgw-so y vgw-mr y cómo se enrutan las llamadas |
| **Referencia del Deployment K8s** (todos los `env` de `deploy_*.json`) | [docs/deploy-reference.md](docs/deploy-reference.md) | Cuando hay que tocar un parámetro del deploy.json |
| **Referencia del Tenant** (todos los campos de `tenantConfiguration_*.json`) | [docs/tenant-reference.md](docs/tenant-reference.md) | Para alta de tenant nuevo o cambio de proveedor |
| Matriz de entornos (puertos, IPs, voces, NLP) | [docs/environments.md](docs/environments.md) | Para saber qué puerto/IP corresponde a cada env |
| Monitoreo Prometheus | [docs/monitoring.md](docs/monitoring.md) | Para añadir un scrape o revisar exporters |
| Operación y troubleshooting | [docs/operations.md](docs/operations.md) | Despliegue, redeploy, incidente NAT/RTP |

## Quickstart

```bash
# 1. Aplicar tenantConfiguration como ConfigMap
kubectl create configmap mrcp-config \
  --from-file=tenantConfiguration.json=multitenant/cl/tenantConfiguration.json \
  -n <namespace> --dry-run=client -o yaml | kubectl apply -f -

# 2. Aplicar el deployment
kubectl apply -f multitenant/cl/deploy.json -n <namespace>

# 3. Cargar scrape config de Prometheus (una sola vez por cluster)
#    -> ver monitoring/README.md
```

## Variantes y detalles importantes

- **`hostNetwork: true`** en todos los deployments — los puertos SIP/RTP usan directamente la IP del nodo. Por eso cada env tiene puertos distintos (ver [environments.md](docs/environments.md)).
- **`SDP_ADDRESS` y `SIP_HOST`** deben apuntar a la **IP interna del datacenter** (`172.16.220.51` en `cl`/`int`). Usar la IP NAT pública causa truncación de RTP por firewall upstream — ver [operations.md](docs/operations.md#incidente-rtp-truncado-por-nat-2026-04-30).
- **`providerType: watson`** en los tenants es solo el *protocolo* (las APIs son compatibles con Watson Speech). El backend real es NVIDIA Riva o Azure TTS.
- **Liveness probe-trampa**: ambos containers fallan automáticamente los **domingos a las 07:00 UTC** (`cutoffdate=$(date +%u%H); test $cutoffdate -eq 307`) para forzar un restart semanal. No es un bug, es el modo recomendado por IBM.

## Versionado y branches

- `main` — base.
- `vgw-ufinet-priv` — rama activa; aplica el fix de RTP/NAT y credenciales Ufinet (2026-04-29 / 2026-04-30).
