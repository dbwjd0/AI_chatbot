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
    const chatbotName = document.querySelector('.container').dataset.chatbotName || '아이';

    const refrigeratorModal = document.getElementById('refrigerator-modal');
    const refrigeratorCloseButton = refrigeratorModal.querySelector('.close-button');

    let processingBubble; // 처리 중 말풍선
    let processingAnimationInterval; // 애니메이션 인터벌 ID
    let processingDotCount = 0; // 점 개수

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
    const moveSound = new Audio('/static/audio/양말 걷기.mp3'); // Using walking_bgm.mp3
    moveSound.volume = 1; // Reduced volume
    moveSound.loop = true; // Intended for continuous, infinite playback when playing
    let isMovingSoundPlaying = false;

    const collisionSound = new Audio('/static/audio/부딪힘.mp3'); // Using crash_bgm.mp3
    collisionSound.volume = 0.5; // Reduced volume
    let isCurrentlyColliding = false; // New flag to track if player is currently colliding

    const selectionSound = new Audio('/static/audio/선택지 좌우.mp3');
    selectionSound.volume = 0.3;
    const confirmationSound = new Audio('/static/audio/선택지 결정.mp3');
    confirmationSound.volume = 0.5;
    const yesConfirmationSound = new Audio('/static/audio/선택지 \'예\'.mp3');
    yesConfirmationSound.volume = 0.5;

    // --- Game State ---
    const playerState = {
        x: (room.offsetWidth / 2) - 200,
        y: room.offsetHeight / 2,
        speed: 3,
        currentAnimation: idleImg,
        lastDirection: 'down' // Default direction
    };
    const keys = {};
    let activeInteraction = null;
    let isDialogActive = false;
    let isConfirmationActive = false;
    let isRefrigeratorConfirmationActive = false; // Add this line
    let selectedConfirmationOption = 'yes'; // 'yes' or 'no'
    let onQuizCooldown = false; // Cooldown flag for the quiz interaction
    let lastFrameTime = 0; // For time-based movement

    // --- Debug Visualization ---
    const playerDebugBox = document.createElement('div');
    playerDebugBox.className = 'debug-box';
    room.appendChild(playerDebugBox);

    // --- 처리 중 말풍선 초기화 ---
    processingBubble = document.createElement('div');
    processingBubble.id = 'processing-bubble';
    processingBubble.textContent = '.'; // 초기 텍스트
    room.appendChild(processingBubble);

    const obstacles = document.querySelectorAll('.furniture-object');
    const obstacleCollisionBuffer = 35; // Make sure this is defined before use

    // --- 컴퓨터 오브젝트 충돌 상자 직접 설정 ---
    // 아래 값을 조절하여 컴퓨터 오브젝트의 충돌 상자를 변경하세요.
    const computerCollision = {
        // x: 이미지 왼쪽을 기준으로 충돌 상자를 좌/우로 이동합니다. (양수: 오른쪽, 음수: 왼쪽)
        x: 50, 
        // y: 이미지 위쪽을 기준으로 충돌 상자를 위/아래로 이동합니다. (양수: 아래쪽, 음수: 위쪽)
        y: 50,
        // width: 충돌 상자의 너비
        width: 280,
        // height: 충돌 상자의 높이
        height: 170 
    };

    // --- 티비 오브젝트 충돌 상자 직접 설정 ---
    // 아래 값을 조절하여 티비 오브젝트의 충돌 상자를 변경하세요.
    const tvCollision = {
        // x: 이미지 왼쪽을 기준으로 충돌 상자를 좌/우로 이동합니다. (양수: 오른쪽, 음수: 왼쪽)
        x: 20, 
        // y: 이미지 위쪽을 기준으로 충돌 상자를 위/아래로 이동합니다. (양수: 아래쪽, 음수: 위쪽)
        y: 70,
        // width: 충돌 상자의 너비
        width: 230,
        // height: 충돌 상자의 높이
        height: 150 
    };

    function getObstacleRect(obstacle) {
        if (obstacle.id === 'computer-obj') {
            return {
                left: obstacle.offsetLeft + computerCollision.x,
                top: obstacle.offsetTop + computerCollision.y,
                width: computerCollision.width,
                height: computerCollision.height
            };
        }
        if (obstacle.id === 'tv') {
            return {
                left: obstacle.offsetLeft + tvCollision.x,
                top: obstacle.offsetTop + tvCollision.y,
                width: tvCollision.width,
                height: tvCollision.height
            };
        }
        if (obstacle.id.startsWith('invisible-wall-')) {
            return {
                left: obstacle.offsetLeft,
                top: obstacle.offsetTop,
                width: obstacle.offsetWidth,
                height: obstacle.offsetHeight
            };
        }
        return { 
            left: obstacle.offsetLeft + obstacleCollisionBuffer,
            top: obstacle.offsetTop + obstacleCollisionBuffer,
            width: obstacle.offsetWidth - (2 * obstacleCollisionBuffer),
            height: obstacle.offsetHeight - (2 * obstacleCollisionBuffer)
        };
    }

    obstacles.forEach(obstacle => {
        // 'invisible-wall-'로 시작하는 ID를 가진 요소는 디버그 상자를 그리지 않고 건너뜁니다.
        if (obstacle.id.startsWith('invisible-wall-')) {
            return;
        }
        const debugBox = document.createElement('div');
        debugBox.className = 'debug-box';
        const rect = getObstacleRect(obstacle);
        debugBox.style.left = `${rect.left}px`;
        debugBox.style.top = `${rect.top}px`;
        debugBox.style.width = `${rect.width}px`;
        debugBox.style.height = `${rect.height}px`;
        room.appendChild(debugBox);
    });

    // --- 상호작용 영역 시각화 ---
    const interactiveObjects = document.querySelectorAll('.interactive-object');

    interactiveObjects.forEach(object => {
        const vizBox = document.createElement('div');
        vizBox.className = 'interaction-area-visualization';
        
        let rect;
        if (object.id === 'Quiz-line') {
            // Quiz-line은 넓은 상호작용 범위를 가짐
            const interactionBuffer = 20; 
            rect = {
                left: object.offsetLeft - interactionBuffer,
                top: object.offsetTop - interactionBuffer,
                width: object.offsetWidth + (2 * interactionBuffer),
                height: object.offsetHeight + (2 * interactionBuffer)
            };
        } else {
            // 다른 오브젝트들은 충돌 범위 + 10px 버퍼를 가짐
            const interactionBuffer = 10; 
            const collisionRect = getObstacleRect(object);
            rect = {
                left: collisionRect.left - interactionBuffer,
                top: collisionRect.top - interactionBuffer,
                width: collisionRect.width + (2 * interactionBuffer),
                height: collisionRect.height + (2 * interactionBuffer)
            };
        }

        vizBox.style.left = `${rect.left}px`;
        vizBox.style.top = `${rect.top}px`;
        vizBox.style.width = `${rect.width}px`;
        vizBox.style.height = `${rect.height}px`;
        room.appendChild(vizBox);
    });

    // --- Input Handlers ---
    document.addEventListener('keydown', (e) => {
        if (isRefrigeratorConfirmationActive) { // Add this block
            if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
                selectionSound.currentTime = 0;
                selectionSound.play();
                selectedConfirmationOption = selectedConfirmationOption === 'yes' ? 'no' : 'yes';
                updateConfirmationSelection();
            }
            return; // Prevent movement keys from being processed
        }
        if (isConfirmationActive) {
            if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
                selectionSound.currentTime = 0;
                selectionSound.play();
                selectedConfirmationOption = selectedConfirmationOption === 'yes' ? 'no' : 'yes';
                updateConfirmationSelection();
            }
        } else if (!isDialogActive) {
            keys[e.key] = true;
        }
    });

    document.addEventListener('keyup', (e) => {
        keys[e.key] = false;
        if (isRefrigeratorConfirmationActive) { // Add this block
            if (e.key === 'Enter') {
                handleRefrigeratorConfirmation();
            }
            return;
        }
        if (isConfirmationActive) {
            if (e.key === 'Enter') {
                handleConfirmation();
            }
            return;
        }

        // 대화창이 활성화된 상태에서 Enter를 누르면, 후속 동작을 처리
        if (isDialogActive) {
            const interactionTarget = activeInteraction ? activeInteraction.dataset.interactionTarget : null;
            
            hideDialog(); // 먼저 대화창을 닫고

            // 후속 동작으로 페이지 이동이 필요한 경우 처리
            if (interactionTarget === 'chat' || interactionTarget === 'chat_history') {
                fadeOverlay.classList.add('visible');
                setTimeout(() => { window.location.href = `/${interactionTarget}/`; }, 300);
            }
            return;
        }

        if (e.key === 'Enter' && activeInteraction) {
            handleInteraction(activeInteraction);
        }
    });

    function handleInteraction(object) {
        const target = object.dataset.interactionTarget;

        if (target === 'schedule') {
            openModal();
            return;
        }

        if (target === 'refrigerator') { // Add this block
            showRefrigeratorConfirmationDialog();
            return;
        }

        const csrftoken = getCookie('csrftoken');

        startProcessingAnimation(); // 로딩 인디케이터 시작

        // API 요청을 통해 동적 대사를 가져옴
        fetch('/api/get-interaction-dialog/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify({ target: target })
        })
        .then(response => response.json())
        .then(data => {
            stopProcessingAnimation(); // 로딩 인디케이터 중지
            if (data.message) {
                if (target === 'bed') {
                    showBedDialog(data.message);
                } else {
                    const imageUrl = (target === 'sofa') ? '/static/img/char_thinking.png' : null;
                    showDialog(`[${chatbotName}]`, data.message, imageUrl);
                }
            }
        })
        .catch(error => {
            stopProcessingAnimation(); // 로딩 인디케이터 중지
            console.error('Error fetching interaction dialog:', error);
            // 에러 발생 시 기본 대사 출력
            showDialog(`[${chatbotName}]`, '...');
        });
    }

    // --- Dialog Functions ---
    function showBedDialog(text) {
        const bedImage = document.getElementById('bed-character-image');
        dialogSpeaker.textContent = `[${chatbotName}]`;
        dialogText.textContent = text;

        if (bedImage) {
            bedImage.src = '/static/img/char_happy_left.png';
            bedImage.style.display = 'block';
        }

        dialogBox.classList.remove('hidden');
        isDialogActive = true;
        interactionPrompt.classList.add('hidden');
    }

    function showDialog(speaker, text, imageUrl = null) {
        const dialogImage = document.getElementById('dialog-character-image');
        const dialogSpeaker = document.getElementById('dialog-speaker');
        const dialogText = document.getElementById('dialog-text');

        // Ensure elements exist before using them
        if (dialogSpeaker) dialogSpeaker.textContent = speaker;
        if (dialogText) dialogText.textContent = text;

        if (imageUrl && dialogImage) {
            dialogImage.src = imageUrl;
            dialogImage.style.display = 'block';
        } else if (dialogImage) {
            dialogImage.style.display = 'none';
        }

        dialogBox.classList.remove('hidden');
        isDialogActive = true;
        interactionPrompt.classList.add('hidden');
    }

    function hideDialog() {
        dialogBox.classList.add('hidden');
        isDialogActive = false;
        isConfirmationActive = false;
        isRefrigeratorConfirmationActive = false; // Add this line

        // Hide the image as well
        const dialogImage = document.getElementById('dialog-character-image');
        const bedImage = document.getElementById('bed-character-image');
        if (dialogImage) dialogImage.style.display = 'none';
        if (bedImage) bedImage.style.display = 'none';

        // Remove confirmation buttons if they exist
        const options = dialogBox.querySelector('.dialog-options');
        if (options) {
            options.remove();
        }
    }

    function showRefrigeratorConfirmationDialog() {
        if (isDialogActive) return;

        isDialogActive = true;
        isRefrigeratorConfirmationActive = true;
        selectedConfirmationOption = 'yes';

        dialogSpeaker.textContent = `[${chatbotName}]`;
        dialogText.textContent = '맛있는 냄새가 나는데, 냉장고를 열어볼까?';

        const options = document.createElement('div');
        options.className = 'dialog-options';

        const yesButton = document.createElement('button');
        yesButton.id = 'confirm-yes';
        yesButton.textContent = '예';

        const noButton = document.createElement('button');
        noButton.id = 'confirm-no';
        noButton.textContent = '아니요';

        options.appendChild(yesButton);
        options.appendChild(noButton);
        dialogBox.appendChild(options);

        updateConfirmationSelection();
        dialogBox.classList.remove('hidden');
    }

    function handleRefrigeratorConfirmation() {
        if (selectedConfirmationOption === 'yes') {
            yesConfirmationSound.play();
            hideDialog();
            openRefrigeratorModal();
        } else {
            confirmationSound.play();
            hideDialog();
        }
    }

    function openRefrigeratorModal() {
        fetch('/api/refrigerator-contents/')
            .then(response => response.json())
            .then(data => {
                displayRefrigeratorContents(data.foods);
                refrigeratorModal.style.display = 'block';
                isDialogActive = true; // Prevent player movement
            })
            .catch(error => {
                console.error('Error fetching refrigerator contents:', error);
            });
    }

    function displayRefrigeratorContents(foods) {
        const itemsContainer = document.getElementById('refrigerator-items');
        itemsContainer.innerHTML = ''; // 기존 아이템 삭제

        if (foods.length === 0) {
            itemsContainer.innerHTML = '<p>냉장고가 비어있습니다.</p>';
            return;
        }

        foods.forEach(food => {
            const foodImg = document.createElement('img');
            foodImg.src = `/static/img/${food.image}`;
            foodImg.alt = food.name;
            foodImg.dataset.foodName = food.name; // 음식 이름 저장
            foodImg.style.cursor = 'pointer';
            foodImg.addEventListener('click', () => {
                playEatingAnimation(food.name);
            });
            itemsContainer.appendChild(foodImg);
        });
    }

    function playEatingAnimation(foodName) {
        closeRefrigeratorModal();

        // 서버에 음식 소비 사실을 알림
        const csrftoken = getCookie('csrftoken');
        fetch('/api/consume-food/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify({ food_name: foodName })
        })
        .catch(error => console.error('Error consuming food:', error));
        
        const originalAnimation = playerImage.src; // 현재 애니메이션 저장
        isDialogActive = true; // 먹는 동안 움직임 방지

        playerImage.src = '/static/img/먹는 모션.gif';

        // 먹는 모션 시간을 2초로 변경
        setTimeout(() => {
            playerImage.src = originalAnimation;
            isDialogActive = false; // 움직임 다시 허용
            showHeartBubble(); // 하트 말풍선 표시 함수 호출
        }, 2000);
    }

    function showHeartBubble() {
        const heartBubble = document.createElement('div');
        heartBubble.className = 'feedback-bubble'; // 새로운 CSS 클래스 적용
        heartBubble.textContent = '❤️';

        // 플레이어 머리 위에 위치 설정
        const bubbleWidth = 40;
        const bubbleHeight = 40;
        const playerHeight = 120;
        heartBubble.style.left = `${playerState.x - bubbleWidth / 2}px`;
        heartBubble.style.top = `${playerState.y - playerHeight / 2 - bubbleHeight - 10}px`;

        room.appendChild(heartBubble);

        // 2초 후에 말풍선 제거
        setTimeout(() => {
            if (heartBubble.parentNode) {
                heartBubble.parentNode.removeChild(heartBubble);
            }
        }, 2000);
    }

    function closeRefrigeratorModal() {
        refrigeratorModal.style.display = 'none';
        isDialogActive = false; // Allow player movement
    }

    function showConfirmationDialog() {
        if (isConfirmationActive || onQuizCooldown) return; // Prevent multiple triggers

        isDialogActive = true;
        isConfirmationActive = true;
        selectedConfirmationOption = 'yes';

        dialogSpeaker.textContent = '[시스템]';
        dialogText.textContent = '퀴즈 방으로 이동할까?';

        const options = document.createElement('div');
        options.className = 'dialog-options';

        const yesButton = document.createElement('button');
        yesButton.id = 'confirm-yes';
        yesButton.textContent = '예';

        const noButton = document.createElement('button');
        noButton.id = 'confirm-no';
        noButton.textContent = '아니요';

        options.appendChild(yesButton);
        options.appendChild(noButton);
        dialogBox.appendChild(options);

        updateConfirmationSelection();
        dialogBox.classList.remove('hidden');
    }

    function updateConfirmationSelection() {
        const yesButton = document.getElementById('confirm-yes');
        const noButton = document.getElementById('confirm-no');
        if (!yesButton || !noButton) return;

        if (selectedConfirmationOption === 'yes') {
            yesButton.classList.add('selected');
            noButton.classList.remove('selected');
        } else {
            noButton.classList.add('selected');
            yesButton.classList.remove('selected');
        }
    }

    function handleConfirmation() {
        if (selectedConfirmationOption === 'yes') {
            yesConfirmationSound.play();
            fadeOverlay.classList.add('visible');
            setTimeout(() => { window.location.href = '/quiz/'; }, 300);
        } else {
            confirmationSound.play();
            hideDialog();
            onQuizCooldown = true;
            setTimeout(() => { onQuizCooldown = false; }, 1000); // 1-second cooldown
        }
    }

    function startProcessingAnimation() {
        processingDotCount = 0;
        processingBubble.textContent = '.';
        processingBubble.style.display = 'flex'; // Show the bubble
        processingAnimationInterval = setInterval(() => {
            processingDotCount = (processingDotCount % 3) + 1;
            processingBubble.textContent = '.'.repeat(processingDotCount);
        }, 300); // Update every 300ms
    }

    function stopProcessingAnimation() {
        clearInterval(processingAnimationInterval);
        processingBubble.style.display = 'none'; // Hide the bubble
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
                isMovingSoundPlaying = false;
            }
        }

        // 3. Obstacle Collision Detection
        const playerWidth = player.offsetWidth;
        const playerHeight = player.offsetHeight;
        const playerHalfWidth = playerWidth / 2;
        const playerHalfHeight = playerHeight / 2;

        const collisionHeight = playerHeight * 0.2;
        const collisionWidth = playerWidth * 0.6;

        let currentFrameCollision = false;

        const futurePlayerRectX = {
            left: nextX - collisionWidth / 2,
            top: playerState.y + playerHalfHeight - collisionHeight,
            width: collisionWidth,
            height: collisionHeight
        };
        let collisionX = false;
        for (const obstacle of obstacles) {
            const obstacleRect = getObstacleRect(obstacle);
            if (checkRectCollision(futurePlayerRectX, obstacleRect)) {
                collisionX = true;
                currentFrameCollision = true;
                break;
            }
        }
        if (!collisionX) {
            playerState.x = nextX;
        }

        const futurePlayerRectY = {
            left: playerState.x - collisionWidth / 2,
            top: nextY + playerHalfHeight - collisionHeight,
            width: collisionWidth,
            height: collisionHeight
        };
        let collisionY = false;
        for (const obstacle of obstacles) {
            const obstacleRect = getObstacleRect(obstacle);
            if (checkRectCollision(futurePlayerRectY, obstacleRect)) {
                collisionY = true;
                currentFrameCollision = true;
                break;
            }
        }
        if (!collisionY) {
            playerState.y = nextY;
        }

        if (currentFrameCollision && !isCurrentlyColliding) {
            collisionSound.currentTime = 0;
            collisionSound.play();
        }
        isCurrentlyColliding = currentFrameCollision;
        
        // 4. Determine animation based on actual movement
        if (dx !== 0 || dy !== 0) {
            if (dy === -1) { newAnimation = walkUpImg; playerState.lastDirection = 'up'; }
            else if (dy === 1) { newAnimation = walkFrontGif; playerState.lastDirection = 'down'; }
            else if (dx === -1) { newAnimation = walkSideLeftGif; playerState.lastDirection = 'left'; }
            else if (dx === 1) { newAnimation = walkSideRightGif; playerState.lastDirection = 'right'; }
        } else {
            switch (playerState.lastDirection) {
                case 'up': newAnimation = idleUpImg; break;
                case 'left': newAnimation = idleLeftImg; break;
                case 'right': newAnimation = idleRightImg; break;
                default: newAnimation = idleImg; break;
            }
        }

        if (playerState.currentAnimation !== newAnimation) {
            playerImage.src = newAnimation;
            playerState.currentAnimation = newAnimation;
        }

        // 6. Boundary Collision
        const roomRect = room.getBoundingClientRect();
        playerState.x = Math.max(playerWidth / 2, Math.min(roomRect.width - playerWidth / 2, playerState.x));
        playerState.y = Math.max(playerHeight / 2, Math.min(roomRect.height - playerHeight / 2, playerState.y));

        // 7. Update Player Position
        player.style.left = `${playerState.x}px`;
        player.style.top = `${playerState.y}px`;

        // --- Update Debug Box for Player ---
        const playerCollisionRect = {
            left: playerState.x - collisionWidth / 2,
            top: playerState.y + playerHalfHeight - collisionHeight,
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
            const playerCollisionRect = {
                left: playerState.x - collisionWidth / 2,
                top: playerState.y + playerHalfHeight - collisionHeight,
                width: collisionWidth,
                height: collisionHeight
            };

            for (const object of objects) {
                let interactionTriggered = false;

                if (object.id === 'Quiz-line') {
                    // Quiz-line은 예전처럼 넓은 범위의 상호작용을 사용
                    const interactionBuffer = 20;
                    const playerRect = { left: playerState.x, top: playerState.y, width: playerWidth, height: playerHeight };
                    const objectRect = { 
                        left: object.offsetLeft - interactionBuffer,
                        top: object.offsetTop - interactionBuffer,
                        width: object.offsetWidth + (2 * interactionBuffer),
                        height: object.offsetHeight + (2 * interactionBuffer)
                    };
                    // checkRectCollision을 사용하여 플레이어의 전체 박스와 확장된 오브젝트 박스를 비교
                    if (checkRectCollision(playerRect, objectRect)) {
                        interactionTriggered = true;
                    }
                } else {
                    // 다른 오브젝트들은 충돌 범위 + 10px 버퍼를 사용
                    const interactionBuffer = 10; 
                    const objectCollisionRect = getObstacleRect(object);
                    const interactionRect = {
                        left: objectCollisionRect.left - interactionBuffer,
                        top: objectCollisionRect.top - interactionBuffer,
                        width: objectCollisionRect.width + (2 * interactionBuffer),
                        height: objectCollisionRect.height + (2 * interactionBuffer)
                    };
                    if (checkRectCollision(playerCollisionRect, interactionRect)) {
                        interactionTriggered = true;
                    }
                }

                if (interactionTriggered) {
                    if (object.id === 'Quiz-line' && !onQuizCooldown) {
                        showConfirmationDialog();
                        canInteract = false; // No prompt for this one
                    } else {
                        interactionPrompt.textContent = object.dataset.interactionMessage;
                        interactionPrompt.classList.remove('hidden');
                        activeInteraction = object;
                        canInteract = true;
                    }
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

        // Update processing bubble position
        if (processingBubble && processingBubble.style.display !== 'none') {
            const bubbleWidth = 40;
            const bubbleHeight = 40;
            const playerHeight = 120;
            processingBubble.style.left = `${playerState.x - bubbleWidth / 2}px`;
            processingBubble.style.top = `${playerState.y - playerHeight / 2 - bubbleHeight - 20}px`;
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

    refrigeratorCloseButton.addEventListener('click', closeRefrigeratorModal);
    window.addEventListener('click', (event) => {
        if (event.target == refrigeratorModal) {
            closeRefrigeratorModal();
        }
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