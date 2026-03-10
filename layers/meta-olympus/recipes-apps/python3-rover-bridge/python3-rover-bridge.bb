SUMMARY = "Extensión nativa de Python en Rust para control de Rover (Olympus Bridge)"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://rover-bridge/"

S = "${WORKDIR}/rover-bridge"

inherit cargo python3-dir

# Dependencias para compilar la extensión nativa
DEPENDS += "python3 python3-setuptools-native"
RDEPENDS:${PN} += "python3-core"

# Forzamos la instalación de la librería dinámica (.so) en el directorio de paquetes de Python
do_install() {
    install -d ${D}${PYTHON_SITEPACKAGES_DIR}
    # Buscamos el archivo .so generado por Cargo y lo movemos a site-packages
    install -m 0755 ${B}/target/${CARGO_TARGET_SUBDIR}/librover_bridge.so ${D}${PYTHON_SITEPACKAGES_DIR}/rover_bridge.so
}

FILES:${PN} += "${PYTHON_SITEPACKAGES_DIR}/rover_bridge.so"
