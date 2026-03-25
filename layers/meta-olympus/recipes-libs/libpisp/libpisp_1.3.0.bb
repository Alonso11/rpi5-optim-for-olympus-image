# Version: v1.0
# libpisp: Raspberry Pi PiSP (Pi Image Signal Processor) library.
# Required as build and runtime dependency by the libcamera rpi/pisp pipeline
# on RPi5. libcamera's subproject wrap specifies revision v1.3.0.

SUMMARY = "Raspberry Pi PiSP tuning and configuration library"
HOMEPAGE = "https://github.com/raspberrypi/libpisp"
LICENSE = "BSD-2-Clause"
LIC_FILES_CHKSUM = "file://LICENSE;md5=f836cc7e4b4a83f710b5ee83f36d45da"

inherit meson pkgconfig

SRC_URI = "git://github.com/raspberrypi/libpisp.git;protocol=https;branch=main"
SRCREV = "${AUTOREV}"
PV = "1.3.0+git${SRCPV}"

S = "${WORKDIR}/git"

DEPENDS = "nlohmann-json boost"
