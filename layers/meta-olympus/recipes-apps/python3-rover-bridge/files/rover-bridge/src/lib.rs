// Version: v1.0
use pyo3::prelude::*;
use serialport;
use std::time::{Duration, Instant};
use std::io::Write;
use std::sync::Mutex;
use rppal::gpio::{Gpio, InputPin, OutputPin};

#[pyclass]
struct Rover {
    port: Mutex<Box<dyn serialport::SerialPort>>,
    // Sensores opcionales (se inicializan con setup_*)
    ultrasonic_trigger: Mutex<Option<OutputPin>>,
    ultrasonic_echo: Mutex<Option<InputPin>>,
}

#[pymethods]
impl Rover {
    #[new]
    fn new(port_name: String, baud_rate: u32) -> PyResult<Self> {
        let port = serialport::new(&port_name, baud_rate)
            .timeout(Duration::from_millis(100))
            .open()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Error serial al abrir {}: {}", port_name, e)))?;

        // Al abrir el puerto, la mayoría de Arduinos se resetean (DTR).
        // Esperamos 2 segundos para que el bootloader termine y el firmware inicie.
        std::thread::sleep(Duration::from_secs(2));

        Ok(Rover {
            port: Mutex::new(port),
            ultrasonic_trigger: Mutex::new(None),
            ultrasonic_echo: Mutex::new(None),
        })
    }

    /// Configura los pines del sensor ultrasónico HC-SR04
    fn setup_ultrasonic(&self, trigger_pin: u8, echo_pin: u8) -> PyResult<String> {
        let gpio = Gpio::new()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Error GPIO: {}", e)))?;

        let mut trigger = gpio.get(trigger_pin)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Error Pin Trigger {}: {}", trigger_pin, e)))?
            .into_output();
        
        let echo = gpio.get(echo_pin)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Error Pin Echo {}: {}", echo_pin, e)))?
            .into_input();

        // Aseguramos que el trigger inicie en bajo
        trigger.set_low();

        let mut t_lock = self.ultrasonic_trigger.lock().unwrap();
        let mut e_lock = self.ultrasonic_echo.lock().unwrap();
        
        *t_lock = Some(trigger);
        *e_lock = Some(echo);

        Ok(format!("Ultrasonico configurado: Trig={}, Echo={}", trigger_pin, echo_pin))
    }

    /// Mide la distancia en milímetros (mm)
    fn get_ultrasonic_distance(&self) -> PyResult<Option<f64>> {
        let mut t_lock = self.ultrasonic_trigger.lock().unwrap();
        let e_lock = self.ultrasonic_echo.lock().unwrap();

        let (trigger, echo) = match (t_lock.as_mut(), e_lock.as_ref()) {
            (Some(t), Some(e)) => (t, e),
            _ => return Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("Sensor ultrasonico no configurado. Llame a setup_ultrasonic primero.")),
        };

        // 1. Enviar pulso de disparo (10 microsegundos)
        trigger.set_high();
        std::thread::sleep(Duration::from_micros(10));
        trigger.set_low();

        // 2. Esperar a que el Echo suba (inicio del pulso)
        let start_wait = Instant::now();
        while echo.is_low() {
            if start_wait.elapsed() > Duration::from_millis(30) { return Ok(None); }
        }
        let pulse_start = Instant::now();

        // 3. Esperar a que el Echo baje (fin del pulso)
        while echo.is_high() {
            if pulse_start.elapsed() > Duration::from_millis(30) { return Ok(None); }
        }
        let pulse_duration = pulse_start.elapsed();

        // 4. Calcular distancia: (tiempo * velocidad_sonido) / 2
        // Velocidad del sonido aprox 343 m/s = 0.343 mm/us
        let distance_mm = (pulse_duration.as_micros() as f64 * 0.343) / 2.0;

        if distance_mm > 4000.0 || distance_mm < 20.0 {
            Ok(None)
        } else {
            Ok(Some(distance_mm))
        }
    }

    /// Envía un comando al Arduino y retorna éxito o error
    fn send_command(&self, cmd: String) -> PyResult<String> {
        let mut port = self.port.lock()
            .map_err(|_| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No se pudo bloquear el puerto serie (Mutex error)"))?;

        let formatted_cmd = format!("{}\n", cmd);
        port.write_all(formatted_cmd.as_bytes())
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Error escritura: {}", e)))?;
        
        port.flush()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Error flush: {}", e)))?;

        Ok(format!("Enviado: {}", cmd))
    }
}

#[pymodule]
fn rover_bridge(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Rover>()?;
    Ok(())
}
