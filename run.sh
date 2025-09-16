
echo "============================================"
echo "Creating virtual environment..."
python -m venv venv
echo "============================================"


echo "============================================"
echo "Activating virtual environment..."
source venv/bin/activate.fish
echo "============================================"

echo "============================================"
echo "Installing dependencies..."
pip install flask
echo "============================================"

echo "============================================"
echo "Starting Flask application..."

echo "Application started successfully!"
echo "Press Ctrl+C to stop the application."

python app.py
echo "============================================"
