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
    model = genai.GenerativeModel('gemini-2.0-flash')
else:
    print("WARNING: GEMINI_API_KEY not found in environment variables")
    model = None

# File-based storage for content persistence across restarts
CONTENT_STORAGE_FILE = 'generated_content.json'

def load_generated_content():
    """Load content from file"""
    try:
        if os.path.exists(CONTENT_STORAGE_FILE):
            with open(CONTENT_STORAGE_FILE, 'r', encoding='utf-8') as f:
                content = json.load(f)
                return content
        else:
            print(f"Storage file {CONTENT_STORAGE_FILE} does not exist, starting with empty content")
    except Exception as e:
        print(f"Error loading content file: {e}")
    return {}

def save_generated_content(content_dict):
    """Save content to file"""
    try:
        with open(CONTENT_STORAGE_FILE, 'w', encoding='utf-8') as f:
            json.dump(content_dict, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving content file: {e}")

generated_content = load_generated_content()

def clean_lyrics(raw_text):
    """Clean up Gemini's output to extract just the lyrics"""
    lines = raw_text.split('\n')
    cleaned_lines = []
    
    # Skip introductory text and explanations
    start_processing = False
    
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines at the beginning
        if not stripped and not start_processing:
            continue
            
        # Skip explanatory text before the actual lyrics
        if any(phrase in stripped.lower() for phrase in [
            'here are', 'lyrics about', 'song lyrics', 'title:', '**title:', 
            'designed to be', 'okay,', 'sure,', 'i\'ll create'
        ]):
            continue
            
        # Start processing when we hit actual song structure
        if any(tag in stripped.lower() for tag in [
            '[verse', '[chorus', '[bridge', '[intro', '[outro'
        ]):
            start_processing = True
            
        if start_processing:
            # Remove markdown formatting
            cleaned = stripped.replace('**', '').replace('*', '')
            
            # Skip lines that are just explanations
            if not any(phrase in cleaned.lower() for phrase in [
                'this song', 'the lyrics', 'these lyrics'
            ]):
                cleaned_lines.append(cleaned)
    
    # Join and clean up extra whitespace
    result = '\n'.join(cleaned_lines)
    
    # Remove any remaining explanatory text at the end
    result = result.split('---')[0]  # Remove anything after separator
    
    # Clean up multiple newlines
    while '\n\n\n' in result:
        result = result.replace('\n\n\n', '\n\n')
    
    return result.strip()

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
        Create song lyrics only. No explanations, no titles, no descriptions.
        
        Specifications:
        - Theme: {prompt}
        - Genre: {genre}
        - Mood: {mood}
        
        Requirements:
        - Complete song structure: 2-3 verses, 2-3 choruses, 1 bridge
        - Radio-friendly and catchy
        - Use clear labels: [Verse 1], [Chorus], [Verse 2], [Bridge], [Outro]
        
        Output format: Start directly with [Verse 1] and provide only the lyrics.
        """
        
        response = model.generate_content(gemini_prompt)
        raw_lyrics = response.text
        
        # Clean up the lyrics - remove extra formatting and explanations
        lyrics = clean_lyrics(raw_lyrics)
        
        content_id = str(datetime.now().timestamp())
        generated_content[content_id] = {
            'lyrics': lyrics,
            'prompt': prompt,
            'genre': genre,
            'mood': mood,
            'timestamp': datetime.now().isoformat()
        }
        
        # Save to file for persistence
        save_generated_content(generated_content)
        
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
        # Reload content from file to ensure we have the latest data
        global generated_content
        generated_content = load_generated_content()
        
        data = request.json
        content_id = data.get('content_id')
        
        if not content_id:
            return jsonify({
                'success': False,
                'error': 'No content ID provided'
            })
        
        if content_id not in generated_content:
            return jsonify({
                'success': False,
                'error': f'Content not found for ID: {content_id}. Available IDs: {list(generated_content.keys())}'
            })
        
        content = generated_content[content_id]
        lyrics = content['lyrics']
        genre = content['genre']
        
        song_result = generate_audio_with_suno(lyrics, genre)
        
        if song_result:
            generated_content[content_id]['song_url'] = song_result
            save_generated_content(generated_content)  # Save to file
            
            # Check if it's a task ID (async) or actual URL
            if song_result.startswith("Task submitted:"):
                return jsonify({
                    'success': True,
                    'message': 'Song generation started! This may take a few minutes to complete.',
                    'task_info': song_result,
                    'note': 'Audio generation is asynchronous. The song will be ready shortly.'
                })
            else:
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
        title = title_line.replace('[', '').replace(']', '').strip()[:80]  # Max 80 chars
        if not title or title.isspace():
            title = "AI Generated Song"
        
        # Limit prompt to 3000 characters for V3_5 model
        prompt_text = lyrics[:3000] if len(lyrics) > 3000 else lyrics
        
        # Limit style to 200 characters for V3_5 model
        style_text = genre[:200] if len(genre) > 200 else genre
        
        payload = {
            "prompt": prompt_text,
            "style": style_text,
            "title": title,
            "customMode": True,
            "instrumental": False,  # We want vocals with lyrics
            "model": "V3_5",
            "negativeTags": "Heavy Metal, Noise" if genre.lower() != "rock" else "Quiet, Ambient",
            "callBackUrl": "https://api.example.com/callback"
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            
            # Check if the response has the expected structure
            if result.get('code') == 200:
                data = result.get('data')
                if data:
                    # The API returns taskId (camelCase) and the actual audio URLs come via callback
                    task_id = data.get('taskId') if isinstance(data, dict) else "pending"
                    return f"Task submitted: {task_id}"
                else:
                    return None
            else:
                return None
        else:
            return None
        
    except requests.exceptions.Timeout:
        return None
    except requests.exceptions.RequestException as e:
        return None
    except Exception as e:
        return None

@app.route('/song_status')
def song_status():
    """Show status of all songs"""
    current_content = load_generated_content()
    
    songs = []
    for content_id, content in current_content.items():
        song_url = content.get('song_url', '')
        
        if song_url.startswith('Task submitted:'):
            task_id = song_url.replace('Task submitted: ', '')
            if task_id and task_id != 'None':
                status = 'Processing'
                download_url = None
            else:
                status = 'Failed'
                download_url = None
        elif song_url.startswith('http'):
            status = 'Ready'
            download_url = song_url
        else:
            status = 'Pending'
            download_url = None
        
        songs.append({
            'content_id': content_id,
            'prompt': content.get('prompt', 'Unknown'),
            'genre': content.get('genre', 'Unknown'),
            'timestamp': content.get('timestamp', ''),
            'status': status,
            'download_url': download_url,
            'task_id': task_id if 'task_id' in locals() else None
        })
    
    return jsonify({
        'songs': songs,
        'total': len(songs),
        'note': 'Songs typically take 1-3 minutes to process. Refresh to check for updates.'
    })

@app.route('/check_song_status/<content_id>')
def check_song_status(content_id):
    """Check the status of a song generation task"""
    try:
        # Reload content from file
        current_content = load_generated_content()
        
        if content_id not in current_content:
            return jsonify({
                'success': False,
                'error': 'Content not found'
            })
        
        content = current_content[content_id]
        song_url = content.get('song_url', '')
        
        if not song_url or not song_url.startswith('Task submitted:'):
            return jsonify({
                'success': False,
                'error': 'No task found for this content'
            })
        
        # Extract task ID from the stored string
        task_id = song_url.replace('Task submitted: ', '')
        if task_id == 'None':
            return jsonify({
                'success': False,
                'error': 'Invalid task ID'
            })
        
        # Check status with Suno API
        status_url = f"https://api.sunoapi.org/api/v1/query?taskId={task_id}"
        headers = {
            "Authorization": f"Bearer {SUNO_API_KEY}",
            "Accept": "application/json"
        }
        
        response = requests.get(status_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('code') == 200:
                data = result.get('data')
                if data and isinstance(data, list) and len(data) > 0:
                    song_data = data[0]  # Get first song
                    status = song_data.get('status')
                    
                    if status == 'complete':
                        # Song is ready! Get the download URL
                        audio_url = song_data.get('audioUrl')
                        video_url = song_data.get('videoUrl') 
                        
                        if audio_url:
                            # Update the content with the actual download URL
                            current_content[content_id]['song_url'] = audio_url
                            current_content[content_id]['video_url'] = video_url
                            current_content[content_id]['status'] = 'complete'
                            save_generated_content(current_content)
                            
                            return jsonify({
                                'success': True,
                                'status': 'complete',
                                'audio_url': audio_url,
                                'video_url': video_url,
                                'message': 'Song is ready for download!'
                            })
                    
                    elif status in ['queued', 'running']:
                        return jsonify({
                            'success': True,
                            'status': status,
                            'message': f'Song is still {status}. Please check again in a moment.'
                        })
                    
                    else:
                        return jsonify({
                            'success': False,
                            'status': status,
                            'error': f'Song generation failed with status: {status}'
                        })
                
                return jsonify({
                    'success': False,
                    'error': 'No data in status response'
                })
            
            else:
                return jsonify({
                    'success': False,
                    'error': f'API error: {result.get("msg", "Unknown error")}'
                })
        
        else:
            return jsonify({
                'success': False,
                'error': f'Status check failed: {response.status_code}'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        })

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
    return jsonify(status)

if __name__ == '__main__':
    os.makedirs('generated_songs', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    
    print("Song Generator Web App")
    print(f"Gemini API: {'✓' if GEMINI_API_KEY else '✗'}")
    print(f"Suno API: {'✓' if SUNO_API_KEY else '✗'}")
    print("Server: http://localhost:5003")
    
    app.run(debug=True, host='0.0.0.0', port=5003)
