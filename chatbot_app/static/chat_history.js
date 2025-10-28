document.addEventListener('DOMContentLoaded', function() {
    const chatLog = document.getElementById('chat-log');
    
    let currentPage = 2;
    let isLoading = false;
    let hasNextPage = chatLog.dataset.hasNextPage === 'true';

    function getValidDate(timestamp) {
        const date = new Date(timestamp);
        return !isNaN(date.getTime()) ? date : null;
    }

    function createMessageDiv(msg) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', msg.is_user ? 'user-message' : 'bot-message');
        messageDiv.dataset.timestamp = msg.timestamp;

        const contentWrapper = document.createElement('div');
        contentWrapper.style.display = 'flex';
        contentWrapper.style.flexDirection = 'column';
        contentWrapper.style.alignItems = 'flex-start';

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

        const time = getValidDate(msg.timestamp);
        let timeString = '';
        if (time) {
            timeString = `(${(time.getHours()).toString().padStart(2, '0')}:${(time.getMinutes()).toString().padStart(2, '0')})`;
        }
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
            const date = getValidDate(msgTimestamp);

            if (!date) {
                return;
            }

            let formattedDate = `[${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일]`;

            if (lastDate !== formattedDate) {
                const separatorDiv = document.createElement('div');
                separatorDiv.classList.add('date-separator');
                separatorDiv.textContent = formattedDate;
                chatLog.insertBefore(separatorDiv, message);
                lastDate = formattedDate;
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

    chatLog.addEventListener('scroll', async () => {
        if (chatLog.scrollTop === 0 && !isLoading && hasNextPage) {
            isLoading = true;
            try {
                const response = await fetch(`/chat_history/load-messages/?page=${currentPage}`);
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

    // 초기 로드 시 메시지 표시
    if (typeof chatHistory !== 'undefined' && chatHistory) {
        displayMessages(chatHistory);
    } else {
        updateDateSeparators();
        chatLog.scrollTop = chatLog.scrollHeight;
    }
});