SUMMARY = "Extensión nativa de Python en Rust para control de Rover (Olympus Bridge)"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://rover-bridge/ \
           file://test_rover.py \
           file://test_bridge.py"

# El código está en la subcarpeta rover-bridge
S = "${WORKDIR}/rover-bridge"

inherit cargo python3native python3-dir pkgconfig

# Dependencias para compilar la extensión nativa (necesita udev para serialport)
DEPENDS += "python3 python3-setuptools-native udev"
RDEPENDS:${PN} += "python3-core python3-pyserial udev"

# Configuración para usar las fuentes vendoreadas incluidas en el repo
do_configure:prepend() {
    # Bitbake's cargo class expects offline crates in this specific directory
    mkdir -p ${WORKDIR}/cargo_home/bitbake
    # Symlink all vendored crates to where Bitbake expects them
    if [ -d "${S}/vendor" ]; then
        ln -sf ${S}/vendor/* ${WORKDIR}/cargo_home/bitbake/
    fi
}

# Forzamos a Cargo a trabajar offline
export CARGO_OFFLINE = "1"

# Variables para compilación cruzada de PyO3
export PYO3_CROSS = "1"
export PYO3_CROSS_PYTHON_VERSION = "3.12"
export PYO3_CROSS_LIB_DIR = "${STAGING_LIBDIR}"
export PYO3_CONFIG_INTERPRETER = "${PYTHON}"

# Forzamos la instalación de la librería dinámica (.so) en el directorio de paquetes de Python
do_install() {
    install -d ${D}${PYTHON_SITEPACKAGES_DIR}
    # Buscamos el archivo .so generado por Cargo y lo movemos a site-packages
    install -m 0755 ${B}/target/${CARGO_TARGET_SUBDIR}/librover_bridge.so ${D}${PYTHON_SITEPACKAGES_DIR}/rover_bridge.so

    # Instalamos los scripts de prueba en /usr/bin de la RPi
    install -d ${D}${bindir}
    install -m 0755 ${WORKDIR}/test_rover.py ${D}${bindir}/test_rover.py
    install -m 0755 ${WORKDIR}/test_bridge.py ${D}${bindir}/test_bridge.py
}

FILES:${PN} += "${PYTHON_SITEPACKAGES_DIR}/rover_bridge.so ${bindir}/test_rover.py ${bindir}/test_bridge.py"
