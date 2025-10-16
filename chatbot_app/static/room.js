document.addEventListener('DOMContentLoaded', () => {
    const character = document.getElementById('character');
    const room = document.getElementById('room');
    const computer = document.getElementById('computer');
    const overlay = document.getElementById('fade-overlay');
    const step = 10;

    let charX = parseFloat(getComputedStyle(character).left);
    let charY = parseFloat(getComputedStyle(character).top);

    if (isNaN(charX)) charX = 50;
    if (isNaN(charY)) charY = room.offsetHeight - character.offsetHeight - 50;

    character.style.left = `${charX}px`;
    character.style.top = `${charY}px`;

    computer.addEventListener('click', (event) => {
        event.preventDefault();
        overlay.classList.add('visible');
        setTimeout(() => {
            window.location.href = computer.href;
        }, 200);
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
            default:
                return;
        }

        character.style.left = `${charX}px`;
        character.style.top = `${charY}px`;
        
        event.preventDefault();
    });
});
