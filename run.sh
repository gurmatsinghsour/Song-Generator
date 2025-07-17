#!/bin/bash

echo "AI Song Generator - Setup & Launch"
echo "====================================="

if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not installed."
    echo "Please install Python 3 and try again."
    exit 1
fi

echo "Python 3 found: $(python3 --version)"

echo ""
echo "Installing dependencies..."
pip3 install flask google-generativeai requests python-dotenv

if [ $? -ne 0 ]; then
    echo "Failed to install dependencies"
    echo "Try running: pip3 install --user flask google-generativeai requests python-dotenv"
    exit 1
fi

echo "Dependencies installed successfully"

if [ ! -f .env ]; then
    echo ""
    echo "WARNING: .env file not found!"
    echo "Please create a .env file with your API keys:"
    echo ""
    echo "GEMINI_API_KEY=your_gemini_api_key_here"
    echo "SUNO_API_KEY=your_suno_api_key_here"
    echo ""
    echo "You can get API keys from:"
    echo "- Gemini: https://ai.google.dev/"
    echo "- Suno: https://sunoapi.org/"
    echo ""
fi

echo ""
echo "Starting AI Song Generator..."
echo "Open your browser to: http://localhost:5000"
echo ""

python3 app.py
