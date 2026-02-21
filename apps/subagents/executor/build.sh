#!/bin/bash
# Ubicación: apps/subagents/executor/build.sh

# 1. Limpiar builds previos
rm -rf package
rm -f executor.zip
mkdir package

# 2. Copiar el Handler (Nivel raíz del zip)
cp handler.py package/

# 3. Copiar la Librería Compartida (La magia de la Opción A)
# Creamos la carpeta destino para que Python pueda hacer: from src.neuro_agent import ...
mkdir -p package/src
# Copiamos SOLO el contenido de código, ignorando pycache
cp -r ../../../src/neuro_agent package/src/

# 4. Instalar dependencias LIGERAS específicas de esta Lambda
pip install -r requirements.txt -t package/ --no-cache-dir

# 5. Limpieza final (Reducir peso del ZIP)
# Eliminar __pycache__ y archivos innecesarios que pip a veces trae
find package -type d -name "__pycache__" -exec rm -rf {} +
find package -type d -name "tests" -exec rm -rf {} +
find package -type d -name "dist-info" -exec rm -rf {} +

# 6. Zippear
cd package
zip -r ../executor.zip .
cd ..

echo "✅ Lambda lista para subir: apps/subagents/executor/executor.zip"
