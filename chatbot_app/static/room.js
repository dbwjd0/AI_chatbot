document.addEventListener('DOMContentLoaded', () => {
    const character = document.getElementById('character');
    const room = document.getElementById('room');
    const computer = document.getElementById('computer');
    const overlay = document.getElementById('fade-overlay');
    const step = 50; // 10px per move

    // Initial position
    let charX = 50;
    let charY = room.offsetHeight - 90 - 50; // character height - bottom offset
    character.style.left = `${charX}px`;
    character.style.top = `${charY}px`;

    computer.addEventListener('click', (event) => {
        event.preventDefault(); // Prevent immediate navigation
        overlay.classList.add('visible');

        setTimeout(() => {
            window.location.href = computer.href; // Navigate after fade
        }, 200); // Match the CSS transition duration
    });

    document.addEventListener('keydown', (event) => {
        const roomRect = room.getBoundingClientRect();
        const charRect = character.getBoundingClientRect();

        switch (event.key) {
            case 'ArrowUp':
                charY = Math.max(0, charY - step);
                break;
            case 'ArrowDown':
                charY = Math.min(roomRect.height - charRect.height, charY + step);
                break;
            case 'ArrowLeft':
                charX = Math.max(0, charX - step);
                break;
            case 'ArrowRight':
                charX = Math.min(roomRect.width - charRect.width, charX + step);
                break;
        }
        character.style.left = `${charX}px`;
        character.style.top = `${charY}px`;
    });
});