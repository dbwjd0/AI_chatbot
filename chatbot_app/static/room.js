document.addEventListener('DOMContentLoaded', () => {
    const movableCharacter = document.getElementById('movable-character');
    const room = document.getElementById('room');
    const computer = document.getElementById('computer');
    const overlay = document.getElementById('fade-overlay');
    const step = 10; // 10px per move (changed from 50 for smoother movement)

    // Initial position - get from CSS or set explicitly
    // Using getComputedStyle to read initial CSS values
    let charX = parseFloat(getComputedStyle(movableCharacter).left);
    let charY = parseFloat(getComputedStyle(movableCharacter).top);

    // Fallback if CSS values are not set or are 'auto'
    if (isNaN(charX)) charX = 50;
    if (isNaN(charY)) charY = room.offsetHeight - movableCharacter.offsetHeight - 50; // Default bottom position

    movableCharacter.style.left = `${charX}px`;
    movableCharacter.style.top = `${charY}px`;

    computer.addEventListener('click', (event) => {
        event.preventDefault(); // Prevent immediate navigation
        overlay.classList.add('visible');

        setTimeout(() => {
            window.location.href = computer.href; // Navigate after fade
        }, 200); // Match the CSS transition duration
    });

    document.addEventListener('keydown', (event) => {
        const roomRect = room.getBoundingClientRect();
        const charRect = movableCharacter.getBoundingClientRect(); // Use movableCharacter

        let newCharX = charX;
        let newCharY = charY;

        switch (event.key) {
            case 'ArrowUp':
                newCharY = Math.max(0, charY - step);
                break;
            case 'ArrowDown':
                newCharY = Math.min(roomRect.height - charRect.height, charY + step);
                break;
            case 'ArrowLeft':
                newCharX = Math.max(0, charX - step);
                break;
            case 'ArrowRight':
                newCharX = Math.min(roomRect.width - charRect.width, charX + step);
                break;
            default:
                return; // Do nothing for other keys
        }

        // Only update if position changed to avoid unnecessary DOM manipulation
        if (newCharX !== charX || newCharY !== charY) {
            charX = newCharX;
            charY = newCharY;
            movableCharacter.style.left = `${charX}px`;
            movableCharacter.style.top = `${charY}px`;
        }
        event.preventDefault(); // Prevent default scroll behavior for arrow keys
    });
});