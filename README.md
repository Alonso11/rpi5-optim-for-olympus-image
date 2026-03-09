# RPi5 Optim for Olympus Image

Esta capa de Yocto Project (`meta-olympus`) está diseñada específicamente para optimizar el consumo de energía de una Raspberry Pi 5 cuando se alimenta con baterías de litio.

## Estructura de la Capa

*   **`conf/layer.conf`**: Registra la capa en el entorno de compilación de Yocto.
*   **`recipes-core/images/olympus-image.bb`**: Receta de la imagen personalizada ligera, eliminando servicios innecesarios (como SSH, WiFi, Bluetooth por defecto).
*   **`recipes-kernel/linux/files/powersave.cfg`**: Configuración del kernel para usar el gobernador de frecuencia `powersave` por defecto, maximizando el ahorro de energía.
*   **`recipes-kernel/linux/linux-raspberrypi_%.bbappend`**: Aplica los parches y configuraciones de energía al kernel oficial de la Raspberry Pi.

## Instalación y Compilación

Para usar esta capa en tu entorno de Yocto:

1.  **Añadir la capa:**
    ```bash
    cd ~/rpi5-yocto-project/build
    bitbake-layers add-layer ../meta-olympus
    ```

2.  **Lanzar la compilación:**
    ```bash
    bitbake olympus-image
    ```

## Optimización de Energía (Próximos Pasos)

*   Desactivar LEDs de la placa.
*   Desactivar salida HDMI por defecto.
*   Ajustar el `config.txt` de la RPi5 para bajar la frecuencia máxima de la CPU.

---
Proyecto desarrollado como parte del TFG Olympus 2026.
