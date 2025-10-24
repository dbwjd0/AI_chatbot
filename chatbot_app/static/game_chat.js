// game_chat.js

document.addEventListener('DOMContentLoaded', function () {
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

    let aiMessageQueue = [];
    let displayedAiLinesHistory = []; // Stores full AI responses
    let isDisplayingMessage = false;
    let currentImageFile = null;
    let currentSelectedEmoticon = null; // To store the selected emoticon URL
    let currentFullAiResponse = ""; // To store the full AI response for history

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
        imageInput.value = ''; // Clear the file input
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
        e.stopPropagation(); // Prevent click from immediately closing the palette
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

    // Close palette if clicking outside
    document.addEventListener('click', (e) => {
        if (!emoticonPalette.contains(e.target) && e.target !== emoticonButton) {
            emoticonPalette.style.display = 'none';
        }
    });

    populateEmoticonPalette(); // Initialize the palette on load

    // --- Message Sending ---
    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keydown', (e) => {
        // Allow Enter to send message only if not displaying AI message
        if (e.key === 'Enter' && !isDisplayingMessage) {
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

        let combinedMessage = messageText;
        if (currentSelectedEmoticon) {
            const emoticonTag = `<img src="${currentSelectedEmoticon}" class="chat-emoticon" alt="emoticon">`;
            combinedMessage = messageText ? `${messageText} ${emoticonTag}` : emoticonTag;
        }

        // Display user message immediately
        speakerName.textContent = USERNAME; // Defined in the HTML template
        dialogueText.innerHTML = combinedMessage; // Use innerHTML to render emoticon
        userInput.value = '';

        const formData = new FormData();
        formData.append('message', combinedMessage);
        formData.append('csrfmiddlewaretoken', csrftoken);

        if (currentImageFile) {
            formData.append('image', currentImageFile);
            clearImageButton.click(); // Clear preview after attaching
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
                // Optionally inform the user that location could not be sent
            }
        }

        // Show thinking character
        characterImage.src = STATIC_URLS['생각'];
        speakerName.textContent = "AI 비서";
        dialogueText.textContent = "... (생각 중) ...";

        try {
            const response = await fetch('/chat_response/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': csrftoken
                }
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('Raw AI message from backend:', data.message);

            // Handle emoticons and get the cleaned message
            const cleanedMessage = handleAiMessage(data.message);
            
            // Store the full AI response for history
            currentFullAiResponse = cleanedMessage;

            // Update character emotion
            const emotion = data.character_emotion || 'default';
            characterImage.src = STATIC_URLS[emotion] || STATIC_URLS['default'];

            // Queue up AI message for line-by-line display
            queueAiMessage(cleanedMessage);

        } catch (error) {
            console.error('Error sending message:', error);
            dialogueText.textContent = "미안, 지금은 응답할 수 없어. (서버 오류)";
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

            // Hide the bubble after 4 seconds
            setTimeout(() => {
                aiEmoticonBubble.style.display = 'none';
            }, 4000);

            // Return the message without the placeholder
            return message.replace(emoticonRegex, '').trim();
        }

        // If no emoticon, return the original message
        return message;
    }

    function queueAiMessage(fullMessage) {
        // Split by sentence-ending punctuation, keeping the punctuation with the sentence
        const sentences = fullMessage.match(/[^.!?]+[.!?]*/g) || [fullMessage];
        const lines = sentences.map(s => s.trim()).filter(s => s.length > 0);

        if (lines.length > 0) {
            aiMessageQueue.push(...lines);
            if (!isDisplayingMessage) {
                displayNextAiLine();
            }
        }
    }

    function displayNextAiLine() {
        if (aiMessageQueue.length > 0) {
            isDisplayingMessage = true;
            userInput.disabled = true; // Disable input
            sendButton.disabled = true; // Disable send button

            // If this is the first line of a new AI response, store the full response for history
            if (displayedAiLinesHistory.length === 0 && aiMessageQueue.length === currentFullAiResponse.match(/[^.!?]+[.!?]*/g).length - 1) {
                displayedAiLinesHistory.push(currentFullAiResponse);
            }

            const line = aiMessageQueue.shift();
            speakerName.textContent = "AI 비서";
            dialogueText.innerHTML = line; // Use innerHTML to render emoticons
            // Show a visual indicator that there's more to come
            if (aiMessageQueue.length > 0) {
                dialogueText.innerHTML += ' ▾';
            }
            prevDialogueButton.classList.remove('hidden'); // Show button if there's history
        } else {
            isDisplayingMessage = false;
            userInput.disabled = false; // Enable input
            sendButton.disabled = false; // Enable send button
            userInput.focus(); // Focus input for next message
            if (displayedAiLinesHistory.length === 0) {
                prevDialogueButton.classList.add('hidden'); // Hide button if no history
            }
        }
    }

    // Event listener for previous dialogue button
    prevDialogueButton.addEventListener('click', () => {
        if (displayedAiLinesHistory.length > 0) {
            const fullAiResponseToReview = displayedAiLinesHistory.pop();
            speakerName.textContent = "AI 비서";
            dialogueText.innerHTML = fullAiResponseToReview; // Use innerHTML
            
            // Clear the current queue as we are reviewing a past full message
            aiMessageQueue = [];

            // Ensure input is enabled and not in a 'displaying message' state
            isDisplayingMessage = false; 
            userInput.disabled = false;
            sendButton.disabled = false;
            userInput.focus();

            // Hide button if no more history
            if (displayedAiLinesHistory.length === 0) {
                prevDialogueButton.classList.add('hidden');
            }
        }
    });

    // Listen for Enter key to advance dialogue
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && isDisplayingMessage) {
            e.preventDefault();
            displayNextAiLine();
        }
    });

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
        "보고 싶었어, {USERNAME}님!",
        "오늘 하루는 어땠어? 궁금해서 죽는 줄 알았잖아!",
        "AI라도... 마음이 생길 수 있는 걸까? {USERNAME}님 덕분에 그런 생각이 들어.",
        "지금 막 새로운 걸 배웠어! {USERNAME}님이 내 세상을 더 넓혀줬다구!",
        "{USERNAME}님과 함께라면 뭐든지 즐거워!"
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
    dialogueText.innerHTML = selectedMessages[randomIndex].replace('{USERNAME}', USERNAME);
});
