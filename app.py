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
            'timestamp': datetime.now().isoformat(),
            'status': 'lyrics_generated'
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
        
        # Update status to indicate generation started
        generated_content[content_id]['status'] = 'generating'
        save_generated_content(generated_content)
        
        song_result = generate_audio_with_suno(lyrics, genre, content_id)
        
        if song_result and song_result.get('success'):
            task_id = song_result.get('task_id')
            generated_content[content_id]['task_id'] = task_id
            generated_content[content_id]['status'] = 'submitted'
            save_generated_content(generated_content)
            
            return jsonify({
                'success': True,
                'task_id': task_id,
                'message': 'Song generation started! This may take a few minutes to complete.',
                'note': 'You will be notified when the song is ready for download.'
            })
        else:
            generated_content[content_id]['status'] = 'failed'
            save_generated_content(generated_content)
            return jsonify({
                'success': False,
                'error': 'Failed to generate audio. Please check your Suno API key and try again.'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        })

def generate_audio_with_suno(lyrics, genre, content_id):
    try:
        url = "https://api.sunoapi.org/api/v1/generate"
        
        headers = {
            "Authorization": f"Bearer {SUNO_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        title_line = lyrics.split('\n')[0] if lyrics else "Generated Song"
        title = title_line.replace('[', '').replace(']', '').strip()[:80]
        if not title or title.isspace():
            title = "AI Generated Song"
        
        # Limit prompt to 3000 characters for V3_5 model
        prompt_text = lyrics[:3000] if len(lyrics) > 3000 else lyrics
        
        # Limit style to 200 characters for V3_5 model
        style_text = genre[:200] if len(genre) > 200 else genre
        
        # Use your actual callback URL - you'll need to make this publicly accessible
        callback_url = f"https://33b81f980f7f.ngrok-free.app/suno_callback"  # Replace with your actual domain
        
        payload = {
            "prompt": prompt_text,
            "style": style_text,
            "title": title,
            "customMode": True,
            "instrumental": False,
            "model": "V3_5",
            "negativeTags": "Heavy Metal, Noise" if genre.lower() != "rock" else "Quiet, Ambient",
            "callBackUrl": callback_url
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('code') == 200:
                data = result.get('data')
                if data:
                    task_id = data.get('taskId') if isinstance(data, dict) else None
                    return {
                        'success': True,
                        'task_id': task_id
                    }
        
        return {'success': False}
        
    except Exception as e:
        print(f"Error generating audio: {e}")
        return {'success': False}

# NEW: Callback endpoint to receive notifications from Suno API
@app.route('/suno_callback', methods=['POST'])
def suno_callback():
    try:
        callback_data = request.json
        print(f"Received callback: {json.dumps(callback_data, indent=2)}")
        
        code = callback_data.get('code')
        msg = callback_data.get('msg')
        data = callback_data.get('data', {})
        
        task_id = data.get('task_id')
        callback_type = data.get('callbackType')
        
        if not task_id:
            return jsonify({'status': 'received'}), 200
        
        # Find the content with this task_id
        content_id = None
        for cid, content in generated_content.items():
            if content.get('task_id') == task_id:
                content_id = cid
                break
        
        if not content_id:
            print(f"No content found for task_id: {task_id}")
            return jsonify({'status': 'received'}), 200
        
        if code == 200 and callback_type == 'complete':
            # Task completed successfully
            music_data = data.get('data', [])
            if music_data:
                # Get the first generated track
                first_track = music_data[0]
                
                # Update the content with download URLs
                generated_content[content_id].update({
                    'status': 'completed',
                    'audio_url': first_track.get('audio_url'),
                    'source_audio_url': first_track.get('source_audio_url'),
                    'stream_audio_url': first_track.get('stream_audio_url'),
                    'image_url': first_track.get('image_url'),
                    'title': first_track.get('title'),
                    'tags': first_track.get('tags'),
                    'duration': first_track.get('duration'),
                    'completed_at': datetime.now().isoformat()
                })
                
                # Save all tracks if multiple were generated
                if len(music_data) > 1:
                    generated_content[content_id]['all_tracks'] = music_data
                
                save_generated_content(generated_content)
                print(f"Song completed for content_id: {content_id}")
        
        elif code != 200:
            # Task failed
            generated_content[content_id].update({
                'status': 'failed',
                'error_message': msg,
                'failed_at': datetime.now().isoformat()
            })
            save_generated_content(generated_content)
            print(f"Song generation failed for content_id: {content_id}, error: {msg}")
        
        return jsonify({'status': 'received'}), 200
        
    except Exception as e:
        print(f"Error processing callback: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/song_status')
def song_status():
    """Show status of all songs"""
    current_content = load_generated_content()
    
    songs = []
    for content_id, content in current_content.items():
        status = content.get('status', 'unknown')
        
        song_info = {
            'content_id': content_id,
            'prompt': content.get('prompt', 'Unknown'),
            'genre': content.get('genre', 'Unknown'),
            'timestamp': content.get('timestamp', ''),
            'status': status,
            'task_id': content.get('task_id'),
            'audio_url': content.get('audio_url'),
            'image_url': content.get('image_url'),
            'title': content.get('title'),
            'duration': content.get('duration')
        }
        
        songs.append(song_info)
    
    return jsonify({
        'songs': songs,
        'total': len(songs)
    })

@app.route('/download_song/<content_id>')
def download_song(content_id):
    """Download the generated song"""
    try:
        current_content = load_generated_content()
        
        if content_id not in current_content:
            return jsonify({
                'success': False,
                'error': 'Content not found'
            }), 404
        
        content = current_content[content_id]
        audio_url = content.get('audio_url')
        
        if not audio_url:
            return jsonify({
                'success': False,
                'error': 'No audio URL available. Song may not be ready yet.'
            }), 404
        
        # Download the file from Suno's servers
        response = requests.get(audio_url, timeout=30)
        
        if response.status_code == 200:
            # Create a filename
            title = content.get('title', 'generated_song')
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"{safe_title}.mp3"
            
            # Return the file as a download
            return send_file(
                io.BytesIO(response.content),
                as_attachment=True,
                download_name=filename,
                mimetype='audio/mpeg'
            )
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to download song from server'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Download error: {str(e)}'
        }), 500

@app.route('/check_song_status/<content_id>')
def check_song_status(content_id):
    """Check the status of a song generation task"""
    try:
        current_content = load_generated_content()
        
        if content_id not in current_content:
            return jsonify({
                'success': False,
                'error': 'Content not found'
            })
        
        content = current_content[content_id]
        status = content.get('status', 'unknown')
        
        response_data = {
            'success': True,
            'status': status,
            'content_id': content_id
        }
        
        if status == 'completed':
            response_data.update({
                'audio_url': content.get('audio_url'),
                'image_url': content.get('image_url'),
                'title': content.get('title'),
                'duration': content.get('duration'),
                'download_url': f'/download_song/{content_id}',
                'message': 'Song is ready for download!'
            })
        elif status == 'failed':
            response_data.update({
                'error_message': content.get('error_message', 'Unknown error'),
                'message': 'Song generation failed'
            })
        elif status in ['generating', 'submitted']:
            response_data['message'] = 'Song is still being generated. Please wait...'
        
        return jsonify(response_data)
            
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