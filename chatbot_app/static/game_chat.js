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

    const locationCheckbox = document.getElementById('location-checkbox');

    let aiMessageQueue = [];
    let displayedAiLinesHistory = []; // Stores full AI responses
    let isDisplayingMessage = false;
    let currentImageFile = null;
    let currentFullAiResponse = ""; // To store the full AI response for history

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
        if (messageText === '' && !currentImageFile) return;

        // Clear history for new interaction
        displayedAiLinesHistory = [];
        prevDialogueButton.classList.add('hidden');

        // Display user message immediately
        speakerName.textContent = USERNAME; // Defined in the HTML template
        dialogueText.textContent = messageText;
        userInput.value = '';

        const formData = new FormData();
        formData.append('message', messageText);
        formData.append('csrfmiddlewaretoken', csrftoken);

        if (currentImageFile) {
            formData.append('image', currentImageFile);
            clearImageButton.click(); // Clear preview after attaching
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
            
            // Store the full AI response for history
            currentFullAiResponse = data.message;

            // Update character emotion
            const emotion = data.character_emotion || 'default';
            characterImage.src = STATIC_URLS[emotion] || STATIC_URLS['default'];

            // Queue up AI message for line-by-line display
            queueAiMessage(data.message);

        } catch (error) {
            console.error('Error sending message:', error);
            dialogueText.textContent = "미안, 지금은 응답할 수 없어. (서버 오류)";
        }
    }

    // --- AI Message Display Logic ---
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
            dialogueText.textContent = line;
            // Show a visual indicator that there's more to come
            if (aiMessageQueue.length > 0) {
                dialogueText.textContent += ' ▾';
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
            dialogueText.textContent = fullAiResponseToReview;
            
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

    // Initial message display from history if any
    if (chatHistory.length > 0) {
        const lastMessage = chatHistory[chatHistory.length - 1];
        if (!lastMessage.is_user) {
            dialogueText.textContent = lastMessage.message;
        }
    } else {
        dialogueText.textContent = "... (삐빅) ... 흥, 드디어 왔네. 뭘 시킬 셈이야?";
    }
});
