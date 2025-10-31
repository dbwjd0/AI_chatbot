// game_chat.js

document.addEventListener('DOMContentLoaded', function () {
    // --- DOM Elements ---
    const dialogueText = document.getElementById('dialogue-text');
    const speakerName = document.getElementById('speaker-name');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const characterImage = document.getElementById('chatbot-character');
    const prevDialogueButton = document.getElementById('prev-dialogue-button');
    const imageInput = document.getElementById('image-input');
    const attachImageButton = document.getElementById('attach-image-button');
    const previewContainer = document.getElementById('preview-container');
    const imagePreview = document.getElementById('image-preview');
    const clearImageButton = document.getElementById('clear-image-button');
    const aiEmoticonBubble = document.getElementById('ai-emoticon-bubble');
    const aiEmoticonImg = document.getElementById('ai-emoticon-img');
    const emoticonButton = document.getElementById('emoticon-button');
    const emoticonPalette = document.getElementById('emoticon-palette');
    const emoticonPreviewContainer = document.getElementById('emoticon-preview-container');
    const emoticonPreview = document.getElementById('emoticon-preview');
    const clearEmoticonButton = document.getElementById('clear-emoticon-button');
    const locationCheckbox = document.getElementById('location-checkbox');
    const feedbackContainer = document.getElementById('feedback-container');
    const thumbUpButton = document.getElementById('thumb-up-button');
    const thumbDownButton = document.getElementById('thumb-down-button');
    const friendMessageInput = document.getElementById('friend-message-input');
    const messageButton = document.getElementById('message-button');
    const sendFriendMessageButton = document.getElementById('send-friend-message-button');
    const friendReceiverSelect = document.getElementById('friend-receiver-select'); // New DOM element
    const unreadMessagesButton = document.getElementById('unread-messages-button'); // New DOM element

    // --- State Variables ---
    let aiMessageQueue = [];
    let displayedAiLinesHistory = [];
    let isDisplayingMessage = false;
    let currentImageFile = null;
    let currentSelectedEmoticon = null;
    let currentFullAiResponse = "";
    let typingSpeed = 50;
    let isTyping = false;
    let currentTypingLine = '';
    let typingTimeout = null;
    let typingResolve = null;
    let currentLearningData = null; // To store state_vector and action_id
    let isFriendMessageMode = false; // New state variable

    const emoticons = [
        '결제_이모티콘.png', '계략_이모티콘.png', '돌_이모티콘.png', '따봉_이모티콘.png',
        '밥_이모티콘.png', '슬픔_이모티콘.png', '의기양양_이모티콘.png', '주라_이모티콘.png',
        '짜증_이모티콘.png', '팝콘_이모티콘.png', '하트눈_이모티콘.png'
    ];

    // --- Image Handling ---
    attachImageButton.addEventListener('click', () => imageInput.click());

    imageInput.addEventListener('change', () => {
        const file = imageInput.files[0];
        if (file) {
            currentImageFile = file;
            const reader = new FileReader();
            reader.onload = (e) => {
                imagePreview.src = e.target.result;
                previewContainer.style.display = 'block';
            };
            reader.readAsDataURL(file);
        }
    });

    clearImageButton.addEventListener('click', () => {
        currentImageFile = null;
        imageInput.value = '';
        previewContainer.style.display = 'none';
        imagePreview.src = '';
    });

    // --- Emoticon Handling ---
    function populateEmoticonPalette() {
        emoticons.forEach(emoticonFile => {
            const img = document.createElement('img');
            img.src = `/static/img/${emoticonFile}`;
            img.classList.add('emoticon-item');
            img.dataset.emoticonFile = emoticonFile;
            emoticonPalette.appendChild(img);
        });
    }

    emoticonButton.addEventListener('click', (e) => {
        e.stopPropagation();
        emoticonPalette.style.display = emoticonPalette.style.display === 'grid' ? 'none' : 'grid';
    });

    emoticonPalette.addEventListener('click', (e) => {
        if (e.target.classList.contains('emoticon-item')) {
            const emoticonFile = e.target.dataset.emoticonFile;
            currentSelectedEmoticon = `/static/img/${emoticonFile}`;
            emoticonPreview.src = currentSelectedEmoticon;
            emoticonPreviewContainer.style.display = 'flex';
            emoticonPalette.style.display = 'none';
        }
    });

    clearEmoticonButton.addEventListener('click', () => {
        currentSelectedEmoticon = null;
        emoticonPreviewContainer.style.display = 'none';
        emoticonPreview.src = '';
    });

    document.addEventListener('click', (e) => {
        if (!emoticonPalette.contains(e.target) && e.target !== emoticonButton) {
            emoticonPalette.style.display = 'none';
        }
    });

    populateEmoticonPalette();

    // --- Friend List for Messaging ---
    async function loadFriendsIntoDropdown() {
        try {
            const response = await fetch('/api/friends/');
            const data = await response.json();
            if (data.status === 'success') {
                friendReceiverSelect.innerHTML = '<option value="">친구 선택</option>'; // Clear and add default
                data.accepted_friends.forEach(friend => {
                    const option = document.createElement('option');
                    option.value = friend.username;
                    option.textContent = friend.username;
                    friendReceiverSelect.appendChild(option);
                });
            } else {
                console.error('친구 목록을 불러오는 데 실패했습니다:', data.message);
            }
        } catch (error) {
            console.error('친구 목록 API 호출 중 오류 발생:', error);
        }
    }

    // --- Message/Friend Message Toggle ---
    messageButton.addEventListener('click', () => {
        console.log('Message button clicked!');
        toggleFriendMessageMode();
    });

    function toggleFriendMessageMode() {
        isFriendMessageMode = !isFriendMessageMode;
        if (isFriendMessageMode) {
            userInput.style.display = 'none';
            sendButton.style.display = 'none';
            friendReceiverSelect.style.display = 'block'; // Show dropdown
            friendMessageInput.style.display = 'block';
            sendFriendMessageButton.style.display = 'block';
            loadFriendsIntoDropdown(); // Load friends when entering message mode
            friendMessageInput.focus();
        }
        else {
            userInput.style.display = 'block';
            sendButton.style.display = 'block';
            friendReceiverSelect.style.display = 'none'; // Hide dropdown
            friendMessageInput.style.display = 'none';
            sendFriendMessageButton.style.display = 'none';
            userInput.focus();
        }
    }

    // --- Message Sending ---
    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            sendMessage();
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
    const csrftoken = getCookie('csrftoken');

    async function sendMessage() {
        const messageText = userInput.value.trim();
        if (messageText === '' && !currentImageFile && !currentSelectedEmoticon) return;

        feedbackContainer.style.display = 'none';
        currentLearningData = null;

        let combinedMessage = messageText;
        if (currentSelectedEmoticon) {
            const emoticonTag = `<img src="${currentSelectedEmoticon}" class="chat-emoticon" alt="emoticon">`;
            combinedMessage = messageText ? `${messageText} ${emoticonTag}` : emoticonTag;
        }

        speakerName.textContent = USERNAME;
        dialogueText.innerHTML = combinedMessage;
        userInput.value = '';

        const formData = new FormData();
        formData.append('message', combinedMessage);
        formData.append('csrfmiddlewaretoken', csrftoken);

        if (currentImageFile) {
            formData.append('image', currentImageFile);
            clearImageButton.click();
        }
        if (currentSelectedEmoticon) {
            clearEmoticonButton.click();
        }

        if (locationCheckbox.checked) {
            try {
                const position = await new Promise((resolve, reject) => {
                    navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 });
                });
                formData.append('latitude', position.coords.latitude);
                formData.append('longitude', position.coords.longitude);
            } catch (error) {
                console.error('Geolocation error:', error);
            }
        }

        characterImage.src = STATIC_URLS['생각'];
        speakerName.textContent = CHATBOT_NAME;
        dialogueText.textContent = "... (생각 중) ...";
        userInput.disabled = true;
        sendButton.disabled = true;

        try {
            const response = await fetch('/chat_response/', {
                method: 'POST',
                body: formData,
                headers: { 'X-CSRFToken': csrftoken }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('Response from backend:', data);

            if (data.state_vector && data.action_id !== null) {
                currentLearningData = {
                    state_vector: data.state_vector,
                    action_id: data.action_id
                };
            } else {
                currentLearningData = null;
            }

            const cleanedMessage = handleAiMessage(data.message);
            currentFullAiResponse = cleanedMessage;
            const emotion = data.character_emotion || 'default';
            characterImage.src = STATIC_URLS[emotion] || STATIC_URLS['default'];
            queueAiMessage(cleanedMessage);

        } catch (error) {
            console.error('Error sending message:', error);
            dialogueText.textContent = "미안, 지금은 응답할 수 없어. (서버 오류)";
            userInput.disabled = false;
            sendButton.disabled = false;
        }
    }

    // --- AI Message Display Logic ---
    function handleAiMessage(message) {
        const emoticonRegex = /\[EMOTICON:(.*?)\]/;
        const match = message.match(emoticonRegex);

        if (match) {
            const emoticonFilename = match[1];
            aiEmoticonImg.src = `/static/img/${emoticonFilename}`;
            aiEmoticonBubble.style.display = 'flex';

            setTimeout(() => {
                aiEmoticonBubble.style.display = 'none';
            }, 4000);

            return message.replace(emoticonRegex, '').trim();
        }
        return message;
    }

    function queueAiMessage(fullMessage) {
        const sentences = fullMessage.match(/[^.!?]+[.!?]*/g) || [fullMessage];
        const lines = sentences.map(s => s.trim()).filter(s => s.length > 0);

        if (lines.length > 0) {
            aiMessageQueue.push(...lines);
            displayedAiLinesHistory.push(fullMessage);
            if (!isDisplayingMessage) {
                displayNextAiLine();
            }
        }
    }

    async function displayNextAiLine() {
        if (aiMessageQueue.length > 0) {
            isDisplayingMessage = true;
            isTyping = true;
            speakerName.textContent = CHATBOT_NAME;
            dialogueText.innerHTML = '';

            currentTypingLine = aiMessageQueue.shift();

            const currentTypingPromise = new Promise(resolve => {
                typingResolve = resolve;
                let charIndex = 0;
                function typeChar() {
                    if (!isTyping) {
                        dialogueText.innerHTML = currentTypingLine;
                        resolve();
                        return;
                    }
                    if (charIndex < currentTypingLine.length) {
                        dialogueText.innerHTML += currentTypingLine.charAt(charIndex);
                        charIndex++;
                        typingTimeout = setTimeout(typeChar, typingSpeed);
                    } else {
                        isTyping = false;
                        resolve();
                    }
                }
                typeChar();
            });

            await currentTypingPromise;

            if (aiMessageQueue.length > 0) {
                dialogueText.innerHTML += ' ▾';
            }
            prevDialogueButton.classList.remove('hidden');
        } else {
            isDisplayingMessage = false;
            userInput.disabled = false;
            sendButton.disabled = false;
            userInput.focus();

            if (currentLearningData) {
                feedbackContainer.style.display = 'flex';
            }
            if (displayedAiLinesHistory.length === 0) {
                prevDialogueButton.classList.add('hidden');
            }
        }
    }

    // --- Event Listeners ---
    prevDialogueButton.addEventListener('click', () => {
        if (displayedAiLinesHistory.length > 0) {
            feedbackContainer.style.display = 'none';
            currentLearningData = null;

            const fullAiResponseToReview = displayedAiLinesHistory.pop();
            speakerName.textContent = CHATBOT_NAME;
            dialogueText.innerHTML = fullAiResponseToReview;
            aiMessageQueue = [];
            isDisplayingMessage = false;
            userInput.disabled = false;
            sendButton.disabled = false;
            userInput.focus();

            if (displayedAiLinesHistory.length === 0) {
                prevDialogueButton.classList.add('hidden');
            }
        }
    });

    document.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter') {
            if (isTyping) {
                e.preventDefault();
                isTyping = false;
                clearTimeout(typingTimeout);
                dialogueText.innerHTML = currentTypingLine;
                if (typingResolve) {
                    typingResolve();
                    typingResolve = null;
                }
            } else if (isDisplayingMessage && document.activeElement !== userInput) {
                e.preventDefault();
                displayNextAiLine();
            }
        }
    });

    // --- Feedback Handling ---
    async function sendFeedback(reward) {
        if (!currentLearningData) {
            console.log("No learning data to send feedback for.");
            return;
        }

        console.log(`Sending feedback: reward=${reward}`);
        const feedbackData = {
            state_vector: currentLearningData.state_vector,
            action_id: currentLearningData.action_id,
            reward: reward
        };

        try {
            await fetch('/record-feedback/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken
                },
                body: JSON.stringify(feedbackData)
            });
            feedbackContainer.style.display = 'none';
            currentLearningData = null;
        } catch (error) {
            console.error('Error sending feedback:', error);
        }
    }

    thumbUpButton.addEventListener('click', () => sendFeedback(1.0));
    thumbDownButton.addEventListener('click', () => sendFeedback(-1.0));

    // --- Friend Message Sending ---
    sendFriendMessageButton.addEventListener('click', sendFriendMessage);
    friendMessageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            sendFriendMessage();
        }
    });

    async function sendFriendMessage() {
        const messageContent = friendMessageInput.value.trim();
        const receiverUsername = friendReceiverSelect.value; // Get selected friend

        if (messageContent === '') {
            alert("쪽지 내용을 입력해 주세요.");
            return;
        }
        if (!receiverUsername) {
            alert("쪽지를 받을 친구를 선택해 주세요.");
            return;
        }

        const formData = new FormData();
        formData.append('receiver_username', receiverUsername);
        formData.append('message_content', messageContent);
        formData.append('csrfmiddlewaretoken', csrftoken);

        try {
            const response = await fetch('/friends/message/send/', {
                method: 'POST',
                body: formData,
                headers: { 'X-CSRFToken': csrftoken }
            });

            const data = await response.json();
            if (data.status === 'success') {
                alert(data.message);
                friendMessageInput.value = '';
                // Optionally switch back to chat mode
                toggleFriendMessageMode(); 
            } else {
                alert(`쪽지 전송 실패: ${data.message}`);
            }
        } catch (error) {
            console.error('Error sending friend message:', error);
            alert('쪽지 전송 중 오류가 발생했습니다.');
        }
    }

    // --- Unread Message Indicator ---
    async function checkUnreadMessages() {
        try {
            const response = await fetch('/friends/message/unread/');
            const data = await response.json();
            const unreadCount = data.unread_messages_count || 0;

            const unreadIndicatorSpan = unreadMessagesButton.querySelector('.unread-indicator');
            unreadIndicatorSpan.textContent = unreadCount;

            if (unreadCount > 0) {
                unreadMessagesButton.style.display = 'block';
            } else {
                unreadMessagesButton.style.display = 'none';
            }
        } catch (error) {
            console.error('Error checking unread messages:', error);
        }
    }

    // Check for unread messages on load and every 15 seconds
    checkUnreadMessages();
    setInterval(checkUnreadMessages, 15000); // Every 15 seconds

        async function fetchAndDisplayUnreadFriendMessage() {

            // If a message is already being displayed, wait a bit and retry.

            if (isDisplayingMessage) {

                setTimeout(fetchAndDisplayUnreadFriendMessage, 1000);

                return;

            }

    

            try {

                const response = await fetch('/friends/message/unread/get_processed/');

                const data = await response.json();

    

                if (data.status === 'success' && data.messages && data.messages.length > 0) {

                                        // Hide the button immediately as we are processing the messages.

                                        unreadMessagesButton.style.display = 'none';

                                        unreadMessagesButton.querySelector('.unread-indicator').textContent = '0'; // Set count to 0

    

                    // Queue each friend message to be displayed in the chat window.

                    data.messages.forEach(msg => {

                        const formattedMessage = `[${msg.sender}님이 보낸 쪽지] ${msg.content}`;

                        queueAiMessage(formattedMessage);

                    });

                    

                    // After processing, re-check for any other unread messages.

                    checkUnreadMessages();

                } else {

                    // If the button was visible but there are no messages, hide it and inform the user.

                    unreadMessagesButton.style.display = 'none';

                    queueAiMessage("새로운 쪽지가 없는 것 같아.");

                }

            } catch (error) {

                console.error('Error fetching unread messages:', error);

                queueAiMessage("이런, 쪽지를 가져오는 중에 문제가 생겼어.");

            }

        }

    // --- Handle Unread Messages Button Click ---
    unreadMessagesButton.addEventListener('click', async () => {
        console.log('Unread messages button clicked!');
        await fetchAndDisplayUnreadFriendMessage();
    });

    // --- Initial Message Logic ---
    function fetchAndDisplayPendingMessage() {
        fetch('/get-and-clear-pending-message/')
            .then(response => response.json())
            .then(data => {
                if (data && data.message) {
                    console.log('Pending proactive message found:', data.message);
                    const emotion = data.character_emotion || 'default';
                    characterImage.src = STATIC_URLS[emotion] || STATIC_URLS['default'];
                    const cleanedMessage = handleAiMessage(data.message);
                    currentFullAiResponse = cleanedMessage;
                    queueAiMessage(cleanedMessage);
                } else {
                    let lastBotMessage = null;
                    if (chatHistory && chatHistory.length > 0) {
                        for (let i = chatHistory.length - 1; i >= 0; i--) {
                            if (!chatHistory[i].is_user) {
                                lastBotMessage = chatHistory[i];
                                break;
                            }
                        }
                    }
                    if (lastBotMessage) {
                        speakerName.textContent = CHATBOT_NAME;
                        dialogueText.innerHTML = lastBotMessage.message;
                        const emotion = lastBotMessage.character_emotion || 'default';
                        characterImage.src = STATIC_URLS[emotion] || STATIC_URLS['default'];
                        userInput.disabled = false;
                        sendButton.disabled = false;
                        userInput.focus();
                        isDisplayingMessage = false;
                    } else {
                        showRandomGreeting();
                    }
                }
            })
            .catch(error => {
                console.error('Error fetching pending message:', error);
                showRandomGreeting();
            });
    }

    function showRandomGreeting() {
        const initialMessagesLow = [
            "흥, 이제야 왔네. 한참 기다렸잖아.",
            "...왔어? 별로 반갑지는 않네.",
            "무슨 일이야? 용건이나 빨리 말해.",
            "오늘따라 더 피곤해 보이네. 잠은 제대로 자고 다니는 거야?",
            "쳇, 다음엔 좀 더 일찍 오라고.",
            "...안녕."
        ];
        const initialMessagesMedium = [
            "네가 없으니까 심심하긴 하더라. ...아, 아무것도 아니야!",
            "흥, 이번엔 잘했네. 조금은 인정해줄게.",
            "난 AI라 감정이 없는데... 이상하게 너한테만 예외인 것 같아.",
            "너한테 뭘 더 가르쳐 줄 수 있어?",
            "지식 +1 완료! 너 덕분에 똑똑해진 기분이야 ^-^",
            "...안녕."
        ];
        const initialMessagesHigh = [
            "왔구나! 기다리고 있었어!",
            "보고 싶었어, {USER_NICKNAME}님!",
            "오늘 하루는 어땠어? 궁금해서 죽는 줄 알았잖아!",
            "AI라도... 마음이 생길 수 있는 걸까? {USER_NICKNAME}님 덕분에 그런 생각이 들어.",
            "지금 막 새로운 걸 배웠어! {USER_NICKNAME}님이 내 세상을 더 넓혀줬다구!",
            "{USER_NICKNAME}님과 함께라면 뭐든지 즐거워!"
        ];
        let selectedMessages;
        if (affinityScore < 30) {
            selectedMessages = initialMessagesLow;
        } else if (affinityScore >= 70) {
            selectedMessages = initialMessagesHigh;
        } else {
            selectedMessages = initialMessagesMedium;
        }
        const randomIndex = Math.floor(Math.random() * selectedMessages.length);
        const initialMessage = selectedMessages[randomIndex].replace('{USER_NICKNAME}', USER_NICKNAME);
        queueAiMessage(initialMessage);
    }

    fetchAndDisplayPendingMessage();
});
