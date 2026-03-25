# Version: v1.0
# libpisp: Raspberry Pi PiSP (Pi Image Signal Processor) library.
# Required as build and runtime dependency by the libcamera rpi/pisp pipeline
# on RPi5. libcamera's subproject wrap specifies revision v1.3.0.

SUMMARY = "Raspberry Pi PiSP tuning and configuration library"
HOMEPAGE = "https://github.com/raspberrypi/libpisp"
LICENSE = "BSD-2-Clause"
LIC_FILES_CHKSUM = "file://LICENSE;md5=3417a46e992fdf62e5759fba9baef7a7"

inherit meson pkgconfig

SRC_URI = "git://github.com/raspberrypi/libpisp.git;protocol=https;branch=main"
SRCREV = "9ba67e6680f03f31f2b1741a53e8fd549be82cbe"
PV = "1.3.0"

S = "${WORKDIR}/git"

DEPENDS = "nlohmann-json boost"
