# Operación y troubleshooting

## Despliegue desde cero (un env)

```bash
ENV=cl
NS=vgw                      # ajustar al namespace real
NODE=smartia-vgw            # nodo donde corre el VGW

cd multitenant/$ENV

# 1. Validar JSONs
python -m json.tool deploy.json > /dev/null
python -m json.tool tenantConfiguration.json > /dev/null

# 2. Crear/actualizar el ConfigMap del tenant
kubectl -n $NS create configmap mrcp-config \
  --from-file=tenantConfiguration.json=tenantConfiguration.json \
  --dry-run=client -o yaml | kubectl apply -f -

# 3. Asegurar el imagePullSecret
kubectl -n $NS get secret admin.registrykey || \
  kubectl -n $NS create secret docker-registry admin.registrykey \
    --docker-server=<registry> --docker-username=<u> --docker-password=<p>

# 4. Aplicar el deployment
kubectl -n $NS apply -f deploy.json

# 5. Esperar y validar
kubectl -n $NS rollout status deploy/vgw-multitenant-deployment
kubectl -n $NS logs -l service=vgw-multitenant -c vgw-multitenant-vgw-so --tail=100
```

> Para envs distintos a `cl`, los nombres son `vgw-<env>-multitenant-deployment` y los archivos `deploy_<env>.json` / `tenantConfiguration_<env>.json`.

## Cambiar un tenant (alta/baja/edición de credenciales o voz)

1. Editar `multitenant/<env>/tenantConfiguration_<env>.json`.
2. Recrear el ConfigMap:
   ```bash
   kubectl -n $NS create configmap mrcp-config \
     --from-file=tenantConfiguration_<env>.json=multitenant/<env>/tenantConfiguration_<env>.json \
     --dry-run=client -o yaml | kubectl apply -f -
   ```
3. **Reiniciar el pod** — vgw-so lee el archivo solo al startup:
   ```bash
   kubectl -n $NS rollout restart deploy/vgw-<env>-multitenant-deployment
   ```
4. Verificar que el nuevo URI se matchea (mandar un INVITE de prueba con `sipp` o desde el SBC en sandbox).

> **No se puede recargar tenants en caliente.** Si esto se vuelve un problema, evaluar `inotify` + script externo, o pasar a un controller que watch el ConfigMap.

## Cambiar puertos / IPs / `RTP_UDP_PORT_RANGE`

1. Editar el bloque `env` correspondiente en `deploy_<env>.json`.
2. **Asegurarse de que el nuevo rango no colisiona con otro env del mismo nodo** — los rangos UDP RTP son grandes:

   | Env | RTP UDP | Otros host ports |
   |---|---|---|
   | dev | 7000-8000 | 5555, 6200, 30200 |
   | cl | 26001-35000 | 5556, 6201, 30201 |
   | int | 15000-25000 | 5557, 6202, 30202 |
   | gen | 35001-40000 | 5558, 6203, 30203 |
   | pipecat | (externo) | 30191 |

3. Aplicar el deploy. Como `hostNetwork: true`, el Pod **no se reagenda automáticamente** si los puertos chocan — hay que borrar el Pod manualmente.
4. Pedir al equipo de red que abra el nuevo rango en el firewall del SBC.

## Diagnóstico

### El SBC no ve respuesta SIP

```bash
# Confirmar que vgw-so escucha en el puerto del nodo
ssh $NODE "sudo ss -lnp | grep 30201"

# Logs SIP
kubectl -n $NS logs -l service=vgw-multitenant -c vgw-multitenant-vgw-so | grep -i sip

# tcpdump en el nodo
ssh $NODE "sudo tcpdump -i any -n port 30201 -c 50"
```

### El bot habla pero la llamada se corta a los ~1.5s

→ Probable truncación RTP por NAT. Ver el incidente abajo.

### El bot no responde / timeouts

```bash
# Tirar contra los STT/TTS internos
python latency_avg.py

# Probar el NLP adapter
curl -s -X POST http://generic-nlp-adapter.services.smartia-ai.com/dialogflow \
  -H 'Content-Type: application/json' -d '{"text":"hola"}'
```

