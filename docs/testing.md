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

### 7. `olympus_hlc` — Paquete HLC v3.0

#### Tests unitarios (sin hardware)

Requieren únicamente Python 3 y `pytest`. Se ejecutan en cualquier máquina.

```bash
# En la máquina de desarrollo (no se necesita la RPi5)
cd olympus-hlc-rpi5/layers/meta-olympus/recipes-apps/python3-rover-bridge/files
pip install pytest
pytest tests/ -v
```

Resultado esperado:
```
tests/test_hlc.py::test_tlmframe_parse_valid         PASSED
tests/test_hlc.py::test_tlmframe_parse_invalid       PASSED
tests/test_hlc.py::test_roverstate_from_ack          PASSED
tests/test_hlc.py::test_energy_monitor               PASSED
tests/test_hlc.py::test_thermal_monitor              PASSED
tests/test_hlc.py::test_slip_monitor                 PASSED
tests/test_hlc.py::test_safe_mode_battery            PASSED
tests/test_hlc.py::test_safe_mode_fault              PASSED
tests/test_hlc.py::test_safe_mode_thermal            PASSED
tests/test_hlc.py::test_safe_mode_reset              PASSED
tests/test_hlc.py::test_waypoint_tracker             PASSED
tests/test_hlc.py::test_comm_link_monitor            PASSED
tests/test_hlc.py::test_csp_round_trip               PASSED
tests/test_hlc.py::test_csp_bad_crc                  PASSED
tests/test_hlc.py::test_parse_response               PASSED
tests/test_hlc.py::test_dry_run_rover                PASSED
tests/test_hlc.py::test_engine_dry_run               PASSED
tests/test_hlc.py::test_engine_safe_mode_integration PASSED
```

#### Modo dry-run (sin Arduino)

Permite probar el loop completo sin hardware. `DryRunRover` emite TLM
sintético cada ~1 s para que el watchdog no dispare.

```bash
python3 -m olympus_hlc --mode manual --dry-run
```

```bash
python3 -m olympus_hlc --mode vision --model /usr/share/olympus/models/yolov8n.onnx --dry-run
```

#### Modo GCS dry-run

```bash
python3 -m olympus_hlc --mode gcs --dry-run
# Escucha en UDP :9000, reenvía TLM al GCS vía :9001
```

#### Modo manual (con Arduino)

```bash
python3 -m olympus_hlc --mode manual
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
python3 -m olympus_hlc --mode vision --model /usr/share/olympus/models/yolov8n.onnx
```

#### Opciones adicionales

```bash
python3 -m olympus_hlc --mode manual \
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

#### Controlador legacy

El script `olympus_controller.py` (v2.4) sigue instalado en `/usr/bin/` para
compatibilidad. Acepta los mismos argumentos que el paquete nuevo.

```bash
olympus_controller.py --mode manual --dry-run
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
| Ciclo lento > 1500 ms | Inferencia YOLOv8n lenta en CPU | Normal en RPi5 sin NPU; subir `vision_conf_min` en `/etc/olympus/olympus_controller.yaml` |
