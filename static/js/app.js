let currentContentId = null;
let recentSongs = JSON.parse(localStorage.getItem('recentSongs') || '[]');

document.addEventListener('DOMContentLoaded', function() {
    console.log('AI Song Generator System Online');
    loadRecentSongs();
    checkApiStatus();
    
    document.getElementById('songForm').addEventListener('submit', function(e) {
        e.preventDefault();
        generateLyrics();
    });
});

async function generateLyrics() {
    const prompt = document.getElementById('prompt').value.trim();
    const genre = document.getElementById('genre').value;
    const mood = document.getElementById('mood').value;
    
    if (!prompt || !genre || !mood) {
        showToast('ERROR: All parameters required', 'warning');
        return;
    }
    
    showLoading(true);
    hideCards();
    
    try {
        const response = await fetch('/generate_lyrics', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                prompt: prompt,
                genre: genre,
                mood: mood
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentContentId = data.content_id;
            displayLyrics(data.lyrics);
            showToast('LYRICS GENERATION COMPLETE', 'success');
            
            addToRecentSongs({
                prompt: prompt,
                genre: genre,
                mood: mood,
                lyrics: data.lyrics.substring(0, 100) + '...',
                timestamp: new Date().toISOString()
            });
        } else {
            showToast('GENERATION FAILED: ' + data.error, 'error');
        }
    } catch (error) {
        console.error('Network Error:', error);
        showToast('NETWORK CONNECTION FAILED', 'error');
    } finally {
        showLoading(false);
    }
}

function displayLyrics(lyrics) {
    document.getElementById('generatedLyrics').textContent = lyrics;
    document.getElementById('lyricsCard').style.display = 'block';
    
    document.getElementById('lyricsCard').scrollIntoView({ 
        behavior: 'smooth',
        block: 'start'
    });
}

function approveLyrics() {
    if (!currentContentId) {
        showToast('NO DATA TO APPROVE', 'warning');
        return;
    }
    
    document.getElementById('songCard').style.display = 'block';
    showToast('LYRICS APPROVED - READY FOR SYNTHESIS', 'success');
    
    document.getElementById('songCard').scrollIntoView({ 
        behavior: 'smooth',
        block: 'start'
    });
}

function regenerateLyrics() {
    hideCards();
    generateLyrics();
}

