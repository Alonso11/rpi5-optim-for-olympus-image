use pyo3::prelude::*;

/// 1. Lógica pura de Rust (Testeable sin Python)
struct RoverCore {
    state: String,
    _port_name: String,
}

impl RoverCore {
    fn new(port_name: String) -> Self {
        RoverCore { 
            state: "IDLE".to_string(),
            _port_name: port_name 
        }
    }

    fn update_ia_status(&mut self, classification: &str) -> String {
        match classification {
            "CLEAR" => self.send_to_arduino("MOVE:FWD:100\n"),
            "OBSTACLE" => self.send_to_arduino("MOVE:STOP:0\n"),
            _ => { 
                self.state = "UNKNOWN".to_string();
                self.state.clone()
            }
        }
    }

    fn get_state(&self) -> String {
        self.state.clone()
    }

    fn send_to_arduino(&mut self, cmd: &str) -> String {
        // En una implementación real, aquí se usaría self.port_name para UART
        self.state = cmd.to_string();
        self.state.clone()
    }
}

/// 2. Envoltura de PyO3 (Interfaz para Python)
#[pyclass]
struct Rover {
    core: RoverCore,
}

#[pymethods]
impl Rover {
    #[new]
    fn new(port_name: String) -> Self {
        Rover { 
            core: RoverCore::new(port_name) 
        }
    }

    fn update_ia_status(&mut self, classification: &str) -> PyResult<()> {
        self.core.update_ia_status(classification);
        Ok(())
    }

    fn get_state(&self) -> String {
        self.core.get_state()
    }
}

#[pymodule]
fn rover_bridge(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<Rover>()?;
    Ok(())
}

/// 3. Pruebas Unitarias (Validan RoverCore sin dependencias de Python)
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_rover_initial_state() {
        let rover = RoverCore::new("/dev/ttyACM0".to_string());
        assert_eq!(rover.get_state(), "IDLE");
    }

    #[test]
    fn test_rover_obstacle_logic() {
        let mut rover = RoverCore::new("/dev/ttyACM0".to_string());
        
        rover.update_ia_status("OBSTACLE");
        assert_eq!(rover.get_state(), "MOVE:STOP:0\n");
        
        rover.update_ia_status("CLEAR");
        assert_eq!(rover.get_state(), "MOVE:FWD:100\n");
    }
}
