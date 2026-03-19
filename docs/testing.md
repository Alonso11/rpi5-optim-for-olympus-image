# Guía de Testing en la RPi5

Todos los scripts se instalan en `/usr/bin/` y son ejecutables directamente.
Conéctate a la RPi5 por SSH antes de comenzar.

```bash
ssh root@<IP_RPi5>
```

---

## Requisitos previos

- Arduino Mega conectado por USB
- Firmware del LLC cargado y corriendo
- `/dev/arduino_mega` presente (verificar con `ls /dev/arduino_mega`)

---

## Orden de prueba recomendado

### 1. Verificar el dispositivo serial

```bash
ls -l /dev/arduino_mega
# Esperado: lrwxrwxrwx ... /dev/arduino_mega -> ttyUSB0 (o ttyACM0)
```

---

### 2. `test_rover.py` — Prueba básica con pyserial

Verifica la comunicación serial sin depender del módulo Rust.

```bash
test_rover.py
```

Menú interactivo:
- `1` — Avanzar 5 segundos y parar
- `2` — Avanzar indefinidamente
- `3` — Parar
- `q` — Salir

**Resultado esperado:** motores responden a los comandos.

---

### 3. `test_bridge.py` — Prueba automatizada del módulo Rust

Verifica que `rover_bridge.so` se carga correctamente y puede comunicarse.

```bash
test_bridge.py
```

Secuencia automática:
1. Crea instancia `Rover` (2 segundos de espera reset Arduino)
2. Envía `F` (avanza 3 segundos)
3. Envía `S` (para)

**Resultado esperado:**
```
Instancia de Rover creada en Rust correctamente.
Moviendo motor (Rust gestiona el puerto serie)...
Respuesta de Rust: Enviado: F
Deteniendo motor...
Respuesta de Rust: Enviado: S
```

---

### 4. `test_bridge_interactive.py` — Control manual completo

El script principal para verificar comunicación en tiempo real.

```bash
test_bridge_interactive.py
```

Con puerto alternativo si `/dev/arduino_mega` no existe:
```bash
test_bridge_interactive.py --port /dev/ttyUSB0 --baud 115200
```

Comandos disponibles en el prompt:
| Comando | Acción |
|---------|--------|
| `F` | Avanzar |
| `B` | Retroceder |
| `L` | Girar izquierda |
| `R` | Girar derecha |
| `S` | Parar |
| `MOVE:FWD:100` | Protocolo largo |
| `q` | Salir |

---

### 5. `test_ultrasonic_rpi.py` — Sensor HC-SR04

Requiere el sensor conectado en GPIO 23 (Trigger) y GPIO 24 (Echo).

```bash
test_ultrasonic_rpi.py
```

**Resultado esperado:**
```
[OK] Conexión con el puente de Rust establecida.
[OK] Ultrasonico configurado: Trig=23, Echo=24
Iniciando mediciones...
Distancia: 235.40 mm
```

Presiona `Ctrl+C` para detener.

---

### 6. `test_opencv_camera.py` — Cámara CSI + OpenCV

Requiere cámara CSI conectada. Verificar primero con:

```bash
rpicam-hello
```

Luego:
```bash
test_opencv_camera.py
```

**Resultado esperado:**
```
[OK] Cámara iniciada. Capturando un frame de prueba...
[OK] Frame guardado en: /root/camera_test_raw.jpg
[OK] Detección de bordes (Canny) realizada y guardada.
```

Para ver las imágenes, cópialas a tu máquina local:
```bash
# Desde tu máquina local
gcloud compute scp instance-20260309-151629:~/camera_test_raw.jpg ./ --zone=us-central1-a
```

---

## Diagnóstico de problemas comunes

| Síntoma | Causa probable | Solución |
|---------|---------------|----------|
| `/dev/arduino_mega` no existe | Arduino no detectado | Verificar cable USB, revisar `dmesg` |
| `Error al abrir el puerto` | Permisos o puerto ocupado | Ejecutar como root, matar procesos que usen el puerto |
| `Error al crear el objeto Rover` | `rover_bridge.so` no encontrado | Verificar `python3 -c "import rover_bridge"` |
| Motores no responden | Baud rate incorrecto o firmware | Verificar firmware Arduino con 115200 |
| `Fuera de rango` en ultrasónico | Objeto muy cerca/lejos o sin eco | Rango válido: 20–4000 mm |
| Cámara no abre | libcamera no inicializada | Probar `rpicam-hello` primero |
