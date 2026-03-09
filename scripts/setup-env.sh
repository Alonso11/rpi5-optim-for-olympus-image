#!/bin/bash
# --- OLYMPUS: PREPARACION DEL ENTORNO ---

ROOT_DIR=\$(pwd)
LAYERS_DIR=\$ROOT_DIR/layers

echo "Clonando capas oficiales (Scarthgap)..."
mkdir -p \$LAYERS_DIR && cd \$LAYERS_DIR

git clone -b scarthgap https://git.yoctoproject.org/git/poky || true
git clone -b scarthgap https://git.yoctoproject.org/git/meta-raspberrypi || true
git clone -b scarthgap https://github.com/openembedded/meta-openembedded.git || true

cd \$ROOT_DIR
echo "Entorno listo. Ahora ejecuta:"
echo "source layers/poky/oe-init-build-env build"
echo "bitbake olympus-image"
