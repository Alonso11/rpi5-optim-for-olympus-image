SUMMARY = "Imagen Olympus: API WiFi + UART para Arduino Mega"
LICENSE = "MIT"

inherit core-image
# Añadir soporte para WiFi, UART, SSH, Redimensionamiento y herramientas de red
IMAGE_INSTALL:append = " \
    custom-udev-rules \
    resize-rootfs \
    wifi-config \
    wifi-power-save \
    packagegroup-core-boot \
    kernel-modules \
    kernel-module-cdc-acm \
    iw \
    wpa-supplicant \
    linux-firmware-rpidistro-bcm43455 \
    python3-core \
    python3-pyserial \
    bash \
    cpufrequtils \
    powertop \
    python3-rover-bridge \
    python3-opencv 
    libcamera 
    libcamera-apps 
    libcamera-v4l2 
    v4l-utils 
    libudev 

    openssh \
    openssh-sftp-server \
"

# Habilitar login root sin contraseña para desarrollo
EXTRA_IMAGE_FEATURES += "debug-tweaks ssh-server-openssh"

# Mantenemos WiFi, pero eliminamos Gráficos y Bluetooth para ahorrar energía
DISTRO_FEATURES:append = " wifi"
DISTRO_FEATURES:remove = "x11 wayland vulkan opengl bluetooth"
