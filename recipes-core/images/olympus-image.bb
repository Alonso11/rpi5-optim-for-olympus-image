SUMMARY = "Imagen Olympus: API WiFi + UART para Arduino Mega"
LICENSE = "MIT"

inherit core-image

# Añadir soporte para WiFi, UART y herramientas de red
IMAGE_INSTALL:append = " \
    wifi-power-save \
    packagegroup-core-boot \
    kernel-modules \
    iw \
    wpa-supplicant \
    linux-firmware-rpidistro-bcm43455 \
    python3-base \
    python3-pyserial \
    cpufrequtils \
    powertop \
"

# Mantenemos WiFi, pero eliminamos Gráficos y Bluetooth para ahorrar energía
DISTRO_FEATURES:append = " wifi"
DISTRO_FEATURES:remove = "x11 wayland vulkan opengl bluetooth"