async function saveLyrics() {
    if (!currentContentId) {
        showToast('NO DATA TO SAVE', 'warning');
        return;
    }
    
    try {
        const response = await fetch('/save_lyrics', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                content_id: currentContentId
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('DATA SAVED: ' + data.filename, 'success');
        } else {
            showToast('SAVE FAILED: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('SAVE OPERATION FAILED', 'error');
    }
}

async function generateSong() {
    if (!currentContentId) {
        showToast('NO APPROVED DATA FOUND', 'warning');
        return;
    }
    
    showLoading(true);
    
    try {
        const response = await fetch('/generate_song', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                content_id: currentContentId
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            displaySongPlayer(data.song_url);
            showToast('AUDIO SYNTHESIS COMPLETE', 'success');
        } else {
            showToast('SYNTHESIS FAILED: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('SYNTHESIS ERROR', 'error');
    } finally {
        showLoading(false);
    }
}

function displaySongPlayer(songUrl) {
    document.getElementById('songSource').src = songUrl;
    document.getElementById('songPlayer').style.display = 'block';
    
    const audio = document.querySelector('#songPlayer audio');
    audio.load();
}

async function checkApiStatus() {
    try {
        const response = await fetch('/api_status');
        const status = await response.json();
        
        let statusHtml = '<div class="row">';
        
        statusHtml += `
            <div class="col-md-6">
                <div class="d-flex align-items-center">
                    <i class="fas fa-brain me-2 ${status.gemini === 'configured' ? 'status-online' : 'status-offline'}"></i>
                    <span>GEMINI AI: </span>
                    <span class="ms-2 badge ${status.gemini === 'configured' ? 'bg-success' : 'bg-danger'}">
                        ${status.gemini === 'configured' ? 'ONLINE' : 'OFFLINE'}
                    </span>
                </div>
            </div>
        `;
        
        const sunoStatus = status.suno === 'configured' ? 
            (status.suno_connection === 'reachable' ? 'ONLINE' : 'CONNECTION ERROR') : 
            'OFFLINE';
        const sunoClass = status.suno === 'configured' && status.suno_connection === 'reachable' ? 
            'bg-success' : 'bg-danger';
        
        statusHtml += `
            <div class="col-md-6">
                <div class="d-flex align-items-center">
                    <i class="fas fa-music me-2 ${status.suno === 'configured' ? 'status-online' : 'status-offline'}"></i>
                    <span>SUNO API: </span>
                    <span class="ms-2 badge ${sunoClass}">
                        ${sunoStatus}
                    </span>
                </div>
            </div>
        `;
        
        statusHtml += '</div>';
        
        if (status.suno === 'configured') {
            statusHtml += `
                <div class="mt-3">
                    <button class="btn btn-sm btn-outline-primary" onclick="testSunoAPI()">
                        <i class="fas fa-vial"></i> TEST SUNO API
                    </button>
                </div>
            `;
        }
        
        if (status.gemini !== 'configured' || status.suno !== 'configured') {
            statusHtml += `
                <div class="alert alert-warning mt-3 mb-0">
                    <i class="fas fa-exclamation-triangle"></i>
                    <strong>CONFIGURATION REQUIRED:</strong> Check .env file
                </div>
            `;
        }
        
        document.getElementById('apiStatus').innerHTML = statusHtml;
        
    } catch (error) {
        document.getElementById('apiStatus').innerHTML = `
            <div class="alert alert-danger mb-0">
                <i class="fas fa-exclamation-circle"></i>
                STATUS CHECK FAILED
            </div>
        `;
    }
}

async function testSunoAPI() {
    showToast('TESTING SUNO API CONNECTION...', 'info');
    
    try {
        const response = await fetch('/test_suno', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('SUNO API TEST SUCCESSFUL', 'success');
        } else {
            showToast('SUNO API TEST FAILED: ' + (data.message || data.error), 'error');
        }
        
    } catch (error) {
        showToast('API TEST ERROR', 'error');
    }
}

function showLoading(show) {
    document.getElementById('loadingSpinner').style.display = show ? 'block' : 'none';
    document.getElementById('generateBtn').disabled = show;
    
    if (show) {
        document.getElementById('generateBtn').innerHTML = '<i class="fas fa-cog fa-spin"></i> PROCESSING...';
    } else {
        document.getElementById('generateBtn').innerHTML = '<i class="fas fa-play"></i> EXECUTE GENERATION';
    }
}

function hideCards() {
    document.getElementById('lyricsCard').style.display = 'none';
    document.getElementById('songCard').style.display = 'none';
}

function showToast(message, type = 'info') {
    const toastElement = document.getElementById('toastNotification');
    const toastMessage = document.getElementById('toastMessage');
    
    toastMessage.textContent = message;
    
    toastElement.classList.remove('bg-success', 'bg-danger', 'bg-warning', 'bg-info');
    
    switch(type) {
        case 'success':
            toastElement.classList.add('bg-success', 'text-white');
            break;
        case 'error':
            toastElement.classList.add('bg-danger', 'text-white');
            break;
        case 'warning':
            toastElement.classList.add('bg-warning', 'text-dark');
            break;
        default:
            toastElement.classList.add('bg-info', 'text-white');
    }
    
    const toast = new bootstrap.Toast(toastElement);
    toast.show();
}

function addToRecentSongs(song) {
    recentSongs.unshift(song);
    if (recentSongs.length > 10) {
        recentSongs = recentSongs.slice(0, 10);
    }
    localStorage.setItem('recentSongs', JSON.stringify(recentSongs));
    loadRecentSongs();
}

function loadRecentSongs() {
    const container = document.getElementById('recentSongs');
    
    if (recentSongs.length === 0) {
        container.innerHTML = '<p class="text-muted">No generation history available</p>';
        return;
    }
    
    let html = '';
    recentSongs.forEach((song, index) => {
        const date = new Date(song.timestamp).toLocaleDateString();
        html += `
            <div class="recent-song-item">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <h6 class="mb-1">${song.prompt}</h6>
                        <small class="text-muted">
                            <i class="fas fa-wave-square"></i> ${song.genre} • 
                            <i class="fas fa-microchip"></i> ${song.mood} • 
                            <i class="fas fa-calendar"></i> ${date}
                        </small>
                        <p class="mt-2 mb-0 small">${song.lyrics}</p>
                    </div>
                    <button class="btn btn-sm btn-outline-primary" onclick="regenerateFromHistory(${index})">
                        <i class="fas fa-sync"></i>
                    </button>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

function regenerateFromHistory(index) {
    const song = recentSongs[index];
    document.getElementById('prompt').value = song.prompt;
    document.getElementById('genre').value = song.genre;
    document.getElementById('mood').value = song.mood;
    
    document.getElementById('songForm').scrollIntoView({ 
        behavior: 'smooth',
        block: 'start'
    });
    
    showToast('PARAMETERS LOADED FROM HISTORY', 'info');
}

function downloadSong() {
    const songUrl = document.getElementById('songSource').src;
    if (songUrl && songUrl !== '') {
        const a = document.createElement('a');
        a.href = songUrl;
        a.download = `ai-generated-song-${Date.now()}.mp3`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        showToast('DOWNLOAD INITIATED', 'success');
    } else {
        showToast('NO AUDIO DATA AVAILABLE', 'warning');
    }
}

function shareSong() {
    const songUrl = document.getElementById('songSource').src;
    if (navigator.share && songUrl) {
        navigator.share({
            title: 'AI Generated Song',
            text: 'Generated with AI Song Generator',
            url: songUrl
        }).then(() => {
            showToast('SHARE SUCCESSFUL', 'success');
        }).catch(() => {
            copyToClipboard(songUrl);
        });
    } else {
        copyToClipboard(songUrl);
    }
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('URL COPIED TO CLIPBOARD', 'success');
    }).catch(() => {
        showToast('COPY OPERATION FAILED', 'error');
    });
}
