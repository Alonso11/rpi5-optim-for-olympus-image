use pyo3::prelude::*;
use std::time::Duration;
use serialport;

#[pyclass]
struct Rover {
    state: String,
    port_name: String,
}

#[pymethods]
impl Rover {
    #[new]
    fn new(port_name: String) -> Self {
        Rover { 
            state: "IDLE".to_string(),
            port_name 
        }
    }

    /// Método para actualizar el estado del rover basado en la IA (desde Python)
    fn update_ia_status(&mut self, classification: &str) -> PyResult<()> {
        match classification {
            "CLEAR" => self.send_to_arduino("MOVE:FWD:100\n"),
            "OBSTACLE" => self.send_to_arduino("MOVE:STOP:0\n"),
            _ => { 
                self.state = "UNKNOWN".to_string();
                Ok(())
            }
        }
    }

    /// Obtener el estado interno de la máquina de estados de Rust
    fn get_state(&self) -> String {
        self.state.clone()
    }

    /// Método privado de ayuda para el envío UART
    fn send_to_arduino(&mut self, cmd: &str) -> PyResult<()> {
        // Lógica de UART real aquí (usando serialport)
        // Por ahora simulamos el cambio de estado
        self.state = cmd.to_string();
        println!("Rust [Bridge]: Enviando a Arduino -> {}", cmd);
        Ok(())
    }
}

/// Definición del módulo de Python que se importará como `import rover_bridge`
#[pymodule]
fn rover_bridge(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<Rover>()?;
    Ok(())
}
