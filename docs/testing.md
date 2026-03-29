# Guía de Testing en la RPi5

Todos los scripts se instalan en `/usr/bin/` y son ejecutables directamente.
Conéctate a la RPi5 por SSH antes de comenzar.

```bash
ssh root@<IP_RPi5>
```

---

## Requisitos previos

- Arduino Mega conectado por USB con firmware LLC cargado
- `/dev/arduino_mega` presente (verificar con `ls /dev/arduino_mega`)

---

## Orden de prueba recomendado

### 1. Verificar el dispositivo serial

```bash
ls -l /dev/arduino_mega
# Esperado: lrwxrwxrwx ... /dev/arduino_mega -> ttyACM0
```

---

### 2. `test_rover.py` — Prueba básica pyserial (legacy)

Verifica la comunicación serial con pyserial directamente (sin rover_bridge).
Útil como diagnóstico si `rover_bridge.so` no carga.

```bash
test_rover.py
```

Menú interactivo (protocolo de bajo nivel básico):
- `1` — Avanzar 5 segundos y parar
- `2` — Avanzar indefinidamente
- `3` — Parar
- `q` — Salir

---

### 3. `test_bridge.py` — Prueba del módulo Rust (protocolo MSM)

Verifica que `rover_bridge.so` carga correctamente y puede comunicarse
con el Arduino usando el protocolo MSM.

```bash
test_bridge.py
```

Secuencia automática:
1. Crea instancia `Rover` (2 segundos de espera reset Arduino)
2. Envía `PING` → espera `PONG`
3. Envía `STB` → espera `ACK:STB`

**Resultado esperado:**
```
[OK] Conexión con el puente de Rust establecida.
[OK] PONG recibido
[OK] ACK:STB recibido
```

---

### 4. `test_bridge_interactive.py` — Control manual MSM completo

Envía comandos MSM directamente al Arduino y muestra la respuesta.

```bash
test_bridge_interactive.py
```

Con puerto alternativo:
```bash
test_bridge_interactive.py --port /dev/ttyACM0 --baud 115200
```

Comandos disponibles en el prompt:
| Comando | Acción MSM |
|---------|------------|
| `PING` | Keepalive |
| `STB` | Standby |
| `EXP:80:80` | Explorar (vel. izq:der) |
| `AVD:L` / `AVD:R` | Evasión |
| `RET` | Retroceder |
| `RST` | Reset desde FAULT |
| `q` | Salir |

---

### 5. `test_ultrasonic_rpi.py` — Sensor HC-SR04 en GPIO RPi5 (futuro)

Requiere un segundo HC-SR04 conectado directamente a GPIO RPi5 (no instalado
en hardware actual). El HC-SR04 activo del rover está en el Arduino (D38/D39).

```bash
test_ultrasonic_rpi.py
```

**Resultado esperado (cuando esté instalado):**
```
[OK] Conexión con el puente de Rust establecida.
[OK] Ultrasonico configurado: Trig=23, Echo=24
Distancia: 235.40 mm
```

---

### 6. `test_opencv_camera.py` — Cámara CSI + OpenCV

Requiere cámara IMX219 conectada en CAM0.

Verificar primero que libcamera detecta la cámara:
```bash
rpicam-hello --list-cameras
```

Luego:
```bash
test_opencv_camera.py
```

**Resultado esperado:**
```
[OK] Frame capturado: 640x480
[OK] Frame guardado en: /root/camera_test_raw.jpg
[OK] Detección de bordes (Canny) realizada.
```

Para copiar imágenes a la máquina local:
```bash
scp root@<IP_RPi5>:/root/camera_test_raw.jpg ./
```

---

### 7. `olympus_controller.py` — Controlador HLC completo

#### Modo dry-run (sin Arduino)

Permite probar el loop completo sin hardware. `DryRunRover` emite TLM
sintético cada ~1 s para que el watchdog no dispare.

```bash
olympus_controller.py --mode manual --dry-run
```

```bash
olympus_controller.py --mode vision --model /usr/share/olympus/models/yolov8n.onnx --dry-run
```

#### Modo manual (con Arduino)

```bash
olympus_controller.py --mode manual
```

Shortcuts en el prompt:
| Shortcut | Comando enviado |
|----------|-----------------|
| `exp 80 80` | `EXP:80:80` |
| `avl` | `AVD:L` |
| `avr` | `AVD:R` |
| `ret` | `RET` |
| `stb` | `STB` |
| `ping` | `PING` |
| `rst` | `RST` |
| `q` | salir (envía STB) |

#### Modo visión (con Arduino + cámara)

```bash
olympus_controller.py --mode vision --model /usr/share/olympus/models/yolov8n.onnx
```

#### Opciones adicionales

```bash
olympus_controller.py --mode manual \
    --port /dev/ttyACM0 \
    --baud 115200 \
    --log-path /tmp/hlc_test.log
```

#### Log generado

```
[2026-03-29T10:00:00.123] [INFO ] [CTRL   ] Starting in MANUAL mode
[2026-03-29T10:00:01.124] [INFO ] [TLM    ] NORMAL stall=000000 batt=15200mV/1200mA dist=800mm t=1000ms
[2026-03-29T10:00:01.125] [INFO ] [CMD    ] STB              → ack:STB
[2026-03-29T10:00:01.126] [INFO ] [MSM    ] STB → STB  [ACK:STB]
```

---

## Diagnóstico de problemas comunes

| Síntoma | Causa probable | Solución |
|---------|---------------|----------|
| `/dev/arduino_mega` no existe | Arduino no detectado o regla udev no cargada | `dmesg \| grep ACM`; verificar `udevadm trigger` |
| `IOError` al abrir puerto | Puerto ocupado o permisos | Ejecutar como root; `fuser /dev/arduino_mega` |
| `ImportError: rover_bridge` | `.so` no instalado | `python3 -c "import rover_bridge"` para diagnóstico |
| `TimeoutError` esperando respuesta | Firmware LLC no cargado o baud incorrecto | Verificar firmware con `test_rover.py` |
| `sin TLM por 5+ s` en el log | Firmware no emite TLM o enlace roto | Verificar firmware LLC versión >= v2.4 |
| Cámara no detectada | dtoverlay incorrecto o conector CAM1 | Verificar `rpicam-hello --list-cameras`; usar CAM0 (conector derecho) |
| Ciclo lento > 1500 ms | Inferencia YOLOv8n lenta en CPU | Normal en RPi5 sin NPU; ajustar `VISION_CONF_MIN` |
