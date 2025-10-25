document.addEventListener('DOMContentLoaded', function() {
    const bgm = document.getElementById('bgm2'); // Assuming bgm2 for game pages
    const toggleBgmBtn = document.getElementById('toggle-bgm-btn');

    if (bgm && toggleBgmBtn) {
        // Check if BGM was previously unmuted
        const isBgmMuted = localStorage.getItem('isBgmMuted');
        if (isBgmMuted === 'false') {
            bgm.muted = false;
            toggleBgmBtn.textContent = 'BGM ON';
        } else {
            bgm.muted = true;
            toggleBgmBtn.textContent = 'BGM OFF';
        }

        toggleBgmBtn.addEventListener('click', function() {
            if (bgm.muted) {
                bgm.muted = false;
                toggleBgmBtn.textContent = 'BGM ON';
                localStorage.setItem('isBgmMuted', 'false');
            } else {
                bgm.muted = true;
                toggleBgmBtn.textContent = 'BGM OFF';
                localStorage.setItem('isBgmMuted', 'true');
            }
        });

        // Attempt to play the audio. This might fail due to browser policies,
        // but the user interaction with the button will allow it.
        bgm.play().catch(error => {
            console.log("BGM autoplay failed:", error);
            // Inform user that they might need to interact to play audio
        });
    }
});