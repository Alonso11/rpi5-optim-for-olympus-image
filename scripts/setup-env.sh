#!/bin/bash
# --- OLYMPUS: PREPARACION DEL ENTORNO ---
set -e

ROOT_DIR=$(pwd)
LAYERS_DIR=$ROOT_DIR/layers

echo "--------------------------------------------------"
echo "Preparando entorno Olympus para RPi5..."
echo "--------------------------------------------------"

mkdir -p $LAYERS_DIR

# Función para clonar si no existe
clone_layer() {
    local url=$1
    local name=$2
    if [ ! -d "$LAYERS_DIR/$name" ]; then
        echo "Clonando $name..."
        git clone -b scarthgap $url "$LAYERS_DIR/$name"
    else
        echo "OK: $name ya existe."
    fi
}

clone_layer https://git.yoctoproject.org/git/poky poky
clone_layer https://git.yoctoproject.org/git/meta-raspberrypi meta-raspberrypi
clone_layer https://github.com/openembedded/meta-openembedded.git meta-openembedded

echo ""
echo "--------------------------------------------------"
echo "Entorno listo. Sigue estos pasos para compilar:"
echo "--------------------------------------------------"
echo "1. Cargar el entorno:"
echo "   source layers/poky/oe-init-build-env build"
echo ""
echo "2. Lanzar la compilación (Esto tomará tiempo):"
echo "   bitbake olympus-image"
echo "--------------------------------------------------"
