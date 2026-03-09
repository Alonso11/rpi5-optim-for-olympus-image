SUMMARY = "Imagen Olympus optimizada para RPi5 y bajo consumo"
LICENSE = "MIT"
inherit core-image
IMAGE_INSTALL:append = "     packagegroup-core-boot     kernel-modules     cpufrequtils     powertop     htop "
IMAGE_FEATURES:remove = "ssh-server-openssh"
