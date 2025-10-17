document.addEventListener('DOMContentLoaded', function() {
    console.log('script.js loaded and DOMContentLoaded fired.'); // 이 줄 추가
    const chatLog = document.getElementById('chat-log');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const imageInput = document.getElementById('image-input');
    const attachImageButton = document.getElementById('attach-image-button');
    const imagePreview = document.getElementById('image-preview');
    const clearImageButton = document.getElementById('clear-image-button');
    let selectedImageBase64 = null; // 선택된 이미지의 Base64 문자열을 저장

    console.log('imageInput element:', imageInput); // 이 줄 추가
    console.log('attachImageButton element:', attachImageButton); // 이 줄 추가

    console.log("Found sendButton element:", sendButton); // 이 줄 추가
    const chatbotCharacter = document.getElementById('chatbot-character');

    let currentPage = 2;
    let isLoading = false;
    let hasNextPage = chatLog.dataset.hasNextPage === 'true';

    attachImageButton.addEventListener('click', () => {
        console.log('Attach image button clicked!'); // 이 줄 추가
        imageInput.click(); // 이미지 첨부 버튼 클릭 시 실제 파일 입력 필드 클릭
    });
    console.log('Attach image button listener attached.'); // 이 줄 추가

    const previewContainer = document.getElementById('preview-container'); // 새 컨테이너 가져오기

    clearImageButton.addEventListener('click', () => {
        clearImageSelection();
    });

    imageInput.addEventListener('change', (event) => {
        const file = event.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (e) => {
                imagePreview.src = e.target.result;
                previewContainer.style.display = 'block'; // 컨테이너를 보여줌
                selectedImageBase64 = e.target.result.split(',')[1]; // Base64 부분만 저장
            };
            reader.readAsDataURL(file);
        } else {
            clearImageSelection();
        }
    });

    function clearImageSelection() {
        imagePreview.src = '';
        previewContainer.style.display = 'none'; // 컨테이너를 숨김
        selectedImageBase64 = null;
        imageInput.value = ''; // 파일 입력 필드 초기화
    }

    // --- 로직 함수 ---
    function createMessageDiv(msg) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', msg.is_user ? 'user-message' : 'bot-message');
        messageDiv.dataset.timestamp = msg.timestamp;

        const contentWrapper = document.createElement('div'); // 이미지와 텍스트를 감싸는 래퍼
        contentWrapper.style.display = 'flex';
        contentWrapper.style.flexDirection = 'column';
        contentWrapper.style.alignItems = 'flex-start'; // 텍스트와 이미지를 왼쪽 정렬 (메시지 버블 내에서)

        // 이미지 데이터가 있으면 이미지 태그를 추가
        if (msg.image_b64_data) {
            const img = document.createElement('img');
            img.src = `data:image/jpeg;base64,${msg.image_b64_data}`;
            img.style.maxWidth = '100%'; // 이미지가 메시지 영역을 넘지 않도록
            img.style.height = 'auto';
            img.style.marginBottom = '5px'; // 메시지 텍스트와의 간격
            img.style.borderRadius = '8px'; // 이미지 모서리 둥글게
            contentWrapper.appendChild(img);
        }

        const p = document.createElement('p');
        p.textContent = msg.message;
        contentWrapper.appendChild(p); // 텍스트를 래퍼에 추가

        messageDiv.appendChild(contentWrapper); // 래퍼를 메시지 div에 추가

        const time = new Date(msg.timestamp);
        const timeString = `(${(time.getHours()).toString().padStart(2, '0')}:${(time.getMinutes()).toString().padStart(2, '0')})`;
        const timeSpan = document.createElement('span');
        timeSpan.classList.add('timestamp');
        timeSpan.textContent = timeString;
        messageDiv.appendChild(timeSpan); // 타임스탬프는 메시지 div에 직접 추가 (flex 아이템으로)
        
        return messageDiv;
    }

    function updateDateSeparators() {
        // 기존 구분선 모두 제거
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
        const imageToSend = selectedImageBase64; // 1. 전송할 이미지 데이터를 임시 변수에 복사

        // 2. 보낼 내용이 없으면 아무것도 하지 않음
        if (messageText === '' && !imageToSend) return;

        // 3. 사용자 메시지를 화면에 먼저 표시
        const userMessage = { message: messageText, is_user: true, timestamp: new Date().toISOString() };
        if (imageToSend) {
            userMessage.image_b64_data = imageToSend;
        }
        displayMessages([userMessage]);

        // 4. 입력 UI를 즉시 초기화 (사용자 경험 향상)
        userInput.value = '';
        clearImageSelection(); 
        
        // 5. 챗봇 상태를 '생각 중'으로 변경
        chatbotCharacter.src = STATIC_URLS['생각'] || STATIC_URLS.default;

        // 6. 위치 정보와 함께, 임시 변수에 저장해 둔 이미지 데이터를 서버로 전송
        const locationCheckbox = document.getElementById('location-checkbox');
        if (locationCheckbox.checked) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    const { latitude, longitude } = position.coords;
                    fetchChatResponse(messageText, latitude, longitude, imageToSend);
                },
                (error) => {
                    console.error('Geolocation error:', error);
                    fetchChatResponse(messageText, null, null, imageToSend);
                }
            );
        } else {
            fetchChatResponse(messageText, null, null, imageToSend);
        }
    }

    async function fetchChatResponse(messageText, latitude, longitude, image_b64_data) { // image_b64_data 매개변수 추가
        try {
            const payload = {
                message: messageText,
            };
            if (latitude && longitude) {
                payload.latitude = latitude;
                payload.longitude = longitude;
            }
            if (image_b64_data) { // 이미지 데이터가 있으면 페이로드에 추가
                payload.image_b64_data = image_b64_data;
            }

            const response = await fetch('/chat_response/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
                body: JSON.stringify(payload)
            });
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

            const data = await response.json();
            const botMessage = { message: data.message, is_user: false, timestamp: data.timestamp };
            
            setTimeout(() => {
                displayMessages([botMessage]);
                chatbotCharacter.src = STATIC_URLS[data.character_emotion] || STATIC_URLS.default;
            }, 500);
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
        displayMessages(chatHistory);
    } else {
        chatLog.scrollTop = chatLog.scrollHeight;
    }
});