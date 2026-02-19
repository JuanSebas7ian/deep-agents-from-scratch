#!/bin/bash
set -e

cd /home/juansebas7ian/deep-agents-from-scratch/neuro_agent

mkdir -p domain
mkdir -p infrastructure/memory
mkdir -p infrastructure/tools
mkdir -p apps/supervisor
mkdir -p apps/subagents
touch infrastructure/__init__.py
touch apps/__init__.py

mv src/shared/config.py domain/
mv src/shared/registry.py domain/
mv src/shared/state.py domain/
mv src/shared/__init__.py domain/

mv src/shared/dynamo_checkpointer.py infrastructure/memory/
touch infrastructure/memory/__init__.py

mv src/shared/tools/* infrastructure/tools/

mv src/supervisor/* apps/supervisor/
mv src/subagents/* apps/subagents/

rm -rf src/shared
rm -rf src/supervisor
rm -rf src/subagents
rm -rf src

cd ..

# Find all python files and notebooks
find neuro_agent scripts notebooks tests -type f \( -name "*.py" -o -name "*.ipynb" \) -exec sed -i 's/src\.shared\.tools/infrastructure.tools/g' {} +
find neuro_agent scripts notebooks tests -type f \( -name "*.py" -o -name "*.ipynb" \) -exec sed -i 's/src\.shared\.dynamo_checkpointer/infrastructure.memory.dynamo_checkpointer/g' {} +
find neuro_agent scripts notebooks tests -type f \( -name "*.py" -o -name "*.ipynb" \) -exec sed -i 's/src\.shared/domain/g' {} +
find neuro_agent scripts notebooks tests -type f \( -name "*.py" -o -name "*.ipynb" \) -exec sed -i 's/src\.supervisor/apps.supervisor/g' {} +
find neuro_agent scripts notebooks tests -type f \( -name "*.py" -o -name "*.ipynb" \) -exec sed -i 's/src\.subagents/apps.subagents/g' {} +

# Update lambda_executor because it uses neuro_agent root?
find neuro_agent scripts notebooks tests -type f \( -name "*.py" -o -name "*.ipynb" \) -exec sed -i 's/from src\.shared\.tools\.database/from infrastructure.tools.database/g' {} +

echo "Done!"
