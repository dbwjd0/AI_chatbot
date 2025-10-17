document.addEventListener('DOMContentLoaded', () => {
    // --- Game Elements ---
    const room = document.getElementById('room');
    const player = document.getElementById('player');
    const playerImage = player.querySelector('img'); // Get the img element
    const objects = document.querySelectorAll('.interactive-object');
    const interactionPrompt = document.getElementById('interaction-prompt');
    const fadeOverlay = document.getElementById('fade-overlay');
    const dialogBox = document.getElementById('dialog-box');
    const dialogSpeaker = document.getElementById('dialog-speaker');
    const dialogText = document.getElementById('dialog-text');

    // --- Image Paths ---
    const idleImg = '/static/img/char_idle.png';
    const walkFrontGif = '/static/img/walk_front.gif';
    const walkUpImg = '/static/img/walk_side_up.gif';
    const walkSideLeftGif = '/static/img/walk_side_left.gif';
    const walkSideRightGif = '/static/img/walk_side_right.gif';

    // --- Game State ---
    const playerState = {
        x: room.offsetWidth / 2,
        y: room.offsetHeight / 2,
        speed: 3,
        currentAnimation: idleImg
    };
    const keys = {};
    let activeInteraction = null;
    let isDialogActive = false;

    // --- Input Handlers ---
    document.addEventListener('keydown', (e) => {
        if (!isDialogActive) {
            keys[e.key] = true;
        }
    });

    document.addEventListener('keyup', (e) => {
        keys[e.key] = false;
        if (isDialogActive) {
            hideDialog();
            return;
        }
        if (e.key === 'Enter' && activeInteraction) {
            handleInteraction(activeInteraction);
        }
    });

    function handleInteraction(object) {
        const target = object.dataset.interactionTarget;
        if (target === 'chat') {
            fadeOverlay.classList.add('visible');
            setTimeout(() => { window.location.href = '/chat'; }, 300);
        } else if (target === 'books') {
            showDialog('[아이]', '내가 좋아하는 책들이 꽂혀있다. 어려운 내용이 많아 보인다.');
        } else if (target === 'sofa') {
            showDialog('[아이]', '푹신한 소파에 앉아 잠시 쉬어볼까?');
        } else if (target === 'bed') {
            showDialog('[아이]', '침대에 누우니 잠이 솔솔 오는걸?');
        } else if (target === 'schedule') {
            openModal();
        }
    }

    // --- Dialog Functions ---
    function showDialog(speaker, text) {
        dialogSpeaker.textContent = speaker;
        dialogText.textContent = text;
        dialogBox.classList.remove('hidden');
        isDialogActive = true;
        interactionPrompt.classList.add('hidden');
    }

    function hideDialog() {
        dialogBox.classList.add('hidden');
        isDialogActive = false;
    }

    const walls = document.querySelectorAll('.wall');

    // --- Game Loop (New Robust Logic) ---
    function gameLoop() {
        let newAnimation = playerState.currentAnimation;

        // 1. Calculate movement vector
        let dx = 0;
        let dy = 0;
        if (!isDialogActive) {
            if (keys['ArrowUp']) dy -= 1;
            if (keys['ArrowDown']) dy += 1;
            if (keys['ArrowLeft']) dx -= 1;
            if (keys['ArrowRight']) dx += 1;
        }

        // 2. Proposed new position
        const nextX = playerState.x + dx * playerState.speed;
        const nextY = playerState.y + dy * playerState.speed;

        // 3. Wall Collision Detection
        const playerWidth = player.offsetWidth;
        const playerHeight = player.offsetHeight;
        const playerCollisionBuffer = 10; // Adjust this value as needed

        // Calculate player's half-dimensions
        const playerHalfWidth = playerWidth / 2;
        const playerHalfHeight = playerHeight / 2;

        // Calculate the effective collision box dimensions
        const collisionWidth = playerWidth - (2 * playerCollisionBuffer);
        const collisionHeight = playerHeight - (2 * playerCollisionBuffer);

        // Check X-axis collision
        const futurePlayerRectX = {
            left: nextX - playerHalfWidth + playerCollisionBuffer, // Adjust left for center positioning and buffer
            top: playerState.y - playerHalfHeight + playerCollisionBuffer, // Adjust top for center positioning and buffer
            width: collisionWidth,
            height: collisionHeight
        };
        let collisionX = false;
        for (const wall of walls) {
            const wallRect = { left: wall.offsetLeft, top: wall.offsetTop, width: wall.offsetWidth, height: wall.offsetHeight };
            if (checkRectCollision(futurePlayerRectX, wallRect)) {
                collisionX = true;
                break;
            }
        }
        if (!collisionX) {
            playerState.x = nextX;
        }

        // Check Y-axis collision
        const futurePlayerRectY = {
            left: playerState.x - playerHalfWidth + playerCollisionBuffer, // Adjust left for center positioning and buffer
            top: nextY - playerHalfHeight + playerCollisionBuffer, // Adjust top for center positioning and buffer
            width: collisionWidth,
            height: collisionHeight
        };
        let collisionY = false;
        for (const wall of walls) {
            const wallRect = { left: wall.offsetLeft, top: wall.offsetTop, width: wall.offsetWidth, height: wall.offsetHeight };
            if (checkRectCollision(futurePlayerRectY, wallRect)) {
                collisionY = true;
                break;
            }
        }
        if (!collisionY) {
            playerState.y = nextY;
        }
        
        // 4. Determine animation based on actual movement
        if (dx !== 0 || dy !== 0) {
            // Animation decision (Y-axis priority)
            if (dy === -1) { // Moving Up
                newAnimation = walkUpImg;
            } else if (dy === 1) { // Moving Down
                newAnimation = walkFrontGif;
            } else if (dx === -1) { // Moving Left
                newAnimation = walkSideLeftGif;
            } else if (dx === 1) { // Moving Right
                newAnimation = walkSideRightGif;
            }
        } else {
            newAnimation = idleImg;
        }

        // 5. Only update src if the animation has changed
        if (playerState.currentAnimation !== newAnimation) {
            playerImage.src = newAnimation;
            playerState.currentAnimation = newAnimation;
        }

        // 6. Boundary Collision (redundant with walls, but good as a fallback)
        const roomRect = room.getBoundingClientRect();
        playerState.x = Math.max(0, Math.min(roomRect.width - playerWidth, playerState.x));
        playerState.y = Math.max(0, Math.min(roomRect.height - playerHeight, playerState.y));

        // 7. Update Player Position on screen
        player.style.left = `${playerState.x}px`;
        player.style.top = `${playerState.y}px`;

        // 8. Check for Interactions
        if (!isDialogActive) {
            let canInteract = false;
            const updatedPlayerRect = { left: playerState.x, top: playerState.y, width: playerWidth, height: playerHeight };
            for (const object of objects) {
                const objectRect = { left: object.offsetLeft, top: object.offsetTop, width: object.offsetWidth, height: object.offsetHeight };
                if (checkCollision(updatedPlayerRect, objectRect)) {
                    interactionPrompt.textContent = object.dataset.interactionMessage;
                    interactionPrompt.classList.remove('hidden');
                    activeInteraction = object;
                    canInteract = true;
                    break;
                }
            }
            if (!canInteract) {
                interactionPrompt.classList.add('hidden');
                activeInteraction = null;
            }
        }

        // 9. Continue Loop
        requestAnimationFrame(gameLoop);
    }

    function checkCollision(rect1, rect2) {
        const buffer = 20;
        return (
            rect1.left < rect2.left + rect2.width + buffer &&
            rect1.left + rect1.width > rect2.left - buffer &&
            rect1.top < rect2.top + rect2.height + buffer &&
            rect1.top + rect1.height > rect2.top - buffer
        );
    }

    function checkRectCollision(rect1, rect2) {
        return (
            rect1.left < rect2.left + rect2.width &&
            rect1.left + rect1.width > rect2.left &&
            rect1.top < rect2.top + rect2.height &&
            rect1.top + rect1.height > rect2.top
        );
    }

    // --- Initialize and Start Game ---
    player.style.left = `${playerState.x}px`;
    player.style.top = `${playerState.y}px`;
    playerImage.src = idleImg; // Set initial image
    gameLoop();

    // --- Schedule Modal Logic ---
    const scheduleModal = document.getElementById('schedule-modal');
    const closeButton = scheduleModal.querySelector('.close-button');
    const saveScheduleBtn = document.getElementById('save-schedule-btn');
    const scheduleTextarea = document.getElementById('schedule-textarea');

    const openModal = () => {
        if (isDialogActive) return;
        scheduleModal.style.display = 'block';
        isDialogActive = true;
        fetch('/schedule/')
            .then(response => response.json())
            .then(data => { scheduleTextarea.value = data.content || ''; })
            .catch(error => console.error('Error fetching schedule:', error));
    };

    const closeModal = () => { 
        scheduleModal.style.display = 'none';
        isDialogActive = false;
    };

    const saveSchedule = () => {
        const content = scheduleTextarea.value;
        const csrftoken = getCookie('csrftoken');
        fetch('/schedule/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
            body: JSON.stringify({ content: content })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert('일정이 저장되었습니다.');
                closeModal();
            } else {
                alert('저장에 실패했습니다: ' + data.message);
            }
        })
        .catch(error => console.error('Error saving schedule:', error));
    };

    closeButton.addEventListener('click', closeModal);
    saveScheduleBtn.addEventListener('click', saveSchedule);
    window.addEventListener('click', (event) => {
        if (event.target == scheduleModal) closeModal();
    });

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
});