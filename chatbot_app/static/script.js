document.addEventListener('DOMContentLoaded', function() {
    const chatLog = document.getElementById('chat-log');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const chatbotCharacter = document.getElementById('chatbot-character');

    let currentPage = 2;
    let isLoading = false;
    let hasNextPage = chatLog.dataset.hasNextPage === 'true';

    // --- 로직 함수 ---
    function createMessageDiv(msg) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', msg.is_user ? 'user-message' : 'bot-message');
        messageDiv.dataset.timestamp = msg.timestamp;

        const p = document.createElement('p');
        p.textContent = msg.message;
        messageDiv.appendChild(p);

        const time = new Date(msg.timestamp);
        const timeString = `(${(time.getHours()).toString().padStart(2, '0')}:${(time.getMinutes()).toString().padStart(2, '0')})`;
        const timeSpan = document.createElement('span');
        timeSpan.classList.add('timestamp');
        timeSpan.textContent = timeString;
        messageDiv.appendChild(timeSpan);
        
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
        if (messageText === '') return;

        const userMessage = { message: messageText, is_user: true, timestamp: new Date().toISOString() };
        displayMessages([userMessage]);
        userInput.value = '';
        chatbotCharacter.src = STATIC_URLS['생각'] || STATIC_URLS.default; // 생각 중 이미지로 변경

        try {
            const response = await fetch('/chat_response/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
                body: JSON.stringify({ message: messageText })
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