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

    // Directional Idle Images
    const idleLeftImg = '/static/img/left_stand.png';
    const idleRightImg = '/static/img/right_stand.png';
    const idleUpImg = '/static/img/side_up_stand.png';

    // --- Audio Elements ---
    const moveSound = new Audio('/static/audio/walking_bgm.mp3'); // Using walking_bgm.mp3
    moveSound.volume = 0.5; // Reduced volume
    moveSound.loop = true; // Intended for continuous, infinite playback when playing
    let isMovingSoundPlaying = false;

    const collisionSound = new Audio('/static/audio/crash_bgm.mp3'); // Using crash_bgm.mp3
    collisionSound.volume = 0.5; // Reduced volume
    let isCurrentlyColliding = false; // New flag to track if player is currently colliding

    // --- Game State ---
    const playerState = {
        x: room.offsetWidth / 2,
        y: room.offsetHeight / 2,
        speed: 3,
        currentAnimation: idleImg,
        lastDirection: 'down' // Default direction
    };
    const keys = {};
    let activeInteraction = null;
    let isDialogActive = false;
    let lastFrameTime = 0; // For time-based movement

    // --- Debug Visualization ---
    const playerDebugBox = document.createElement('div');
    playerDebugBox.className = 'debug-box';
    room.appendChild(playerDebugBox);

    const obstacles = document.querySelectorAll('.furniture-object');
    const obstacleCollisionBuffer = 35; // Make sure this is defined before use

    obstacles.forEach(obstacle => {
        // 'invisible-wall-'로 시작하는 ID를 가진 요소는 디버그 상자를 그리지 않고 건너뜁니다.
        if (obstacle.id.startsWith('invisible-wall-')) {
            return;
        }
        const debugBox = document.createElement('div');
        debugBox.className = 'debug-box';
        const rect = {
            left: obstacle.offsetLeft + obstacleCollisionBuffer,
            top: obstacle.offsetTop + obstacleCollisionBuffer,
            width: obstacle.offsetWidth - (2 * obstacleCollisionBuffer),
            height: obstacle.offsetHeight - (2 * obstacleCollisionBuffer)
        };
        debugBox.style.left = `${rect.left}px`;
        debugBox.style.top = `${rect.top}px`;
        debugBox.style.width = `${rect.width}px`;
        debugBox.style.height = `${rect.height}px`;
        room.appendChild(debugBox);
    });

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
        if (target === 'chat_history') {
            fadeOverlay.classList.add('visible');
            setTimeout(() => { window.location.href = '/chat_history/'; }, 300);
        } else if (target === 'game-chat') {
            fadeOverlay.classList.add('visible');
            setTimeout(() => { window.location.href = '/game-chat/'; }, 300);
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

    // --- Game Loop (New Robust Logic) ---
    function gameLoop(timestamp) {
        if (!lastFrameTime) lastFrameTime = timestamp;
        const deltaTime = (timestamp - lastFrameTime) / 1000; // Convert to seconds
        lastFrameTime = timestamp;

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

        // Adjust speed by deltaTime
        const currentSpeed = playerState.speed * deltaTime * 60; // Multiply by 60 for a base 60fps speed

        // 2. Proposed new position
        const nextX = playerState.x + dx * currentSpeed;
        const nextY = playerState.y + dy * currentSpeed;

        // Play/pause movement sound
        if (dx !== 0 || dy !== 0) {
            if (!isMovingSoundPlaying) {
                moveSound.play();
                isMovingSoundPlaying = true;
            }
        } else {
            if (isMovingSoundPlaying) {
                moveSound.pause();
                // moveSound.currentTime = 0; // Removed again to allow continuous loop without reset
                isMovingSoundPlaying = false;
            }
        }

        // 3. Obstacle Collision Detection
        const playerWidth = player.offsetWidth;
        const playerHeight = player.offsetHeight;
        const playerCollisionBuffer = 10; // Shrinks player's box
        
        // Calculate player's half-dimensions
        const playerHalfWidth = playerWidth / 2;
        const playerHalfHeight = playerHeight / 2;

        // Calculate the effective collision box dimensions
        const collisionWidth = playerWidth - (2 * playerCollisionBuffer);
        const collisionHeight = playerHeight - (2 * playerCollisionBuffer);

        let currentFrameCollision = false; // Flag for collision in this frame

        // Check X-axis collision
        const futurePlayerRectX = {
            left: nextX - playerHalfWidth + playerCollisionBuffer, // Adjust left for center positioning and buffer
            top: playerState.y - playerHalfHeight + playerCollisionBuffer, // Adjust top for center positioning and buffer
            width: collisionWidth,
            height: collisionHeight
        };
        let collisionX = false;
        for (const obstacle of obstacles) {
            let obstacleRect;
            if (obstacle.id.startsWith('invisible-wall-')) {
                // For our wall, use the exact dimensions without a buffer
                obstacleRect = {
                    left: obstacle.offsetLeft,
                    top: obstacle.offsetTop,
                    width: obstacle.offsetWidth,
                    height: obstacle.offsetHeight
                };
            } else {
                // For all other obstacles, use the buffer as before
                obstacleRect = { 
                    left: obstacle.offsetLeft + obstacleCollisionBuffer,
                    top: obstacle.offsetTop + obstacleCollisionBuffer,
                    width: obstacle.offsetWidth - (2 * obstacleCollisionBuffer),
                    height: obstacle.offsetHeight - (2 * obstacleCollisionBuffer)
                };
            }
            if (checkRectCollision(futurePlayerRectX, obstacleRect)) {
                collisionX = true;
                currentFrameCollision = true;
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
        for (const obstacle of obstacles) {
            let obstacleRect;
            if (obstacle.id.startsWith('invisible-wall-')) {
                // For our wall, use the exact dimensions without a buffer
                obstacleRect = {
                    left: obstacle.offsetLeft,
                    top: obstacle.offsetTop,
                    width: obstacle.offsetWidth,
                    height: obstacle.offsetHeight
                };
            } else {
                // For all other obstacles, use the buffer as before
                obstacleRect = { 
                    left: obstacle.offsetLeft + obstacleCollisionBuffer,
                    top: obstacle.offsetTop + obstacleCollisionBuffer,
                    width: obstacle.offsetWidth - (2 * obstacleCollisionBuffer),
                    height: obstacle.offsetHeight - (2 * obstacleCollisionBuffer)
                };
            }
            if (checkRectCollision(futurePlayerRectY, obstacleRect)) {
                collisionY = true;
                currentFrameCollision = true;
                break;
            }
        }
        if (!collisionY) {
            playerState.y = nextY;
        }

        // Collision sound logic: Play only on initial impact
        if (currentFrameCollision && !isCurrentlyColliding) {
            collisionSound.currentTime = 0; // Ensure it plays from the start
            collisionSound.play();
        }
        isCurrentlyColliding = currentFrameCollision;
        
        // 4. Determine animation based on actual movement
        if (dx !== 0 || dy !== 0) {
            // Animation decision (Y-axis priority)
            if (dy === -1) { // Moving Up
                newAnimation = walkUpImg;
                playerState.lastDirection = 'up';
            } else if (dy === 1) { // Moving Down
                newAnimation = walkFrontGif;
                playerState.lastDirection = 'down';
            } else if (dx === -1) { // Moving Left
                newAnimation = walkSideLeftGif;
                playerState.lastDirection = 'left';
            } else if (dx === 1) { // Moving Right
                newAnimation = walkSideRightGif;
                playerState.lastDirection = 'right';
            }
        } else {
            // Select idle animation based on last direction
            switch (playerState.lastDirection) {
                case 'up':
                    newAnimation = idleUpImg;
                    break;
                case 'left':
                    newAnimation = idleLeftImg;
                    break;
                case 'right':
                    newAnimation = idleRightImg;
                    break;
                case 'down':
                default:
                    newAnimation = idleImg; // Default down-facing idle
                    break;
            }
        }

        // 5. Only update src if the animation has changed
        if (playerState.currentAnimation !== newAnimation) {
            playerImage.src = newAnimation;
            playerState.currentAnimation = newAnimation;
        }

        // 6. Boundary Collision (redundant with walls, but good as a fallback)
        const roomRect = room.getBoundingClientRect();
        playerState.x = Math.max(playerWidth / 2, Math.min(roomRect.width - playerWidth / 2, playerState.x));
        playerState.y = Math.max(playerHeight / 2, Math.min(roomRect.height - playerHeight / 2, playerState.y));

        // 7. Update Player Position on screen
        player.style.left = `${playerState.x}px`;
        player.style.top = `${playerState.y}px`;

        // --- Update Debug Box for Player ---
        const playerCollisionRect = {
            left: playerState.x - playerHalfWidth + playerCollisionBuffer,
            top: playerState.y - playerHalfHeight + playerCollisionBuffer,
            width: collisionWidth,
            height: collisionHeight
        };
        playerDebugBox.style.left = `${playerCollisionRect.left}px`;
        playerDebugBox.style.top = `${playerCollisionRect.top}px`;
        playerDebugBox.style.width = `${playerCollisionRect.width}px`;
        playerDebugBox.style.height = `${playerCollisionRect.height}px`;

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

        // Update proactive notification position
        if (notificationBubble && notificationBubble.style.display !== 'none') {
            const bubbleWidth = 40;
            const bubbleHeight = 40;
            const playerHeight = 120;
            notificationBubble.style.left = `${playerState.x - bubbleWidth / 2}px`;
            notificationBubble.style.top = `${playerState.y - playerHeight / 2 - bubbleHeight - 20}px`;
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

    // --- Proactive Notification Logic ---
    const notificationBubble = document.getElementById('proactive-notification');

    function checkProactiveNotification() {
        fetch('/check-notification/')
            .then(response => response.json())
            .then(data => {
                if (data.has_pending_message) {
                    notificationBubble.style.display = 'flex'; // Use flex to center the '!'
                } else {
                    notificationBubble.style.display = 'none';
                }
            })
            .catch(error => {
                console.error('Error checking for proactive messages:', error);
                notificationBubble.style.display = 'none';
            });
    }

    // Check immediately on load, then every 5 seconds
    checkProactiveNotification();
    setInterval(checkProactiveNotification, 5000);

    // --- Initialize and Start Game ---
    player.style.left = `${playerState.x}px`;
    player.style.top = `${playerState.y}px`;
    playerImage.src = idleImg; // Set initial image
    requestAnimationFrame(gameLoop);

    // --- Schedule Modal Logic ---
    const scheduleModal = document.getElementById('schedule-modal');
    const closeButton = scheduleModal.querySelector('.close-button');
    const scheduleListContainer = document.getElementById('schedule-list-container');
    const newScheduleTimeInput = document.getElementById('new-schedule-time-input');
    const newScheduleTextarea = document.getElementById('new-schedule-textarea');
    const addScheduleBtn = document.getElementById('add-schedule-btn');

    let editingScheduleId = null; // 현재 편집 중인 스케줄 ID 추적

    const fetchAndRenderSchedules = () => {
        fetch('/schedule/')
            .then(response => response.json())
            .then(data => {
                renderSchedules(data.schedules);
            })
            .catch(error => console.error('스케줄 불러오기 오류:', error));
    };

    const renderSchedules = (schedules) => {
        scheduleListContainer.innerHTML = ''; // Clear existing list
        if (schedules.length === 0) {
            scheduleListContainer.innerHTML = '<p>오늘의 일정이 없습니다. 새로운 일정을 추가해보세요!</p>';
            return;
        }

        schedules.forEach(schedule => {
            const scheduleItem = document.createElement('div');
            scheduleItem.className = 'schedule-item';
            scheduleItem.dataset.id = schedule.id;
            scheduleItem.innerHTML = `
                <span class="schedule-time">${schedule.schedule_time || '시간 미지정'}</span>
                <span class="schedule-content">${schedule.content}</span>
                <div class="schedule-actions">
                    <button class="edit-schedule-btn" data-id="${schedule.id}">수정</button>
                    <button class="delete-schedule-btn" data-id="${schedule.id}">삭제</button>
                </div>
            `;
            scheduleListContainer.appendChild(scheduleItem);
        });

        // Add event listeners for dynamically created buttons
        scheduleListContainer.querySelectorAll('.edit-schedule-btn').forEach(button => {
            button.addEventListener('click', (event) => {
                const id = parseInt(event.target.dataset.id);
                const scheduleToEdit = schedules.find(s => s.id === id);
                if (scheduleToEdit) {
                    newScheduleTimeInput.value = scheduleToEdit.schedule_time || '09:00';
                    newScheduleTextarea.value = scheduleToEdit.content;
                    addScheduleBtn.textContent = '일정 업데이트';
                    editingScheduleId = id;
                }
            });
        });

        scheduleListContainer.querySelectorAll('.delete-schedule-btn').forEach(button => {
            button.addEventListener('click', (event) => {
                const id = parseInt(event.target.dataset.id);
                if (confirm('정말로 이 일정을 삭제하시겠습니까?')) {
                    deleteSchedule(id);
                }
            });
        });
    };

    const openModal = () => {
        if (isDialogActive) return;
        scheduleModal.style.display = 'block';
        isDialogActive = true;
        fetchAndRenderSchedules(); // Fetch and render schedules when modal opens
        // Reset new schedule input fields
        newScheduleTimeInput.value = '09:00';
        newScheduleTextarea.value = '';
        addScheduleBtn.textContent = '일정 추가';
        editingScheduleId = null;
    };

    const closeModal = () => {
        scheduleModal.style.display = 'none';
        isDialogActive = false;
    };

    const handleAddUpdateSchedule = () => {
        const content = newScheduleTextarea.value;
        const schedule_time = newScheduleTimeInput.value;
        const csrftoken = getCookie('csrftoken');

        if (!content) {
            alert('일정 내용을 입력해주세요.');
            return;
        }

        let bodyData = { content: content, schedule_time: schedule_time };
        let action = 'create';

        if (editingScheduleId) {
            action = 'update';
            bodyData.id = editingScheduleId;
        }
        bodyData.action = action;

        fetch('/schedule/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
            body: JSON.stringify(bodyData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert(data.message);
                newScheduleTextarea.value = '';
                newScheduleTimeInput.value = '09:00';
                addScheduleBtn.textContent = '일정 추가';
                editingScheduleId = null;
                fetchAndRenderSchedules(); // Re-fetch and render schedules
            } else {
                alert('작업에 실패했습니다: ' + data.message);
            }d
        })
        .catch(error => console.error('스케줄 저장 오류:', error));
    };

    const deleteSchedule = (id) => {
        const csrftoken = getCookie('csrftoken');
        fetch('/schedule/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
            body: JSON.stringify({ action: 'delete', id: id })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert(data.message);
                fetchAndRenderSchedules(); // 스케줄 다시 불러와 렌더링
            } else {
                alert('삭제에 실패했습니다: ' + data.message);
            }
        })
        .catch(error => console.error('스케줄 삭제 오류:', error));
    };

    closeButton.addEventListener('click', closeModal);
    addScheduleBtn.addEventListener('click', handleAddUpdateSchedule);
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