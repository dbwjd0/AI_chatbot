// This script runs inside the iframe
document.addEventListener('DOMContentLoaded', function() {
    const bgm = document.getElementById('bgm_iframe_player');
    let currentVolume = 0.5; // Default volume
    let isMuted = false;

    // Load saved volume and mute state from localStorage
    const savedVolume = localStorage.getItem('bgmVolume');
    if (savedVolume !== null) {
        currentVolume = parseFloat(savedVolume);
    }
    bgm.volume = currentVolume;

    const savedMuteState = localStorage.getItem('isBgmMuted');
    if (savedMuteState === 'true') {
        isMuted = true;
    }
    bgm.muted = isMuted;

    // Attempt to play BGM
    // Autoplay policies might prevent this, so we'll rely on parent window to initiate play
    bgm.play().catch(error => {
        console.log("BGM autoplay in iframe failed:", error);
        // If autoplay fails, try to play when parent sends a 'play' message
    });

    // Listen for messages from the parent window
    window.addEventListener('message', function(event) {
        // Ensure the message is from a trusted origin if deployed
        // if (event.origin !== "http://your-domain.com") return;

        const message = event.data;

        switch (message.command) {
            case 'play':
                bgm.play().catch(error => console.log("Play command failed:", error));
                break;
            case 'pause':
                bgm.pause();
                break;
            case 'setVolume':
                if (typeof message.value === 'number' && message.value >= 0 && message.value <= 1) {
                    bgm.volume = message.value;
                    currentVolume = message.value;
                    localStorage.setItem('bgmVolume', currentVolume.toString());
                }
                break;
            case 'toggleMute':
                bgm.muted = !bgm.muted;
                isMuted = bgm.muted;
                localStorage.setItem('isBgmMuted', isMuted.toString());
                // Inform parent about the new mute state
                event.source.postMessage({ command: 'muteStateChanged', value: isMuted }, event.origin);
                break;
            case 'getVolume':
                event.source.postMessage({ command: 'volumeState', value: bgm.volume }, event.origin);
                break;
            case 'getMuteState':
                event.source.postMessage({ command: 'muteState', value: bgm.muted }, event.origin);
                break;
            case 'loadTrack':
                if (message.value) {
                    bgm.src = message.value;
                    bgm.load();
                    bgm.play().catch(error => console.log("Load track and play failed:", error));
                }
                break;
        }
    });

    // Inform parent window that iframe is ready and current state
    window.parent.postMessage({
        command: 'iframeReady',
        volume: bgm.volume,
        muted: bgm.muted,
        isPlaying: !bgm.paused
    }, '*'); // Use specific origin in production
});