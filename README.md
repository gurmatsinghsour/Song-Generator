# AI Song Generator

A web application that generates song lyrics using Google's Gemini AI and converts them into actual songs using the Suno API.

## Features

- Generate lyrics based on custom prompts, genres, and moods
- User approval system for generated lyrics
- Convert approved lyrics into full songs with music
- Clean cyberpunk-themed web interface
- Save lyrics to text files
- Recent songs history with localStorage

## Requirements

- Python 3.8+
- Flask
- Google Generative AI SDK
- Requests
- Python-dotenv

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Song-Generator
```

2. Run the setup script:
```bash
./setup.sh
```

3. Configure your API keys in `.env`:
```
GEMINI_API_KEY=your_gemini_api_key_here
SUNO_API_KEY=your_suno_api_key_here
```

## API Keys

- **Gemini API**: Get your key from [Google AI Studio](https://ai.google.dev/)
- **Suno API**: Get your key from [Suno API](https://sunoapi.org/)

## Usage

1. Start the application:
```bash
python3 app.py
```

2. Open your browser to `http://localhost:5000`

3. Enter a song concept, select genre and mood

4. Generate lyrics and approve them

5. Create the full song with music

## Project Structure

```
Song-Generator/
├── app.py              # Main Flask application
├── templates/
│   └── index.html      # Web interface
├── static/
│   ├── css/
│   │   └── style.css   # Cyberpunk styling
│   └── js/
│       └── app.js      # Frontend JavaScript
├── generated_songs/    # Saved lyrics directory
├── requirements.txt    # Python dependencies
├── setup.sh           # Setup script
├── run.sh             # Run script
└── .env               # API keys (create this)
```

## API Endpoints

- `GET /` - Main web interface
- `POST /generate_lyrics` - Generate lyrics with Gemini AI
- `POST /generate_song` - Create song with Suno API
- `POST /save_lyrics` - Save lyrics to file
- `GET /api_status` - Check API configuration status
- `POST /test_suno` - Test Suno API connection

## Development

The application uses Flask for the backend and vanilla JavaScript for the frontend. The cyberpunk theme is implemented with CSS custom properties and terminal-style fonts.

## License

MIT License
