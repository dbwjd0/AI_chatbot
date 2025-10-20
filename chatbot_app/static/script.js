document.addEventListener('DOMContentLoaded', function() {
    const chatLog = document.getElementById('chat-log');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const imageInput = document.getElementById('image-input');
    const attachImageButton = document.getElementById('attach-image-button');
    const imagePreview = document.getElementById('image-preview');
    const clearImageButton = document.getElementById('clear-image-button');
    const previewContainer = document.getElementById('preview-container');
    
    let selectedImageFile = null; // 선택된 이미지 파일을 저장

    const chatbotCharacter = document.getElementById('chatbot-character');

    let currentPage = 2;
    let isLoading = false;
    let hasNextPage = chatLog.dataset.hasNextPage === 'true';

    attachImageButton.addEventListener('click', () => imageInput.click());

    clearImageButton.addEventListener('click', () => clearImageSelection());

    imageInput.addEventListener('change', (event) => {
        const file = event.target.files[0];
        if (file) {
            selectedImageFile = file; // 파일 객체 저장
            const reader = new FileReader();
            reader.onload = (e) => {
                imagePreview.src = e.target.result;
                previewContainer.style.display = 'block';
            };
            reader.readAsDataURL(file); // 미리보기용으로만 사용
        } else {
            clearImageSelection();
        }
    });

    function clearImageSelection() {
        imagePreview.src = '';
        previewContainer.style.display = 'none';
        selectedImageFile = null;
        imageInput.value = '';
    }

    // --- 로직 함수 ---
    function createMessageDiv(msg) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', msg.is_user ? 'user-message' : 'bot-message');
        messageDiv.dataset.timestamp = msg.timestamp;

        const contentWrapper = document.createElement('div');
        contentWrapper.style.display = 'flex';
        contentWrapper.style.flexDirection = 'column';
        contentWrapper.style.alignItems = 'flex-start';

        // image_url을 사용하여 이미지 렌더링
        if (msg.image_url) {
            const img = document.createElement('img');
            img.src = msg.image_url;
            img.style.maxWidth = '100%';
            img.style.height = 'auto';
            img.style.marginBottom = '5px';
            img.style.borderRadius = '8px';
            contentWrapper.appendChild(img);
        }

        const p = document.createElement('p');
        p.textContent = msg.message;
        contentWrapper.appendChild(p);

        messageDiv.appendChild(contentWrapper);

        const time = new Date(msg.timestamp);
        const timeString = `(${(time.getHours()).toString().padStart(2, '0')}:${(time.getMinutes()).toString().padStart(2, '0')})`;
        const timeSpan = document.createElement('span');
        timeSpan.classList.add('timestamp');
        timeSpan.textContent = timeString;
        messageDiv.appendChild(timeSpan);
        
        return messageDiv;
    }

    function updateDateSeparators() {
        chatLog.querySelectorAll('.date-separator').forEach(el => el.remove());
        let lastDate = null;
        const messages = chatLog.querySelectorAll('.message');
        messages.forEach(message => {
            const msgTimestamp = message.dataset.timestamp;
            const msgDate = new Date(msgTimestamp).toDateString();
            if (lastDate !== msgDate) {
                const date = new Date(msgTimestamp);
                const formattedDate = `[${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일]`;
                const separatorDiv = document.createElement('div');
                separatorDiv.classList.add('date-separator');
                separatorDiv.textContent = formattedDate;
                chatLog.insertBefore(separatorDiv, message);
                lastDate = msgDate;
            }
        });
    }

    function displayMessages(messages, prepend = false) {
        const scrollHeightBefore = chatLog.scrollHeight;
        messages.forEach(msg => {
            const messageEl = createMessageDiv(msg);
            if (prepend) {
                chatLog.insertBefore(messageEl, chatLog.firstChild);
            } else {
                chatLog.appendChild(messageEl);
            }
        });
        updateDateSeparators();
        if (prepend) {
            chatLog.scrollTop = chatLog.scrollHeight - scrollHeightBefore;
        } else {
            chatLog.scrollTop = chatLog.scrollHeight;
        }
    }

    // --- 이벤트 리스너 및 초기화 ---
    chatLog.addEventListener('scroll', async () => {
        if (chatLog.scrollTop === 0 && !isLoading && hasNextPage) {
            isLoading = true;
            try {
                const response = await fetch(`/chat/load-messages/?page=${currentPage}`);
                const data = await response.json();
                if (data.messages.length > 0) {
                    displayMessages(data.messages, true);
                    currentPage++;
                }
                hasNextPage = data.has_next_page;
            } catch (error) {
                console.error('Error loading more messages:', error);
            }
            isLoading = false;
        }
    });

    async function sendMessage() {
        const messageText = userInput.value.trim();
        const imageFile = selectedImageFile;

        if (messageText === '' && !imageFile) return;

        // 사용자 메시지를 화면에 먼저 표시 (미리보기용 URL 사용)
        const userMessage = { 
            message: messageText, 
            is_user: true, 
            timestamp: new Date().toISOString() 
        };
        if (imageFile) {
            userMessage.image_url = URL.createObjectURL(imageFile); // 임시 URL 생성
        }
        displayMessages([userMessage]);

        userInput.value = '';
        clearImageSelection();
        
        chatbotCharacter.src = STATIC_URLS['생각'] || STATIC_URLS.default;

        const locationCheckbox = document.getElementById('location-checkbox');
        if (locationCheckbox.checked) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    const { latitude, longitude } = position.coords;
                    fetchChatResponse(messageText, latitude, longitude, imageFile);
                },
                (error) => {
                    console.error('Geolocation error:', error);
                    fetchChatResponse(messageText, null, null, imageFile);
                }
            );
        } else {
            fetchChatResponse(messageText, null, null, imageFile);
        }
    }

    async function fetchChatResponse(messageText, latitude, longitude, imageFile) {
        try {
            const formData = new FormData();
            formData.append('message', messageText);

            if (latitude && longitude) {
                formData.append('latitude', latitude);
                formData.append('longitude', longitude);
            }
            if (imageFile) {
                formData.append('image', imageFile);
            }

            const response = await fetch('/chat_response/', {
                method: 'POST',
                headers: { 'X-CSRFToken': getCookie('csrftoken') }, // Content-Type은 브라우저가 자동으로 설정
                body: formData
            });
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

            const data = await response.json();

            // AI 응답 메시지 표시
            const botMessage = { 
                message: data.message, 
                is_user: false, 
                timestamp: data.timestamp 
            };
            displayMessages([botMessage]);

            // AI 캐릭터 감정 업데이트
            chatbotCharacter.src = STATIC_URLS[data.character_emotion] || STATIC_URLS.default;

            // 사용자가 보낸 이미지의 URL을 실제 서버 URL로 업데이트
            if (data.user_image_url) {
                const userMessages = chatLog.querySelectorAll('.user-message');
                const lastUserMessage = userMessages[userMessages.length - 1];
                const imgElement = lastUserMessage.querySelector('img');
                if (imgElement && imgElement.src.startsWith('blob:')) {
                    URL.revokeObjectURL(imgElement.src); // 기존 blob URL 메모리 해제
                    imgElement.src = data.user_image_url;
                }
            }

        } catch (error) {
            console.error('Error sending message:', error);
            const errorMessage = { message: '죄송합니다. 메시지를 처리하는 데 문제가 발생했습니다.', is_user: false, timestamp: new Date().toISOString() };
            displayMessages([errorMessage]);
            chatbotCharacter.src = STATIC_URLS.sad;
        }
    }

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

    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') sendMessage(); });

    // 초기화
    if (typeof chatHistory !== 'undefined' && chatHistory) {
        // 초기 로드 시에는 서버에서 image.url을 내려주므로 별도 처리가 필요 없음
        displayMessages(chatHistory);
    } else {
        chatLog.scrollTop = chatLog.scrollHeight;
    }
});