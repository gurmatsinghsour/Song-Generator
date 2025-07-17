from flask import Flask, render_template, request, jsonify, send_file
import google.generativeai as genai
import requests
import os
import json
from datetime import datetime
import io
import base64
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
SUNO_API_KEY = os.getenv('SUNO_API_KEY')

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
else:
    print("WARNING: GEMINI_API_KEY not found in environment variables")
    model = None

generated_content = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_lyrics', methods=['POST'])
def generate_lyrics():
    try:
        if not GEMINI_API_KEY or not model:
            return jsonify({
                'success': False,
                'error': 'Gemini API key not configured. Please check your .env file.'
            })
        
        data = request.json
        prompt = data.get('prompt', '')
        genre = data.get('genre', 'pop')
        mood = data.get('mood', 'happy')
        
        gemini_prompt = f"""
        Generate song lyrics with the following specifications:
        - Theme/Topic: {prompt}
        - Genre: {genre}
        - Mood: {mood}
        
        Requirements:
        - Create a complete song with verse, chorus, and bridge
        - Make it catchy and memorable
        - Include proper song structure
        - Keep it appropriate and radio-friendly
        - Length: 2-3 verses, 2-3 choruses, 1 bridge
        
        Format the output clearly with labels like [Verse 1], [Chorus], [Verse 2], etc.
        """
        
        response = model.generate_content(gemini_prompt)
        lyrics = response.text
        
        content_id = str(datetime.now().timestamp())
        generated_content[content_id] = {
            'lyrics': lyrics,
            'prompt': prompt,
            'genre': genre,
            'mood': mood,
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify({
            'success': True,
            'lyrics': lyrics,
            'content_id': content_id
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/generate_song', methods=['POST'])
def generate_song():
    try:
        data = request.json
        content_id = data.get('content_id')
        
        if content_id not in generated_content:
            return jsonify({
                'success': False,
                'error': 'Content not found'
            })
        
        content = generated_content[content_id]
        lyrics = content['lyrics']
        genre = content['genre']
        
        print(f"Generating song for content_id: {content_id}")
        print(f"Genre: {genre}")
        print(f"Lyrics length: {len(lyrics)} characters")
        
        song_result = generate_audio_with_suno(lyrics, genre)
        
        if song_result:
            generated_content[content_id]['song_url'] = song_result
            
            return jsonify({
                'success': True,
                'song_url': song_result,
                'message': 'Song generated successfully!'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to generate audio. Please check your Suno API key and try again.'
            })
            
    except Exception as e:
        print(f"Error in generate_song: {e}")
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        })

def generate_audio_with_suno(lyrics, genre):
    try:
        url = "https://api.sunoapi.org/api/v1/generate"
        
        headers = {
            "Authorization": f"Bearer {SUNO_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        title_line = lyrics.split('\n')[0] if lyrics else "Generated Song"
        title = title_line.replace('[', '').replace(']', '').strip()[:50]
        
        payload = {
            "prompt": lyrics,
            "style": genre,
            "title": title,
            "customMode": True,
            "instrumental": False,
            "model": "V3_5",
            "negativeTags": "Heavy Metal, Noise" if genre != "rock" else "Quiet, Ambient"
        }
        
        print(f"Sending request to Suno API...")
        print(f"Title: {title}")
        print(f"Genre: {genre}")
        
        response = requests.post(url, headers=headers, json=payload)
        
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Suno API response: {result}")
            
            audio_url = (result.get('audio_url') or 
                        result.get('url') or 
                        result.get('song_url') or
                        result.get('download_url'))
            
            if audio_url:
                return audio_url
            else:
                print("No audio URL found in response")
                return None
        else:
            print(f"Suno API error: {response.status_code}")
            print(f"Error response: {response.text}")
            return None
        
    except Exception as e:
        print(f"Error generating audio: {e}")
        return None

@app.route('/save_lyrics', methods=['POST'])
def save_lyrics():
    try:
        data = request.json
        content_id = data.get('content_id')
        
        if content_id not in generated_content:
            return jsonify({
                'success': False,
                'error': 'Content not found'
            })
        
        content = generated_content[content_id]
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"lyrics_{timestamp}.txt"
        
        with open(f"generated_songs/{filename}", 'w', encoding='utf-8') as f:
            f.write(f"Song Generated: {content['timestamp']}\n")
            f.write(f"Prompt: {content['prompt']}\n")
            f.write(f"Genre: {content['genre']}\n")
            f.write(f"Mood: {content['mood']}\n")
            f.write("\n" + "="*50 + "\n\n")
            f.write(content['lyrics'])
        
        return jsonify({
            'success': True,
            'filename': filename,
            'message': 'Lyrics saved successfully!'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api_status')
def api_status():
    status = {
        'gemini': 'configured' if GEMINI_API_KEY else 'not configured',
        'suno': 'configured' if SUNO_API_KEY else 'not configured'
    }
    
    if status['suno'] == 'configured':
        try:
            response = requests.get("https://api.sunoapi.org", timeout=5)
            status['suno_connection'] = 'reachable' if response.status_code in [200, 404] else 'unreachable'
        except:
            status['suno_connection'] = 'unreachable'
    else:
        status['suno_connection'] = 'not configured'
    
    return jsonify(status)

@app.route('/test_suno', methods=['POST'])
def test_suno():
    try:
        test_lyrics = """[Verse 1]
This is a test song
Just to check if everything works
Simple melody and words
Testing the API connection

[Chorus]  
Test test test
Making sure it's working
Test test test
Everything is perfect"""

        result = generate_audio_with_suno(test_lyrics, "pop")
        
        if result:
            return jsonify({
                'success': True,
                'message': 'Suno API test successful!',
                'test_url': result
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Suno API test failed'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    os.makedirs('generated_songs', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    
    print("Song Generator Web App Starting...")
    print("Features:")
    print("  • Gemini AI lyrics generation")
    print("  • User approval system")
    print("  • Audio generation with Suno API")
    print("  • Clean web interface")
    print("\nAPI Status:")
    print(f"  • Gemini API: {'Configured' if GEMINI_API_KEY else 'Not configured'}")
    print(f"  • Suno API: {'Configured' if SUNO_API_KEY else 'Not configured'}")
    
    if not GEMINI_API_KEY or not SUNO_API_KEY:
        print("\nPlease check your .env file and ensure all API keys are set!")
    
    print("\nStarting Flask server...")
    print("Open your browser to: http://localhost:5000")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