Si las latencias del NLP suben mucho, el `WATSON_CONVERSATION_CONNECTION_TIMEOUT` puede dispararse antes — subirlo a 15s+ en el deploy (ver [tenant-reference.md](tenant-reference.md#variables-de-entorno-relacionadas-referencia-cruzada)).

### Llamadas se cortan los domingos a las 07:00 UTC

**Esperado**. Es el restart programado del `livenessProbe`. El SBC debe reintentar y la nueva llamada se atiende en ~30s.

---

## Incidente RTP truncado por NAT (2026-04-30)

**Síntoma.** En el entorno `cl` (Ufinet, prod Chile), el saludo del bot se cortaba ~1.5 segundos después de empezar y el llamante colgaba sin alcanzar a oír la pregunta.

**Causa raíz.** `SDP_ADDRESS` y `SIP_HOST` apuntaban a la **IP NAT pública** `200.62.8.140`. El firewall upstream entre el SBC de Ufinet y el cluster aceptaba los primeros paquetes UDP del flujo RTP, pero su tabla de estado expiraba el flujo después de ~1.5s de tráfico saliente y empezaba a *droppear* el resto — no era pérdida aleatoria, era corte completo.

**Fix.** Cambiar a la **IP interna del datacenter** `172.16.220.51`. Como el SBC y el VGW están en la misma red privada, el RTP ya no atraviesa el firewall NAT.

**Commit.** [`fd64633`](../) — `fix(vgw): use internal IP to avoid RTP truncation through NAT`. Aplicado a `multitenant/cl/deploy.json` y `multitenant/int/deploy_int.json`.

**Verificación post-fix.**

```bash
# Confirmar SDP_ADDRESS en el deploy actual
kubectl -n $NS get deploy vgw-multitenant-deployment -o yaml \
  | grep -A1 SDP_ADDRESS
# debe decir 172.16.220.51

# Verificar que el SDP en el 200 OK lleva la IP interna
ssh $NODE "sudo tcpdump -i any -n -A port 30201" | grep "c=IN IP4"
```

**Reglas mnemónicas que dejó este incidente.**

1. Para `cl`/`int` (red privada Ufinet) → siempre IP interna.
2. Si vuelve a aparecer truncación de audio, **lo primero** es revisar `SDP_ADDRESS` y `SIP_HOST`, no la calidad del audio ni la latencia del STT.
3. Para envs en otros nodos (`dev`, `gen`, `pipecat`) sigue siendo válido `128.24.57.99` (no atraviesan ese firewall específico).

---

## Backup y rollback

El repo no usa Helm ni Kustomize — el deploy es un JSON crudo. Para rollback:

```bash
# K8s mantiene los últimos N replicasets
kubectl -n $NS rollout history deploy/vgw-<env>-multitenant-deployment
kubectl -n $NS rollout undo deploy/vgw-<env>-multitenant-deployment --to-revision=<N>
```

Para volver a un commit anterior del repo:

```bash
git log --oneline -- multitenant/<env>/
git show <commit>:multitenant/<env>/deploy_<env>.json | kubectl -n $NS apply -f -
```

> Los backups en `multitenant/bk/` son **históricos** (Aladino, snapshot 2024-10-24). No se aplican como rollback automático.

---

## Checklist post-cambio

- [ ] JSON parsea (`python -m json.tool`)
- [ ] ConfigMap actualizado **antes** del rollout
- [ ] `kubectl rollout status` dice `successfully rolled out`
- [ ] Logs de `vgw-so` muestran el load del `tenantConfiguration_<env>.json` sin errores
- [ ] Llamada de prueba SIP exitosa contra cada `URIs[].uri` afectado
- [ ] Métricas en Prometheus muestran target UP (`/targets` filter `vgw-`)
- [ ] Si tocaste `SDP_ADDRESS`/`SIP_HOST`/`RTP_UDP_PORT_RANGE` → coordinar con red para reglas de firewall
