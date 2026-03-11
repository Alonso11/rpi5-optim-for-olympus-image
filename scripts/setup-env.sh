#!/bin/bash
# --- OLYMPUS: PREPARACION DEL ENTORNO ---
set -e

ROOT_DIR=$(pwd)
LAYERS_DIR=$ROOT_DIR/layers

echo "--------------------------------------------------"
echo "Preparando entorno Olympus para RPi5..."
echo "--------------------------------------------------"

mkdir -p $LAYERS_DIR

# Función para sincronizar capas (detectar, mover o clonar)
sync_layer() {
    local url=$1
    local name=$2
    
    # 1. Si la capa está en el directorio superior, moverla aquí
    if [ ! -d "$LAYERS_DIR/$name" ] && [ -d "$ROOT_DIR/../$name" ]; then
        echo "Detectada capa existente en el directorio superior. Moviendo $name..."
        mv "$ROOT_DIR/../$name" "$LAYERS_DIR/"
    fi

    # 2. Si no existe, clonar
    if [ ! -d "$LAYERS_DIR/$name" ]; then
        echo "Clonando $name..."
        git clone -b scarthgap $url "$LAYERS_DIR/$name"
    else
        # 3. Si existe, actualizar
        echo "Actualizando $name..."
        cd "$LAYERS_DIR/$name"
        git pull origin scarthgap
        cd "$ROOT_DIR"
    fi
}

sync_layer https://git.yoctoproject.org/git/poky poky
sync_layer https://git.yoctoproject.org/git/meta-raspberrypi meta-raspberrypi
sync_layer https://github.com/openembedded/meta-openembedded.git meta-openembedded

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
