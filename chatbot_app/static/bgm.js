document.addEventListener('DOMContentLoaded', function() {
    const bgm = document.getElementById('bgm2'); // Assuming bgm2 for game pages
    const toggleBgmBtn = document.getElementById('toggle-bgm-btn');
    const volumeSlider = document.getElementById('bgm-volume-slider');

    console.log('BGM element:', bgm);
    console.log('Toggle BGM Button:', toggleBgmBtn);
    console.log('Volume Slider:', volumeSlider);

    if (bgm && toggleBgmBtn && volumeSlider) {
        // --- Volume Control ---
        const savedVolume = localStorage.getItem('bgmVolume');
        if (savedVolume !== null) {
            bgm.volume = savedVolume;
            volumeSlider.value = savedVolume * 100;
        } else {
            bgm.volume = 0.5; // Default volume
            volumeSlider.value = 50;
        }

        volumeSlider.addEventListener('input', function() {
            const newVolume = this.value / 100;
            bgm.volume = newVolume;
            localStorage.setItem('bgmVolume', newVolume);
        });

        // --- Mute Toggle ---
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

        // --- Autoplay and Time Saving ---
        const savedTime = localStorage.getItem('bgmCurrentTime');
        if (savedTime) {
            bgm.currentTime = parseFloat(savedTime);
            localStorage.removeItem('bgmCurrentTime'); // Clear after use
        }

        bgm.play().catch(error => {
            console.log("BGM autoplay failed:", error);
        });

        window.addEventListener('beforeunload', () => {
            if (!bgm.muted) {
                localStorage.setItem('bgmCurrentTime', bgm.currentTime.toString());
            }
        });
    }
});