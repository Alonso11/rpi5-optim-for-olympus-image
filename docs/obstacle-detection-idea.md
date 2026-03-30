# Plan: Detección de Obstáculos con Visión — Rover Olympus

## Objetivo

Integrar la cámara CSI de la RPi5 con la Máquina de Estados Maestra (MSM) del
Arduino para dar al rover capacidad de evasión autónoma de obstáculos usando
visión por computadora.

El controlador soporta dos modos de operación seleccionables mediante un flag
(`--mode`). En ambos modos el pipeline hacia el Arduino es idéntico — solo
cambia la fuente de los comandos MSM.

---

## Modos de operación

```
┌──────────────────────────────────────────────────────────┐
│  olympus_controller.py --mode vision                     │
│                                                          │
│  Cámara CSI → cv2.dnn (YOLOv8n) → Decisión automática   │
│                              ↓                           │
│                   EXP:l:r / AVD:L / AVD:R / RET          │
│                              ↓                           │
│              rover_bridge.send_command()                 │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│  olympus_controller.py --mode manual                     │
│                                                          │
│  Operador (stdin) → escribe el mismo comando MSM         │
│                              ↓                           │
│                   EXP:l:r / AVD:L / AVD:R / RET          │
│                              ↓                           │
│              rover_bridge.send_command()                 │
└──────────────────────────────────────────────────────────┘
```

El operador en modo manual actúa como el modelo — produce exactamente los mismos
comandos MSM que produciría YOLOv8n. Esto permite:
- **Depurar** el comportamiento del rover sin depender del modelo
- **Validar** que el pipeline MSM funciona antes de activar la visión
- **Teleoperación** de emergencia si el modelo falla

### Comandos disponibles en modo manual

| Lo que escribe el operador | Comando MSM enviado | Efecto |
|---|---|---|
| `exp <l> <r>` | `EXP:<l>:<r>` | Explorar con velocidades |
| `avl` | `AVD:L` | Girar izquierda (evadir) |
| `avr` | `AVD:R` | Girar derecha (evadir) |
| `ret` | `RET` | Retroceder |
| `stb` | `STB` | Standby (parar) |
| `ping` | `PING` | Keepalive manual |
| `rst` | `RST` | Reset MSM |
| `q` | — | Salir del controlador |

---

## Diseño interno — patrón Strategy

Ambos modos comparten el mismo loop principal. La fuente de comandos es
intercambiable mediante una interfaz común:

```python
class CommandSource:
    def next_command(self) -> str | None:
        """Devuelve el siguiente comando MSM, o None si no hay nada."""
        ...

class VisionSource(CommandSource):
    """Lee frames de la cámara y decide via cv2.dnn + YOLOv8n."""

class ManualSource(CommandSource):
    """Lee comandos escritos por el operador en stdin."""
```

Loop principal (independiente del modo):

```python
source = VisionSource(...) if args.mode == "vision" else ManualSource()

while True:
    cmd = source.next_command()
    if cmd:
        response = rover.send_command(cmd)
        log(cmd, response)

    # Keepalive: si han pasado >1s sin enviar nada → PING
    if time_since_last_cmd() > 1.0:
        rover.send_command("PING")
```

---

## Arquitectura de capas de protección

```
┌─────────────────────────────────────────────────────────────────┐
│  Nivel 1 — Cámara CSI + cv2.dnn (HLC / RPi5)                   │
│  YOLOv8n ONNX → detecta obstáculos en ~8–12 FPS                 │
│  Decide dirección de evasión → AVD:L / AVD:R / RET              │
├─────────────────────────────────────────────────────────────────┤
│  Nivel 2 — HC-SR04 en Arduino (LLC / hardware)                  │
│  Distancia < 200 mm → MSM transiciona a FAULT de forma inmediata│
│  Sin intervención de la RPi5 — capa de último recurso           │
├─────────────────────────────────────────────────────────────────┤
│  Nivel 3 — Stall detection (LLC / hardware)                     │
│  Encoder no avanza con motor activo → FAULT + stall_mask        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Sensores y su rol

| Sensor | Ubicación | Qué aporta | Quién lo lee |
|--------|-----------|-----------|--------------|
| Cámara CSI | RPi5 (MIPI CSI-2) | Detección visual de obstáculos, dirección evasión | HLC (Python) |
| HC-SR04 | Arduino D38/D39 | Parada de emergencia < 200 mm | LLC (firmware) |
| Encoders × 6 | Arduino INT0–INT5 | Stall detection por motor | LLC (firmware) |
| TF-Luna (futuro) | Arduino D16/D17 | Distancia precisa 0.2–8 m @ 100 Hz | LLC → HLC via TLM |

> **Nota:** El HC-SR04 está físicamente en el Arduino, NO en los GPIO de la RPi5.
> El rover_bridge tiene métodos para un HC-SR04 secundario en RPi5 pero no está
> instalado en el hardware actual.

---

## Stack de visión elegido: cv2.dnn + YOLOv8n ONNX

Se eligió `cv2.dnn` (incluido en `python3-opencv`) sobre `onnxruntime` porque:
- `python3-opencv` ya está en la imagen Yocto y compila correctamente
- `meta-onnxruntime` no está clonado en el repo — requeriría trabajo adicional
- `cv2.dnn` soporta modelos `.onnx` nativamente con OpenCV >= 4.5

### Rendimiento estimado en RPi5 @ 1.5 GHz

| Resolución | FPS aprox (cv2.dnn CPU) |
|---|---|
| 640×640 | ~8–12 FPS |
| 320×320 | ~20–25 FPS |

Para navegación de rover a velocidades bajas (EXP:40:40), 8–10 FPS es suficiente.

---

## Flujo de integración cámara → MSM

```
[Cámara CSI]
     │ frame 640×480
     ▼
