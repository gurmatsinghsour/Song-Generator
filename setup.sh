#!/bin/bash

echo "Setting up AI Song Generator Web App..."

if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not installed."
    echo "Please install Python 3 and try again."
    exit 1
fi

echo "Python 3 found"

if ! command -v pip &> /dev/null && ! command -v pip3 &> /dev/null; then
    echo "pip is required but not installed."
    echo "Please install pip and try again."
    exit 1
fi

echo "pip found"

echo "Installing dependencies..."
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "Dependencies installed successfully!"
else
    echo "Failed to install dependencies"
    echo "Please check your internet connection and try again"
    exit 1
fi

echo ""
echo "Creating required directories..."
mkdir -p generated_songs
mkdir -p templates
mkdir -p static/css
mkdir -p static/js

if [ ! -f .env ]; then
    echo ""
    echo "Creating .env template file..."
    cat > .env << EOF
GEMINI_API_KEY=your_gemini_api_key_here
SUNO_API_KEY=your_suno_api_key_here
EOF
    echo "Please edit .env and add your actual API keys"
    echo ""
    echo "You can get API keys from:"
    echo "- Gemini: https://ai.google.dev/"
    echo "- Suno: https://sunoapi.org/"
fi

echo ""
echo "Setup complete!"
echo "To start the application, run: python3 app.py"
