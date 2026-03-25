# Arquitectura del Sistema Olympus

## Visión General

El proyecto Olympus implementa un rover controlado por dos microcontroladores:

- **RPi5 (HLC)** — High-Level Controller. Ejecuta una imagen Linux personalizada
  construida con Yocto (rama scarthgap). Responsable de la lógica de alto nivel,
  visión por computadora, sensores y comunicación con el LLC.
- **Arduino Mega 2560 (LLC)** — Low-Level Controller. Ejecuta el firmware de
  control de motores en tiempo real. Recibe comandos ASCII por USART3.

```
┌────────────────────────────────────┐        ┌──────────────────────────────────┐
│  Raspberry Pi 5 (HLC)              │        │  Arduino Mega 2560 (LLC)         │
│  Yocto — meta-olympus              │        │  rover-low-level-controller      │
│                                    │        │                                  │
│  rover_bridge.so (Rust/PyO3) ──────┼─USART3─┼─── CommandInterface              │
│  /dev/arduino_mega                 │D14/D15 │    MSM (Standby/Explore/…/Fault) │
│                                    │        │                                  │
│  python3 (HLC logic)               │        │  6 Motores L298N (PWM)           │
│  OpenCV + cv2.dnn (YOLOv8n ONNX)  │        │  HC-SR04 D38(Trig) D39(Echo)     │
│  Cámara CSI (libcamera / V4L2)     │        │  6 Encoders Hall (INT0–INT5)     │
└────────────────────────────────────┘        └──────────────────────────────────┘
```

---

## Capas del Stack de Software (RPi5)

```
┌─────────────────────────────────────────┐
│  olympus_controller.py (HLC logic)      │  ← pendiente de implementar
├─────────────────────────────────────────┤
│  rover_bridge.so  (Rust/PyO3)           │
│  - Serial USART3 hacia Arduino          │
│  - GPIO RPi5 para HC-SR04 futuro        │
├─────────────────────────────────────────┤
│  serialport crate  │  rppal crate       │
├─────────────────────────────────────────┤
│  /dev/arduino_mega (udev symlink)       │
├─────────────────────────────────────────┤
│  Yocto Linux — meta-olympus (scarthgap) │
└─────────────────────────────────────────┘
```

---

## Layer Stack de Yocto

| Capa | Descripción | Disponible |
|------|-------------|------------|
| poky/meta | Core de OpenEmbedded | ✅ |
| poky/meta-poky | Distribución Poky | ✅ |
| poky/meta-yocto-bsp | BSPs de referencia | ✅ |
| meta-openembedded/meta-oe | Recetas OE extendidas | ✅ |
| meta-openembedded/meta-python | Paquetes Python | ✅ |
| meta-openembedded/meta-multimedia | Libcamera, GStreamer | ✅ |
| meta-openembedded/meta-networking | WiFi, wpa_supplicant | ✅ |
| meta-raspberrypi | Soporte RPi5 (kernel, firmware) | ✅ |
| **meta-olympus** | Capa personalizada del proyecto | ✅ |
| meta-tensorflow-lite | Inferencia TFLite | ❌ no clonado |
| meta-onnxruntime | Inferencia ONNX Runtime | ❌ no clonado |

> **Nota:** La inferencia ONNX se cubre con `cv2.dnn` (incluido en `python3-opencv`),
> que puede cargar modelos `.onnx` directamente sin necesitar `meta-onnxruntime`.
> Las entradas de `bblayers.conf` y `IMAGE_INSTALL` para estas layers están
> pendientes de limpiar.

---

## Recetas en meta-olympus

| Receta | Descripción | En imagen |
|--------|-------------|-----------|
| python3-rover-bridge | Módulo Rust/PyO3 (serial + GPIO) | ✅ |
| wifi-config | wpa_supplicant configurado | ✅ |
| wifi-power-save | Ahorro energía WiFi (systemd) | ✅ |
| custom-udev-rules | Symlink /dev/arduino_mega | ✅ |
| resize-rootfs | Expansión rootfs (one-shot) | ✅ |
| linux-raspberrypi_%.bbappend | Config kernel powersave | - |
| libcamera-apps_%.bbappend | Fix FILES para rpicam_app.so | - |
| rust-raspi-uart | Binario UART básico (sin vendor) | ❌ |
| rover-hlc-backup | Prototipo HLC en Rust | ❌ |

---

## Protocolo MSM (USART3 — 115200 baud)

La RPi5 se comunica con el Arduino usando el protocolo ASCII de la MSM.
Cada trama termina en `\n`. El Arduino responde en <300 ms.

### Comandos RPi5 → Arduino

| Comando | Acción |
|---------|--------|
| `PING` | Keepalive — resetea watchdog Arduino (2 s max sin PING → FAULT) |
| `STB` | Pasar a Standby (motores parados) |
| `EXP:<l>:<r>` | Explorar con velocidades izquierda/derecha (ej: `EXP:80:80`) |
| `AVD:L` | Girar izquierda (evasión) |
| `AVD:R` | Girar derecha (evasión) |
| `RET` | Retroceder |
| `FLT` | Forzar FAULT desde HLC |
| `RST` | Reset → Standby |

### Respuestas Arduino → RPi5

| Respuesta | Significado |
|-----------|-------------|
| `PONG` | Respuesta a PING |
| `ACK:<STATE>` | Transición confirmada (ej: `ACK:EXP`) |
| `TLM:<SAFETY>:<MASK>` | Telemetría periódica (~1 s) |
| `ERR:ESTOP` | Comando rechazado (Arduino en FAULT) |
| `ERR:WDOG` | Watchdog expirado → FAULT |
| `ERR:UNKNOWN` | Comando no reconocido |

---

## Sensores

### HC-SR04 — capa de emergencia (LLC)

Conectado al **Arduino Mega** y gestionado en el firmware LLC.

| Pin HC-SR04 | Pin Arduino |
|-------------|-------------|
| Trigger | D38 |
| Echo | D39 |

- Lectura cada 5 ciclos (~100 ms)
- Distancia < 200 mm → MSM transiciona a FAULT automáticamente
- La RPi5 recibe la notificación via `TLM` o `ACK:FLT`

### Cámara CSI — visión (HLC)

Cámara CSI conectada a la RPi5. Gestionada con libcamera + OpenCV V4L2.

- Detección de obstáculos: `cv2.dnn` + YOLOv8n ONNX (~8–12 FPS a 640×480)
- Decisión de evasión: posición X del bounding box → `AVD:L` / `AVD:R`
- Ver `docs/obstacle-detection-idea.md` para el plan completo

### HC-SR04 secundario — GPIO RPi5 (futuro)

Los métodos `setup_ultrasonic` / `get_ultrasonic_distance` de `rover_bridge`
están preparados para un segundo HC-SR04 conectado directamente a GPIO RPi5.
No está instalado en el hardware actual.

---

## Configuración de Hardware (local.conf)

```
MACHINE = "raspberrypi5"
arm_freq=1500       # CPU limitada a 1.5 GHz para ahorro de batería
enable_uart=1       # UART hardware habilitado
dtoverlay=disable-bt  # Bluetooth desactivado (libera UART principal)
camera_auto_detect=1  # Detección automática cámara CSI
VIDEO_CAMERA = "1"
```
