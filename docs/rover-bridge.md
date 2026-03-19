# rover_bridge — Módulo Rust/PyO3

## Descripción

`rover_bridge` es una extensión nativa de Python escrita en Rust y compilada como
librería dinámica (`.so`). Expone la clase `Rover` que encapsula la comunicación
serial con el Arduino Mega y el control GPIO del sensor HC-SR04.

Se instala en `/usr/lib/python3.12/site-packages/rover_bridge.so`.

---

## Tecnologías

| Componente | Tecnología |
|------------|------------|
| FFI Python ↔ Rust | PyO3 0.22.6 |
| Comunicación serial | serialport 4.8.1 |
| GPIO RPi5 | rppal 0.22.1 |
| Build offline | 46 crates vendoreados |

---

## API Python

### `Rover(port: str, baud_rate: int)`

Abre el puerto serial y espera 2 segundos para el reset del Arduino (DTR).

```python
import rover_bridge

rover = rover_bridge.Rover("/dev/arduino_mega", 115200)
```

---

### `rover.send_command(cmd: str) -> str`

Envía un comando ASCII al Arduino (agrega `\n` automáticamente).
Retorna `"Enviado: {cmd}"` como confirmación.

```python
rover.send_command("F")   # Avanzar
rover.send_command("S")   # Parar
rover.send_command("MOVE:FWD:100")  # Protocolo largo
```

---

### `rover.setup_ultrasonic(trigger_pin: int, echo_pin: int) -> str`

Configura los pines GPIO para el sensor HC-SR04.
Debe llamarse antes de `get_ultrasonic_distance()`.

```python
rover.setup_ultrasonic(23, 24)
# Retorna: "Ultrasonico configurado: Trig=23, Echo=24"
```

---

### `rover.get_ultrasonic_distance() -> float | None`

Lanza un pulso de 10 µs y mide el tiempo de eco.
Retorna la distancia en milímetros, o `None` si está fuera de rango (< 20 mm o > 4000 mm).

```python
distancia = rover.get_ultrasonic_distance()
if distancia:
    print(f"{distancia:.2f} mm")
```

---

## Protocolo Serial

```
RPi5                    Arduino Mega
 │                           │
 │── "F\n" ─────────────────►│
 │                           │  (ejecuta motor adelante)
 │◄─── "OK: Ejecutando ADELANTE\n" ──│
```

- Formato: `{COMANDO}\n`
- Buffer Arduino: 32 bytes máximo
- Baud rate: 115200 (error de trama < 0.16% a 16 MHz)

---

## Implementación Rust

```rust
#[pyclass]
struct Rover {
    port: Mutex<Box<dyn serialport::SerialPort>>,
    trigger_pin: Mutex<Option<OutputPin>>,
    echo_pin: Mutex<Option<InputPin>>,
}

#[pymethods]
impl Rover {
    #[new]
    fn new(port_name: &str, baud_rate: u32) -> PyResult<Self> { ... }
    fn send_command(&self, cmd: &str) -> PyResult<String> { ... }
    fn setup_ultrasonic(&self, trigger: u8, echo: u8) -> PyResult<String> { ... }
    fn get_ultrasonic_distance(&self) -> PyResult<Option<f64>> { ... }
}
```

Todos los recursos de hardware están protegidos con `Mutex<T>` para acceso seguro
desde múltiples hilos Python (GIL liberado en operaciones I/O).

---

## Build en Yocto

La receta `python3-rover-bridge.bb` compila el módulo en modo offline:

```bash
# do_configure:prepend — linkea los crates vendoreados
ln -sf ${S}/vendor/* ${WORKDIR}/cargo_home/bitbake/

# Variables de compilación cruzada para PyO3
export CARGO_OFFLINE = "1"
export PYO3_CROSS = "1"
export PYO3_CROSS_PYTHON_VERSION = "3.12"
export PYO3_CROSS_LIB_DIR = "${STAGING_LIBDIR}"
```

El binario resultante `librover_bridge.so` se instala como `rover_bridge.so`
en el directorio site-packages de Python 3.12.
