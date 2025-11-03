document.addEventListener('DOMContentLoaded', function() {
    const bgmIframe = document.getElementById('bgm-iframe');
    let iframeReady = false;
    let currentVolume = 0.5;
    let isMuted = false;

    // Function to send messages to the iframe
    function postMessageToIframe(command, value = null) {
        if (iframeReady && bgmIframe && bgmIframe.contentWindow) {
            bgmIframe.contentWindow.postMessage({ command: command, value: value }, '*'); // Specify targetOrigin in production
        }
    }

    // Listen for messages from the iframe
    window.addEventListener('message', function(event) {
        // Ensure the message is from a trusted origin if deployed
        // if (event.origin !== "http://your-domain.com") return;

        const message = event.data;

        if (message.command === 'iframeReady') {
            iframeReady = true;
            currentVolume = message.volume;
            isMuted = message.muted;
            console.log('BGM iframe is ready. Initial volume:', currentVolume, 'muted:', isMuted);

            // Initialize UI elements if they exist
            const toggleBgmBtn = document.getElementById('toggle-bgm-btn');
            const volumeSlider = document.getElementById('bgm-volume-slider');

            if (volumeSlider) {
                volumeSlider.value = currentVolume * 100;
            }
            if (toggleBgmBtn) {
                toggleBgmBtn.textContent = isMuted ? 'BGM OFF' : 'BGM ON';
            }

            // Autoplay policy workaround: try to play after user interaction
            // This might be triggered by the first user click on the page
            // For now, we'll rely on the iframe's internal autoplay attempt,
            // and user interaction will enable it if blocked.
            // We can add a specific 'play' command here if needed after user interaction.
            // Explicitly send play command to iframe, in case autoplay was blocked
            postMessageToIframe('play');
        } else if (message.command === 'muteStateChanged') {
            isMuted = message.value;
            const toggleBgmBtn = document.getElementById('toggle-bgm-btn');
            if (toggleBgmBtn) {
                toggleBgmBtn.textContent = isMuted ? 'BGM OFF' : 'BGM ON';
            }
        }
    });

    // --- UI Control Logic (similar to original bgm.js, but sending messages) ---
    const toggleBgmBtn = document.getElementById('toggle-bgm-btn');
    const volumeSlider = document.getElementById('bgm-volume-slider');

    if (toggleBgmBtn) {
        toggleBgmBtn.addEventListener('click', function() {
            postMessageToIframe('toggleMute');
        });
    }

    if (volumeSlider) {
        volumeSlider.addEventListener('input', function() {
            const newVolume = this.value / 100;
            postMessageToIframe('setVolume', newVolume);
        });
    }

    // Initial setup for UI elements based on localStorage (before iframe is ready)
    const savedVolume = localStorage.getItem('bgmVolume');
    if (volumeSlider && savedVolume !== null) {
        volumeSlider.value = parseFloat(savedVolume) * 100;
    } else if (volumeSlider) {
        volumeSlider.value = 50; // Default
    }

    const isBgmMuted = localStorage.getItem('isBgmMuted');
    if (toggleBgmBtn) {
        if (isBgmMuted === 'true') {
            toggleBgmBtn.textContent = 'BGM OFF';
        } else {
            toggleBgmBtn.textContent = 'BGM ON';
        }
    }
});