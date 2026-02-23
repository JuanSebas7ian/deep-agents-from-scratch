#!/bin/bash
# Ubicación: apps/subagents/executor/build.sh

# 1. Limpiar builds previos
rm -rf package
rm -f executor.zip
mkdir package

# 2. Copiar el Handler (Nivel raíz del zip)
cp handler.py package/

# 3. Copiar la Librería Compartida (La magia de la Opción A)
# Copiamos SOLO el contenido de código, ignorando pycache, directo a la raíz del package
cp -r ../../../src/neuro_agent package/neuro_agent/

# 4. Instalar dependencias LIGERAS específicas de esta Lambda
pip install -r requirements.txt -t package/ --no-cache-dir

# 5. Limpieza final (Reducir peso del ZIP)
# Eliminar __pycache__ y archivos innecesarios que pip a veces trae
find package -type d -name "__pycache__" -exec rm -rf {} +
find package -type d -name "tests" -exec rm -rf {} +
find package -type d -name "*.dist-info" -exec rm -rf {} +

# 6. Zippear usando Python (ya que zip puede no estar instalado)
cd package
python3 -m zipfile -c ../executor.zip ./*
cd ..

echo "✅ Lambda lista para subir: apps/subagents/executor/executor.zip"

