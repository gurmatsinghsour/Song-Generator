let currentContentId = null;
let recentSongs = JSON.parse(localStorage.getItem('recentSongs') || '[]');
let statusCheckInterval = null;

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
                content_id: data.content_id,
                prompt: prompt,
                genre: genre,
                mood: mood,
                lyrics: data.lyrics.substring(0, 100) + '...',
                timestamp: new Date().toISOString(),
                status: 'lyrics_generated'
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
    
    showLoading(true, 'INITIATING AUDIO SYNTHESIS...');
    
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
            showToast('SYNTHESIS INITIATED - TASK ID: ' + data.task_id, 'success');
            showSongProgress();
            
            // Update recent songs with task info
            updateRecentSongStatus(currentContentId, 'generating', data.task_id);
            
            // Start monitoring the song status
            startStatusMonitoring();
        } else {
            showToast('SYNTHESIS FAILED: ' + data.error, 'error');
        }
    } catch (error) {
        showToast('SYNTHESIS ERROR', 'error');
    } finally {
        showLoading(false);
    }
}

function showSongProgress() {
    const progressHtml = `
        <div id="songProgress" class="mt-3">
            <div class="d-flex align-items-center mb-2">
                <div class="spinner-border spinner-border-sm text-warning me-2" role="status"></div>
                <span class="terminal-text">PROCESSING AUDIO...</span>
            </div>
            <div class="progress">
                <div class="progress-bar progress-bar-striped progress-bar-animated bg-warning" 
                     role="progressbar" style="width: 100%"></div>
            </div>
            <small class="text-muted mt-1 d-block">This typically takes 1-3 minutes</small>
        </div>
    `;
    
    document.querySelector('#songCard .card-body').insertAdjacentHTML('beforeend', progressHtml);
}

function startStatusMonitoring() {
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
    }
    
    statusCheckInterval = setInterval(async () => {
        await checkSongStatus();
    }, 10000); // Check every 10 seconds
    
    // Also check immediately
    setTimeout(checkSongStatus, 2000);
}

async function checkSongStatus() {
    if (!currentContentId) return;
    
    try {
        const response = await fetch(`/check_song_status/${currentContentId}`);
        const data = await response.json();
        
        if (data.success) {
            if (data.status === 'completed') {
                // Song is ready!
                clearInterval(statusCheckInterval);
                statusCheckInterval = null;
                
                displayCompletedSong(data);
                showToast('AUDIO SYNTHESIS COMPLETE!', 'success');
                
                // Update recent songs
                updateRecentSongStatus(currentContentId, 'completed', null, data.audio_url);
                
            } else if (data.status === 'failed') {
                clearInterval(statusCheckInterval);
                statusCheckInterval = null;
                
                showToast('SYNTHESIS FAILED: ' + (data.error_message || 'Unknown error'), 'error');
                updateRecentSongStatus(currentContentId, 'failed');
                
                // Remove progress indicator
                const progressElement = document.getElementById('songProgress');
                if (progressElement) {
                    progressElement.remove();
                }
            }
            // For 'generating' or 'submitted' status, keep waiting
        }
    } catch (error) {
        console.error('Status check error:', error);
    }
}

function displayCompletedSong(data) {
    // Remove progress indicator
    const progressElement = document.getElementById('songProgress');
    if (progressElement) {
        progressElement.remove();
    }
    
    // Display player with download options
    const playerHtml = `
        <div id="songPlayer" class="mt-4">
            <h6 class="terminal-text">AUDIO OUTPUT COMPLETE:</h6>
            <div class="song-info mb-3">
                <div class="row">
                    <div class="col-md-8">
                        <strong>${data.title || 'Generated Song'}</strong><br>
                        <small class="text-muted">Duration: ${data.duration ? Math.round(data.duration) + 's' : 'Unknown'}</small>
                    </div>
                    <div class="col-md-4 text-end">
                        ${data.image_url ? `<img src="${data.image_url}" alt="Cover" style="width: 60px; height: 60px; object-fit: cover; border-radius: 4px;">` : ''}
                    </div>
                </div>
            </div>
            <audio controls class="w-100 mb-3">
                <source src="${data.audio_url}" type="audio/mpeg">
                Your browser does not support the audio element.
            </audio>
            <div class="btn-group w-100" role="group">
                <button class="btn btn-success" onclick="downloadSongDirect('${currentContentId}')">
                    <i class="fas fa-download"></i> DOWNLOAD MP3
                </button>
                <button class="btn btn-info" onclick="copySongUrl('${data.audio_url}')">
                    <i class="fas fa-link"></i> COPY URL
                </button>
                <button class="btn btn-warning" onclick="shareSong('${data.audio_url}')">
                    <i class="fas fa-share-alt"></i> SHARE
                </button>
            </div>
        </div>
    `;
    
    // Remove any existing player
    const existingPlayer = document.getElementById('songPlayer');
    if (existingPlayer) {
        existingPlayer.remove();
    }
    
    document.querySelector('#songCard .card-body').insertAdjacentHTML('beforeend', playerHtml);
}

async function downloadSongDirect(contentId) {
    try {
        showToast('INITIATING DOWNLOAD...', 'info');
        
        // Create a temporary link to trigger download
        const link = document.createElement('a');
        link.href = `/download_song/${contentId}`;
        link.download = ''; // Let the server set the filename
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        showToast('DOWNLOAD STARTED', 'success');
    } catch (error) {
        showToast('DOWNLOAD FAILED', 'error');
    }
}

