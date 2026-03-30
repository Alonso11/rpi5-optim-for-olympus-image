# Arquitectura del Sistema Olympus

## Visión General

El proyecto Olympus implementa un rover controlado por dos nodos:

- **RPi5 (HLC)** — High-Level Controller. Ejecuta una imagen Linux personalizada
  construida con Yocto (rama scarthgap). Responsable de la lógica de alto nivel,
  visión por computadora y comunicación con el LLC.
- **Arduino Mega 2560 (LLC)** — Low-Level Controller. Ejecuta el firmware de
  control de motores en tiempo real (Rust/AVR). Recibe comandos ASCII por USB
  (USART0 → chip CDC-ACM ATmega16U2).

```
┌────────────────────────────────────┐        ┌──────────────────────────────────┐
│  Raspberry Pi 5 (HLC)              │        │  Arduino Mega 2560 (LLC)         │
│  Yocto — meta-olympus              │        │  rover-low-level-controller      │
│                                    │        │                                  │
│  rover_bridge.so (Rust/PyO3) ──────┼─ USB ──┼─── USART0 (CDC-ACM)             │
│  /dev/arduino_mega                 │        │    MSM: STB/EXP/AVD/RET/FLT     │
│                                    │        │                                  │
│  olympus_controller.py (v1.9)      │        │  6 Motores (PWM L298N)           │
│  OpenCV + cv2.dnn (YOLOv8n/-seg)  │        │  HC-SR04 D38(Trig) D39(Echo)     │
│  Cámara CSI (libcamera / V4L2)     │        │  VL53L0X (ToF I2C)               │
│                                    │        │  6 Encoders Hall (INT0–INT5)     │
└────────────────────────────────────┘        └──────────────────────────────────┘
```

---

## Capas del Stack de Software (RPi5)