[cv2.dnn — YOLOv8n]
     │ lista de detecciones (clase, confianza, bbox)
     ▼
[Lógica de decisión]
     │
     ├── sin obstáculos relevantes ──► EXP:left:right  (seguir explorando)
     │
     ├── obstáculo a la izquierda  ──► AVD:R           (girar derecha)
     │
     ├── obstáculo a la derecha    ──► AVD:L           (girar izquierda)
     │
     └── obstáculo central / cerca ──► RET             (retroceder)
                                        └─► luego AVD:L o AVD:R
     ▼
[rover_bridge.send_command(cmd)]
     │ USART3 serial
     ▼
[Arduino MSM]
     │
     ▼
[6 Motores]
```

---

## Lógica de decisión (criterio de bounding box)

El frame es de 640 px de ancho. Dividimos en tres zonas:

```
|← 0–213 px →|← 214–426 px →|← 427–640 px →|
   Zona IZQ      Zona CENTRO     Zona DER
   → AVD:R        → RET          → AVD:L
```

Condiciones de activación:
- Confianza del bbox > 0.5
- Área del bbox > 5 % del frame (filtrar detecciones pequeñas / lejanas)
- Si múltiples detecciones: priorizar la de mayor área (obstáculo más cercano)

---

## Watchdog — keepalive obligatorio

El Arduino dispara `ERR:WDOG → FAULT` si no recibe ningún comando en ~2 s
(100 ciclos × 20 ms). El loop del HLC **debe** enviar `PING` periódicamente
aunque la cámara no detecte nada.

Frecuencia mínima recomendada: cada 1 s (o aprovechar el propio `EXP:l:r`
como keepalive implícito).

---

## Pasos de implementación (roadmap)

### Paso 1 — Limpiar el build *(✅ completado)*
- [x] Quitar `onnxruntime` de `IMAGE_INSTALL` en `olympus-image.bb`
- [x] Quitar `meta-tensorflow-lite` y `meta-onnxruntime` de `bblayers.conf`

### Paso 2 — Exportar el modelo *(✅ completado)*
- [x] Exportado con `yolo export model=yolov8n.pt format=onnx imgsz=640 opset=12`
- [x] `cv2.dnn.readNetFromONNX` carga correctamente en RPi5

### Paso 3 — Empaquetar el modelo en Yocto *(✅ completado)*
- [x] `yolov8n.onnx` en `SRC_URI` de `python3-rover-bridge` (receta v1.3)
- [x] Instalado en `/usr/share/olympus/models/yolov8n.onnx`

### Paso 4 — Escribir `olympus_controller.py` *(✅ completado — v1.7)*
- [x] Flag `--mode vision|manual` via argparse
- [x] Clase `ManualSource`: parsea stdin → comandos MSM
- [x] Clase `VisionSource`: cámara + cv2.dnn + decisión por zonas del frame
- [x] Loop principal unificado con keepalive PING cada 1 s
- [x] Fallback seguro: si cámara falla en modo vision → `STB` + aviso
- [x] Instalado en `/usr/bin/` via la receta
- [x] Parámetros configurables vía YAML (`/etc/olympus/olympus_controller.yaml`)

### Paso 5 — Calibrar en campo *(pendiente — requiere hardware)*
- [ ] Ajustar umbrales de confianza y área por bbox en `/etc/olympus/olympus_controller.yaml`
- [ ] Ajustar velocidades de EXP/AVD/RET según terreno
- [ ] Verificar que el HC-SR04 del Arduino sigue siendo la red de seguridad final

---

## Alineación con SyRS Olympus (§7.3.8)

| Estado SyRS | Estado olympus_controller | Comando MSM |
|---|---|---|
| Standby | Inicio / error cámara | `STB` |
| Exploración Activa / Desplazarse | Camino libre | `EXP:l:r` |
| Exploración Activa / EvitarObstaculo | Obstáculo detectado | `AVD:L` / `AVD:R` |
| HomingRetreat | Obstáculo central | `RET` |
| SafeMode | HC-SR04 < 200 mm (Arduino auto) | `ACK:FLT` (recibido) |

---

## Historial de decisiones

| Fecha | Decisión | Motivo |
|---|---|---|
| 2026-03-24 | cv2.dnn en lugar de onnxruntime | meta-onnxruntime no disponible; cv2.dnn cubre el caso de uso |
| 2026-03-24 | HC-SR04 en Arduino, no en RPi5 GPIO | Hardware físico conectado a D38/D39; capa de emergencia más fiable en LLC |
| 2026-03-24 | YOLOv8n como modelo base | Balance tamaño/precisión/velocidad para RPi5 CPU |
