# RPi5 Olympus OS - Professional Yocto Project

Este repositorio es un **Proyecto Contenedor** diseñado para construir una imagen de Linux ultra-eficiente para la Raspberry Pi 5, optimizada para el uso con baterías de litio en el proyecto TFG Olympus.

## Estructura del Proyecto

*   **\`layers/meta-olympus/\`**: Capa personalizada con optimizaciones de energía (WiFi Power Save, Kernel Powersave Governor).
*   **\`build/conf/\`**: Archivos de configuración maestra (\`local.conf\` y \`bblayers.conf\`) con parámetros de hardware pre-configurados (CPU a 1.5GHz, LEDs desactivados, UART habilitada).
*   **\`scripts/setup-env.sh\`**: Script de automatización para descargar todas las capas oficiales necesarias (Poky, Meta-RaspberryPi, Meta-OE).

## Guía de Inicio Rápido (Google Cloud)

Para compilar la imagen en tu máquina virtual:

1.  **Clonar este repositorio:**
    \`\`\`bash
    git clone https://github.com/Alonso11/rpi5-optim-for-olympus-image.git
    cd rpi5-optim-for-olympus-image
    \`\`\`

2.  **Preparar el entorno:**
    \`\`\`bash
    ./scripts/setup-env.sh
    \`\`\`

3.  **Inicializar Bitbake:**
    \`\`\`bash
    source layers/poky/oe-init-build-env build
    \`\`\`

4.  **Compilar la imagen Olympus:**
    \`\`\`bash
    bitbake olympus-image
    \`\`\`

## Optimizaciones de Energía Incluidas

*   **CPU Governor:** Configurado en \`powersave\` por defecto en el kernel.
*   **Frecuencia:** Limitada a 1.5GHz para reducir consumo térmico y eléctrico.
*   **WiFi:** Modo \`power_save\` activado automáticamente al arranque.
*   **Hardware:** Bluetooth y LEDs de estado desactivados para minimizar micro-amperios.
*   **UART:** Habilitada para comunicación con Arduino Mega.

---
Proyecto TFG Olympus 2026.