```
┌─────────────────────────────────────────────────────┐
│  olympus_controller.py (v1.9)                       │
│  - _load_config() (YAML /etc/olympus/, fallback)    │
│  - RoverMSM + RoverState (espejo estado Arduino)    │
│  - TlmFrame parser (20 campos, ICD LLC)             │
│  - WaypointTracker (5 puntos seguros, SyRS-061)     │
│  - EnergyMonitor (4S Li-ion, EPS-REQ-001)           │
│  - SlipMonitor (stall_mask TLM, RF-004)             │
│  - OlympusLogger (ISO-8601, RotatingFileHandler)    │
│  - VisionSource (bbox: YOLOv8n / seg: YOLOv8n-seg)  │
│  - ManualSource (stdin shortcuts)                   │
├─────────────────────────────────────────────────────┤
│  rover_bridge.so  (Rust/PyO3 — v1.5)               │
│  - send_command(cmd) → respuesta ASCII Arduino      │
│  - recv_tlm()        → frame TLM asíncrono o None   │
│  - setup_ultrasonic / get_ultrasonic_distance [FUTURO] │
├─────────────────────────────────────────────────────┤
│  serialport crate  │  rppal crate                   │
├─────────────────────────────────────────────────────┤
│  /dev/arduino_mega (udev symlink → ttyACM0)         │
├─────────────────────────────────────────────────────┤
│  Yocto Linux — meta-olympus (scarthgap)             │
└─────────────────────────────────────────────────────┘
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

> `meta-tensorflow-lite` y `meta-onnxruntime` no están en el proyecto.
> La inferencia ONNX se cubre con `cv2.dnn` incluido en `python3-opencv`.

---

## Recetas en meta-olympus

| Receta | Descripción | En imagen |
|--------|-------------|-----------|
| `python3-rover-bridge` | Módulo Rust/PyO3 + controlador + modelo ONNX + config YAML | ✅ |
| `wifi-config` | wpa_supplicant configurado | ✅ |
| `wifi-power-save` | Ahorro energía WiFi (systemd) | ✅ |
| `custom-udev-rules` | Symlink /dev/arduino_mega | ✅ |
| `resize-rootfs` | Expansión rootfs one-shot primer arranque | ✅ |
| `libpisp_1.3.0` | Biblioteca ISP pisp para cámara RPi5 | ✅ |
| `linux-raspberrypi_%.bbappend` | Fragmentos kernel powersave + camera DMA-BUF | — |
| `libcamera_%.bbappend` | Fork RPi Foundation, pipeline rpi/pisp | — |
| `libcamera-apps_%.bbappend` | rpicam-apps HEAD, meson feature types | — |
| `opencv_%.bbappend` | Activa BUILD_opencv_dnn para cv2.dnn | — |
| `rpi-config_%.bbappend` | dtoverlay imx219/ov5647, camera_auto_detect=0 | — |

---

## Protocolo MSM (USB CDC-ACM — 115200 baud 8N1)

La RPi5 se comunica con el Arduino a través del USB del Mega (USART0 → ATmega16U2).
Cada trama termina en `\n`. El firmware responde en < 20 ms (timeout HLC 300 ms).
El Arduino emite telemetría extendida (TLM) de forma asíncrona cada ~1 s.

### Comandos RPi5 → Arduino

| Comando | Acción |
|---------|--------|
| `PING` | Keepalive — resetea watchdog Arduino (~2 s sin PING → FAULT) |
| `STB` | Standby (motores parados) |
| `EXP:<l>:<r>` | Explorar con velocidades 0–100 (ej: `EXP:80:80`) |
| `AVD:L` | Girar izquierda (evasión) |
| `AVD:R` | Girar derecha (evasión) |
| `RET` | Retroceder |
| `FLT` | Forzar FAULT desde HLC *(solo disponible como entrada directa en modo manual — no tiene atajo)* |
| `RST` | Reset → Standby |

### Respuestas Arduino → RPi5

| Respuesta | Significado |
|-----------|-------------|
| `PONG` | Respuesta a PING |
| `ACK:<STATE>` | Transición confirmada (ej: `ACK:EXP`) |
| `ERR:ESTOP` | Comando rechazado (Arduino en FAULT) |
| `ERR:WDOG` | Watchdog expirado → FAULT |
| `ERR:UNKNOWN` | Comando no reconocido |

### Frame TLM extendido (asíncrono, ~1 s)

```
TLM:<SAF>:<STALL>:<TS>ms:<MV>mV:<MA>mA:<I0>:<I1>:<I2>:<I3>:<I4>:<I5>:<T>C:<B0>:<B1>:<B2>:<B3>:<B4>:<B5>C:<DIST>mm
```

| Campo | Descripción |
|-------|-------------|
| SAF | Estado de seguridad: NORMAL / WARN / LIMIT / FAULT |
| STALL | Máscara stall 6 bits (bit5=FR … bit0=RL) |
| TS | Tick Arduino en ms (monotónico) |
| MV | Tensión batería en mV (0 = sin lectura) |
| MA | Corriente batería en mA con signo |
| I0–I5 | Corrientes motores FR/FL/CR/CL/RR/RL en mA |
| T | Temperatura ambiente °C |
| B0–B5 | Temperaturas celdas batería °C |
| DIST | Distancia frontal ToF en mm (0 = sin lectura) |

Ver ICD completo: `../TFG_OLYMPUS_BACKUP/srs_rover_olympus/icd/icd_llc.tex`

---

## Capas de Protección de Distancia

```
LLC (hardware):   < 150 mm (VL53L0X ToF)  → FAULT inmediato en Arduino
LLC (hardware):   < 200 mm (HC-SR04)      → FAULT inmediato en Arduino
HLC (táctica):    < 300 mm (campo DIST del TLM) → RET proactivo (WaypointTracker)
```

---

## Supervisión de Energía (4S Li-ion)

| Nivel | Umbral | Acción HLC |
|-------|--------|------------|
| OK | ≥ 14 000 mV (3.5 V/celda) | Normal |
| WARN | 12 800 – 13 999 mV | Log WARN + alerta operador |
| CRITICAL | < 12 800 mV (3.2 V/celda) | Forzar STB inmediato |

---

## Sensores

### HC-SR04 — emergencia hardware (LLC)

| Pin HC-SR04 | Pin Arduino |
|-------------|-------------|
| Trigger | D38 |
| Echo | D39 |

Lectura cada 5 ciclos LLC (~100 ms). Distancia < 200 mm → FAULT automático.

### VL53L0X — ToF I2C (LLC)

Montado en parte frontal del chasis. Distancia < 150 mm → FAULT automático.
Valor reportado en campo `DIST` del frame TLM.

### Cámara CSI — visión (HLC)

- IMX219 genérica en **CAM0** (conector derecho de la RPi5)
- `dtoverlay=imx219,cam0` aplicado automáticamente por `rpi-config_%.bbappend`
- Captura con `rpicam-still --output -` (un frame por llamada vía subprocess) → inferencia con `cv2.dnn.readNetFromONNX`
- Modo `bbox` (referencia): YOLOv8n ONNX — decisión por centro de bounding box
- Modo `segmentation` (GNC-REQ-002): YOLOv8n-seg ONNX — decisión por cobertura de máscara por zona
- Seleccionable via `vision_mode` en `/etc/olympus/olympus_controller.yaml`
- ~1–2 FPS a 640×480 (CPU)

### HC-SR04 secundario — GPIO RPi5 (futuro)

Los métodos `setup_ultrasonic` / `get_ultrasonic_distance` de `rover_bridge.so`
están preparados para un segundo sensor directo en GPIO RPi5. No instalado aún.

---

## Configuración de Hardware relevante

| Parámetro | Valor | Efecto |
|-----------|-------|--------|
| `MACHINE` | raspberrypi5 | BSP target |
| `arm_freq` | 1500 MHz | CPU limitada para ahorro de batería |
| `enable_uart=1` | — | UART hardware habilitado |
| `dtoverlay=disable-bt` | — | Bluetooth desactivado (libera UART PL011) |
| `dtoverlay=imx219,cam0` | — | Cámara IMX219 en conector CAM0 (derecho) |
| `camera_auto_detect=0` | — | Detección manual vía overlays explícitos |