function copySongUrl(url) {
    navigator.clipboard.writeText(url).then(() => {
        showToast('URL COPIED TO CLIPBOARD', 'success');
    }).catch(() => {
        showToast('COPY OPERATION FAILED', 'error');
    });
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
        
        statusHtml += `
            <div class="col-md-6">
                <div class="d-flex align-items-center">
                    <i class="fas fa-music me-2 ${status.suno === 'configured' ? 'status-online' : 'status-offline'}"></i>
                    <span>SUNO API: </span>
                    <span class="ms-2 badge ${status.suno === 'configured' ? 'bg-success' : 'bg-danger'}">
                        ${status.suno === 'configured' ? 'ONLINE' : 'OFFLINE'}
                    </span>
                </div>
            </div>
        `;
        
        statusHtml += '</div>';
        
        if (status.gemini !== 'configured' || status.suno !== 'configured') {
            statusHtml += `
                <div class="alert alert-warning mt-3 mb-0">
                    <i class="fas fa-exclamation-triangle"></i>
                    <strong>CONFIGURATION REQUIRED:</strong> Check .env file
                </div>
            `;
        }
        
        // Add song status overview
        statusHtml += await getSongStatusOverview();
        
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

async function getSongStatusOverview() {
    try {
        const response = await fetch('/song_status');
        const data = await response.json();
        
        if (data.songs && data.songs.length > 0) {
            const processing = data.songs.filter(s => ['generating', 'submitted'].includes(s.status)).length;
            const completed = data.songs.filter(s => s.status === 'completed').length;
            const failed = data.songs.filter(s => s.status === 'failed').length;
            
            return `
                <div class="mt-3 pt-3 border-top">
                    <h6 class="text-muted mb-2">GENERATION QUEUE:</h6>
                    <div class="row text-center">
                        <div class="col-4">
                            <div class="badge bg-warning">${processing}</div>
                            <small class="d-block text-muted">Processing</small>
                        </div>
                        <div class="col-4">
                            <div class="badge bg-success">${completed}</div>
                            <small class="d-block text-muted">Completed</small>
                        </div>
                        <div class="col-4">
                            <div class="badge bg-danger">${failed}</div>
                            <small class="d-block text-muted">Failed</small>
                        </div>
                    </div>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error getting song status overview:', error);
    }
    
    return '';
}

function showLoading(show, message = 'PROCESSING...') {
    document.getElementById('loadingSpinner').style.display = show ? 'block' : 'none';
    document.getElementById('generateBtn').disabled = show;
    
    if (show) {
        document.getElementById('generateBtn').innerHTML = '<i class="fas fa-cog fa-spin"></i> ' + message;
    } else {
        document.getElementById('generateBtn').innerHTML = '<i class="fas fa-play"></i> EXECUTE GENERATION';
    }
}

function hideCards() {
    document.getElementById('lyricsCard').style.display = 'none';
    document.getElementById('songCard').style.display = 'none';
    
    // Clear any status monitoring
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
        statusCheckInterval = null;
    }
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

function updateRecentSongStatus(contentId, status, taskId = null, audioUrl = null) {
    const songIndex = recentSongs.findIndex(song => song.content_id === contentId);
    if (songIndex !== -1) {
        recentSongs[songIndex].status = status;
        if (taskId) recentSongs[songIndex].task_id = taskId;
        if (audioUrl) recentSongs[songIndex].audio_url = audioUrl;
        localStorage.setItem('recentSongs', JSON.stringify(recentSongs));
        loadRecentSongs();
    }
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
        const statusBadge = getStatusBadge(song.status);
        
        html += `
            <div class="recent-song-item">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <div class="d-flex align-items-center mb-1">
                            <h6 class="mb-0 me-2">${song.prompt}</h6>
                            ${statusBadge}
                        </div>
                        <small class="text-muted">
                            <i class="fas fa-wave-square"></i> ${song.genre} • 
                            <i class="fas fa-microchip"></i> ${song.mood} • 
                            <i class="fas fa-calendar"></i> ${date}
                        </small>
                        <p class="mt-2 mb-0 small">${song.lyrics}</p>
                        ${song.status === 'completed' && song.audio_url ? `
                            <div class="mt-2">
                                <button class="btn btn-sm btn-success" onclick="downloadSongDirect('${song.content_id}')">
                                    <i class="fas fa-download"></i> Download
                                </button>
                            </div>
                        ` : ''}
                    </div>
                    <div class="ms-2">
                        <button class="btn btn-sm btn-outline-primary" onclick="regenerateFromHistory(${index})">
                            <i class="fas fa-sync"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

function getStatusBadge(status) {
    const badges = {
        'lyrics_generated': '<span class="badge bg-info">Lyrics Ready</span>',
        'generating': '<span class="badge bg-warning">Processing</span>',
        'submitted': '<span class="badge bg-warning">Queued</span>',
        'completed': '<span class="badge bg-success">Ready</span>',
        'failed': '<span class="badge bg-danger">Failed</span>'
    };
    
    return badges[status] || '<span class="badge bg-secondary">Unknown</span>';
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

function shareSong(songUrl) {
    if (navigator.share && songUrl) {
        navigator.share({
            title: 'AI Generated Song',
            text: 'Generated with AI Song Generator',
            url: songUrl
        }).then(() => {
            showToast('SHARE SUCCESSFUL', 'success');
        }).catch(() => {
            copySongUrl(songUrl);
        });
    } else {
        copySongUrl(songUrl);
    }
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
    }
});