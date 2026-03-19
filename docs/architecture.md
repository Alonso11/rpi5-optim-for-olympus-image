# Arquitectura del Sistema Olympus

## Visión General

El proyecto Olympus implementa un rover controlado por dos microcontroladores:

- **RPi5 (HLC)** — High-Level Controller. Ejecuta una imagen Linux personalizada
  construida con Yocto (rama scarthgap). Responsable de la lógica de alto nivel,
  visión por computadora, sensores y comunicación con el LLC.
- **Arduino Mega 2560 (LLC)** — Low-Level Controller. Ejecuta el firmware de
  control de motores en tiempo real. Recibe comandos ASCII por UART/USB.

```
┌────────────────────────────────────┐        ┌──────────────────────────┐
│  Raspberry Pi 5 (HLC)              │        │  Arduino Mega 2560 (LLC) │
│  Yocto — meta-olympus              │        │  rover-low-level-ctrl    │
│                                    │  USB   │                          │
│  rover_bridge.so (Rust/PyO3) ──────┼────────┼─── CommandInterface      │
│  /dev/arduino_mega                 │        │    USART0 @ 115200       │
│                                    │        │                          │
│  python3 (HLC logic)               │        │  Motores (L298N/BTS7960) │
│  OpenCV / TFLite / ONNX            │        │  Sensores ultrasónicos   │
└────────────────────────────────────┘        └──────────────────────────┘
         │
         │ GPIO 23/24
         ▼
    HC-SR04 (Ultrasónico)
```

---

## Capas del Stack de Software (RPi5)

```
┌─────────────────────────────────────────┐
│  Aplicación Python (HLC logic)          │
├─────────────────────────────────────────┤
│  rover_bridge.so  (Rust/PyO3)           │
│  - Serial UART hacia Arduino            │
│  - GPIO para HC-SR04                    │
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

| Capa | Descripción |
|------|-------------|
| poky/meta | Core de OpenEmbedded |
| poky/meta-poky | Distribución Poky |
| poky/meta-yocto-bsp | BSPs de referencia |
| meta-openembedded/meta-oe | Recetas OE extendidas |
| meta-openembedded/meta-python | Paquetes Python |
| meta-openembedded/meta-multimedia | Libcamera, GStreamer |
| meta-openembedded/meta-networking | WiFi, wpa_supplicant |
| meta-raspberrypi | Soporte RPi5 (kernel, firmware) |
| meta-tensorflow-lite | Inferencia TFLite |
| meta-onnxruntime | Inferencia ONNX Runtime |
| **meta-olympus** | Capa personalizada del proyecto |

---

## Recetas en meta-olympus

| Receta | Descripción | En imagen |
|--------|-------------|-----------|
| python3-rover-bridge | Módulo Rust/PyO3 (serial + GPIO) | SI |
| wifi-config | wpa_supplicant configurado | SI |
| wifi-power-save | Ahorro energía WiFi (systemd) | SI |
| custom-udev-rules | Symlink /dev/arduino_mega | SI |
| resize-rootfs | Expansión rootfs (one-shot) | SI |
| linux-raspberrypi_%.bbappend | Config kernel powersave | - |
| libcamera-apps_%.bbappend | Fix FILES para rpicam_app.so | - |
| rust-raspi-uart | Binario UART básico (sin vendor) | NO |
| rover-hlc-backup | Prototipo HLC en Rust | NO |

---

## Comunicación UART

- **Interfaz:** USB Serial (CH340 o ATmega16U2)
- **Puerto:** `/dev/arduino_mega` (symlink udev estable)
- **Baud rate:** 115200
- **Protocolo:** ASCII, terminado en `\n`
- **Timeout:** 100 ms

### Comandos soportados

| Comando | Acción |
|---------|--------|
| `F` | Avanzar |
| `B` | Retroceder |
| `L` | Girar izquierda |
| `R` | Girar derecha |
| `S` | Parar |
| `MOVE:FWD:100` | Protocolo largo (velocidad) |

---

## Sensor Ultrasónico HC-SR04

Conectado directamente a los GPIO de la RPi5 y gestionado desde Rust via `rppal`:

| Pin HC-SR04 | GPIO RPi5 (BCM) |
|-------------|-----------------|
| Trigger | 23 |
| Echo | 24 |

- Pulso trigger: 10 µs
- Fórmula: `distancia_mm = (t_echo_us × 0.343) / 2`
- Rango válido: 20 mm – 4000 mm
- Frecuencia de muestreo recomendada: 10 Hz

---

## Configuración de Hardware (local.conf)

```
MACHINE = "raspberrypi5"
RPI_EXTRA_CONFIG = "
    enable_uart=1
    dtoverlay=disable-bt
"
```

- `enable_uart=1` — habilita el UART hardware en `/dev/ttyAMA0`
- `dtoverlay=disable-bt` — libera el UART principal desactivando Bluetooth
