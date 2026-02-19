#!/bin/bash
echo "📦 Building Executor..."
rm -rf package
mkdir -p package

# 1. Copy Handler
cp handler.py package/lambda_function.py

# 2. Copy Shared Kernel (The Monorepo Trick)
mkdir -p package/src/shared
cp -r ../../../shared/* package/src/shared/
touch package/src/__init__.py

# 3. Deps
pip install -r requirements.txt -t package/

# 4. Zip
cd package
zip -r ../executor_lambda.zip .
