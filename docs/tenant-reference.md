# Referencia del Tenant

Este documento explica **cada campo** de `tenantConfiguration_*.json`, montado en el pod de `vgw-so` vía ConfigMap y leído por la variable `MULTI_TENANT_CONFIG_FILE`.

## Estructura general

```json
{
  "tenants": [
    {
      "tenantURI": "...",
      "description": "...",
      "URIs": [ { "name": "...", "uri": "..." } ],
      "conversation": { ... },
      "stt":          { ... },
      "tts":          { ... },
      "reporting":    { ... }
    }
  ]
}
```

`tenants` es un array. **Cada llamada SIP entrante se matchea contra UN tenant** según la SIP URI del INVITE (ver [architecture.md](architecture.md#routing-multitenant)).

---

## Campos top-level del tenant

### `tenantURI`

Etiqueta humana del tenant (no se usa para matching). Aparece en logs y eventos de reporting.

> Convención del repo: `"<Marca> <ID externo> <País>"`, ej. `"SmartIA 20056 Chile"`, `"SmartIA 20593 Ecuador"`. El ID corresponde al ID de campaña del PBX.

### `description`

Texto libre. Por convención **igual que `tenantURI`**.

### `URIs[]`

```json
"URIs": [
  { "name": "smartia_001_chile", "uri": "smartia001chl" },
  { "name": "integradial_panama", "uri": "50722209165" }
]
```

| Campo | Significado |
|---|---|
| `name` | Etiqueta humana del alias. Aparece en logs. |
| `uri` | Valor literal que VGW matchea contra el `user` de la SIP Request-URI / `To:` URI. |

**Cómo funciona el matching.** Si llega:

```
INVITE sip:smartia001chl@172.16.220.51:30201 SIP/2.0
```

VGW saca el `user` (`smartia001chl`) y busca un tenant que tenga ese valor en `URIs[].uri`. Si no encuentra → `404 Not Found`.

> Un tenant puede tener **varios alias** — útil cuando el mismo bot se publica con un nombre interno y un DID público (caso `Panama` y `El Salvador` en `int/`).

### `reporting`

```json
"reporting": {
  "url": "http://vgw-reporting.services.smartia-ai.com/vgw/report",
  "cdrEventInd": "cdr",
  "convEventInd": "conversation",
  "transcriptionEventInd": "transcription"
}
```

Sobreescribe a nivel **tenant** los `REPORTING_*` del deploy. En este repo todos los tenants usan los mismos valores que el deploy. Está bueno duplicarlo para que el tenant sea autocontenido (si en el futuro un tenant reporta a otro endpoint, basta con cambiar acá).

| Campo | Equivalente en deploy.json |
|---|---|
| `url` | `REPORTING_URL` |
| `cdrEventInd` | `REPORTING_CDR_EVENT_INDEX` |
| `convEventInd` | `REPORTING_CONVERSATION_EVENT_INDEX` |
| `transcriptionEventInd` | `REPORTING_TRANSCRIPTION_EVENT_INDEX` |

---

## Bloque `conversation` (NLP / Dialogflow)

```json
"conversation": {
  "url": "http://generic-nlp-adapter.services.smartia-ai.com/dialogflow",
  "workspaceID": "xxxx",
  "password": "xxxx",
  "username": "xxxx"
}
```

| Campo | Significado |
|---|---|
| `url` | Endpoint del NLP adapter. VGW hace POST con la transcripción y el adapter resuelve contra Dialogflow / IBM Watson Assistant / lo que sea. |
| `workspaceID` | ID del workspace/agente. Algunos adapters lo ignoran y usan el path. |
| `username` / `password` | Credenciales Basic Auth. **Hoy quedan como `xxxx` placeholder** porque el adapter usa auth interna por header. Si el adapter cambia a Basic Auth, hay que poner los reales. |

### Variantes de URL en el repo

| URL | Uso |
|---|---|
| `generic-nlp-adapter.services.smartia-ai.com/dialogflow` | NLP adapter público (`dev`, `int`, `gen`, `pipecat`). |
| `generic-nlp-adapter.services3.smartia-ai.com/dialogflow` | Variante usada en `cl/` (Ufinet, ambiente segregado). |
| `genbot-nlp-adapter.services.smartia-ai.com/dialogflow` | Bot generativo (`gen` — tenant `SmartIA Gen 5006`). |
| `mrcp-transfer-nlp-adapter.services.smartia-ai.com/user/10103/dialogflow` | Adapter especial con transfer MRCP (`gen` — `SmartIA TTS Test`). Usa `workspaceID` real (`ivr-generico-qcpu`). |

---

## Bloque `stt` (Speech-to-Text)

```json
"stt": {
  "providerSelectionPolicy": "sequential",
  "providers": [
    {
      "name": "nvidia-stt",
      "providerType": "watson",
      "credentials": {
        "url": "http://172.16.220.46:3002/",
        "username": "",
        "password": ""
      }
    }
  ],
  "trackLatency": true
}
```

### `providerSelectionPolicy`

| Valor | Comportamiento |
|---|---|
| `sequential` | Intenta el primer provider; si falla, va al siguiente. **Único valor usado en este repo.** |
| `roundrobin` | Distribuye llamadas. No usado acá. |

### `providers[]`

| Campo | Significado |
|---|---|
| `name` | Etiqueta libre — aparece en logs y métricas Prometheus (`stt_provider`). Convención: `nvidia-stt` o `azure-stt`. |
| `providerType` | **Siempre `watson`**. Es el *protocolo* que habla VGW. NVIDIA Riva expone una API compatible con Watson Speech, por eso aplica. No cambiar salvo si IBM agrega soporte nativo de NVIDIA/Azure. |
| `credentials.url` | Endpoint del STT. Ver [tabla de URLs](#urls-de-stttts-en-uso). |
| `credentials.username` / `password` | Vacíos en NVIDIA Riva (no requiere auth en la red interna). |

### `trackLatency`

`true` → vgw-mr mide la latencia STT y la adjunta a los eventos de transcripción. Habilita la métrica Prometheus `vgw_stt_latency_*`.

---

## Bloque `tts` (Text-to-Speech)

```json
"tts": {
  "providerSelectionPolicy": "sequential",
  "providers": [
    {
      "name": "nvidia-tts",
      "providerType": "watson",
      "credentials": {
        "url": "http://172.16.220.46:3000/",
        "username": "",
        "password": ""
      },
      "config": {
        "voice": "tts_spanish.56"
      }
    }
  ]
}
```

Estructura igual que `stt` + un campo extra:

### `config.voice`

ID de voz dentro del provider. Valores en uso:

| Voice ID | Provider | Uso |
|---|---|---|
| `tts_spanish.56` | NVIDIA Riva | `cl/` (Chile) |
| `tts_spanish.111` | NVIDIA Riva | `int/` (todos los países: EC, CR, CO, GT, PE, MX, PA, SV) y `pipecat/`/`dev/` |
| sin `voice` | Azure TTS adapter | `gen/` — el adapter resuelve la voz internamente |

Cambiar voz: editar este campo y **redesplegar el ConfigMap** (no hace falta tocar el deploy).

---

## URLs de STT/TTS en uso

| Tenant / env | STT | TTS |
|---|---|---|
| `cl/` (todos) | `http://172.16.220.46:3002/` o `:3003/` | `http://172.16.220.46:3000/` o `:3001/` |
| `int/` (todos) | `http://172.16.220.46:3003/` | `http://172.16.220.46:3001/` |
| `dev/`, `pipecat/` | `http://stt-multitenant-ts-2.nvidiaservices.smartia-ai.com` | `http://tts-multitenant-ts-2.nvidiaservices.smartia-ai.com` |
| `gen/` | `http://stt-multitenant-ts.nvidiaservices2.smartia-ai.com` | `http://10.0.0.11:8001` o `:8002` (Azure adapter) |

> **Nota.** En `cl/` los puertos `3000`/`3002` y `3001`/`3003` se reparten entre tenants para balancear carga manualmente. No hay LB delante.

---

## Plantilla para tenant nuevo

```json
{
  "tenantURI": "Cliente Nuevo - 99999 Pais",
  "description": "Cliente Nuevo - 99999 Pais",
  "URIs": [
    { "name": "cliente_nuevo", "uri": "clientenuevo99999" }
  ],
  "conversation": {
    "url": "http://generic-nlp-adapter.services.smartia-ai.com/dialogflow",
    "workspaceID": "xxxx",
    "password": "xxxx",
    "username": "xxxx"
  },
  "stt": {
    "providerSelectionPolicy": "sequential",
    "providers": [
      {
        "name": "nvidia-stt",
        "providerType": "watson",
        "credentials": { "url": "http://172.16.220.46:3003/", "username": "", "password": "" }
      }
    ],
    "trackLatency": true
  },
  "tts": {
    "providerSelectionPolicy": "sequential",
    "providers": [
      {
        "name": "nvidia-tts",
        "providerType": "watson",
        "credentials": { "url": "http://172.16.220.46:3001/", "username": "", "password": "" },
        "config": { "voice": "tts_spanish.111" }
      }
    ]
  },
  "reporting": {
    "url": "http://vgw-reporting.services.smartia-ai.com/vgw/report",
    "cdrEventInd": "cdr",
    "convEventInd": "conversation",
    "transcriptionEventInd": "transcription"
  }
}
```

### Pasos para activar

1. Pegar el bloque dentro del `tenants[]` del archivo del env correcto.
2. Validar JSON: `python -m json.tool multitenant/<env>/tenantConfiguration_<env>.json > /dev/null`.
3. Recrear el ConfigMap:
   ```bash
   kubectl -n <ns> create configmap mrcp-config \
     --from-file=tenantConfiguration_<env>.json=multitenant/<env>/tenantConfiguration_<env>.json \
     --dry-run=client -o yaml | kubectl apply -f -
   ```
4. Reiniciar el pod (vgw-so **no** recarga el archivo en caliente):
   ```bash
   kubectl -n <ns> rollout restart deploy/vgw-<env>-multitenant-deployment
   ```
5. Configurar el SBC para enviar el INVITE con `sip:<URIs[0].uri>@<SIP_HOST>:<SIP_PORT>`.

---

## Variables de entorno relacionadas (referencia cruzada)

Algunas tunings de runtime que el README de `multitenant/dev/` y `multitenant/pipecat/` documenta a nivel **tenant** se aplican vía `env` en el deploy.json (no en el tenantConfig). Recordatorio:

| Variable | Dónde va | Para qué |
|---|---|---|
| `SESSION_INACTIVITY_TIMEOUT` | `vgw-so.env` | Timeout de inactividad de sesión (segundos). |
| `FINAL_UTTERANCE_TIMEOUT` | `vgw-so.env` | Tiempo (ms) para esperar el final de un turno. |
| `POST_RESPONSE_TIMEOUT` | `vgw-so.env` | Tiempo (ms) tras la respuesta del NLP. |
| `WATSON_STT_CONNECTION_TIMEOUT` | `vgw-so.env` | Timeout conexión STT (s). |
| `WATSON_TTS_CONNECTION_TIMEOUT` | `vgw-so.env` | Timeout conexión TTS (s). |
| `WATSON_CONVERSATION_CONNECTION_TIMEOUT` | `vgw-so.env` | Timeout conexión NLP (s). |
| `DISABLE_STT_DURING_PLAYBACK` | `vgw-so.env` y `vgw-mr.env` | `false` para habilitar barge-in (interrupción del bot). |

> **No están actualmente** en los `deploy_*.json` salvo `DISABLE_STT_DURING_PLAYBACK`. Si un tenant requiere timeouts diferentes de los de IBM, hay que agregarlos al deploy del env (y eso aplica a **todos** los tenants de ese env — el VGW no soporta timeouts por-tenant).
