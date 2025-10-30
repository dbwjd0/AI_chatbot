// static/friend_management.js

document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('search-user-input');
    const sendRequestBtn = document.getElementById('send-request-btn');
    const searchMessage = document.getElementById('search-message');
    const pendingList = document.getElementById('pending-requests-list');
    const acceptedList = document.getElementById('accepted-friends-list');

    // CSRF 토큰을 쿠키에서 가져오는 함수 (Django 표준 방식)
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

    // ----------------------------------------------------
    // 1. 친구 요청 보내기
    // ----------------------------------------------------
    sendRequestBtn.addEventListener('click', function() {
        const targetUsername = searchInput.value.trim();
        if (!targetUsername) {
            searchMessage.textContent = "사용자 이름을 입력하세요.";
            searchMessage.style.color = 'red';
            return;
        }

        searchMessage.textContent = "요청 보내는 중...";
        searchMessage.style.color = 'orange';

        const formData = new FormData();
        formData.append('target_username', targetUsername);

        fetch('/friends/request/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrftoken
            },
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                searchMessage.textContent = data.message;
                searchMessage.style.color = 'green';
                searchInput.value = ''; // 성공 시 입력 필드 초기화
            } else {
                searchMessage.textContent = `오류: ${data.message}`;
                searchMessage.style.color = 'red';
            }
        })
        .catch(error => {
            console.error('친구 요청 오류:', error);
            searchMessage.textContent = '서버 통신 오류가 발생했습니다.';
            searchMessage.style.color = 'red';
        });
    });

    // ----------------------------------------------------
    // 2. 친구 요청 수락 처리
    // ----------------------------------------------------
    const handleAcceptRequest = (requestId) => {
        fetch(`/friends/accept/${requestId}/`, { // 🌟 수정된 URL 사용 🌟
            method: 'POST',
            headers: {
                'X-CSRFToken': csrftoken
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success' || data.status === 'info') {
                // 성공 또는 정보성 메시지일 경우 목록 새로고침
                loadFriendData(); 
            } else {
                // alert() 대신에 UI에 메시지를 표시하는 것이 더 좋습니다.
                console.error(`요청 수락 실패: ${data.message}`);
                // 여기서는 간단히 alert을 사용하여 사용자에게 피드백을 줍니다.
                alert(`요청 수락 실패: ${data.message}`); 
            }
        })
        .catch(error => {
            console.error('친구 요청 수락 오류:', error);
            alert('요청 수락 중 서버 통신 오류가 발생했습니다.');
        });
    };

    // ----------------------------------------------------
    // 2.1. 친구 요청 거절 처리
    // ----------------------------------------------------
    const handleRejectRequest = (requestId) => {
        fetch(`/friends/reject/${requestId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrftoken
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success' || data.status === 'info') {
                loadFriendData(); 
            } else {
                console.error(`요청 거절 실패: ${data.message}`);
                alert(`요청 거절 실패: ${data.message}`); 
            }
        })
        .catch(error => {
            console.error('친구 요청 거절 오류:', error);
            alert('요청 거절 중 서버 통신 오류가 발생했습니다.');
        });
    };

    // ----------------------------------------------------
    // 2.2. 친구 삭제 처리
    // ----------------------------------------------------
    const handleDeleteFriend = (friendshipId) => {
        if (!confirm('정말로 이 친구를 삭제하시겠습니까?')) {
            return;
        }
        fetch(`/friends/delete/${friendshipId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrftoken
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                loadFriendData();
            } else {
                console.error(`친구 삭제 실패: ${data.message}`);
                alert(`친구 삭제 실패: ${data.message}`);
            }
        })
        .catch(error => {
            console.error('친구 삭제 오류:', error);
            alert('친구 삭제 중 서버 통신 오류가 발생했습니다.');
        });
    };

    // ----------------------------------------------------
    // 3. 친구 목록 및 요청 목록 로드
    // ----------------------------------------------------
    function loadFriendData() {
        pendingList.innerHTML = '<li>데이터 로딩 중...</li>';
        acceptedList.innerHTML = '<li>데이터 로딩 중...</li>';
        
        fetch('/api/friends/') // 🌟 수정된 URL 사용 🌟
        .then(response => response.json())
        .then(data => {
            // 받은 친구 요청 목록 렌더링
            pendingList.innerHTML = '';
            if (data.pending_requests && data.pending_requests.length > 0) {
                data.pending_requests.forEach(req => {
                    const li = document.createElement('li');
                    li.innerHTML = `
                        <span class="user-name">${req.from_user_username}</span>
                        <button class="action-btn accept-btn" data-request-id="${req.id}">수락</button>
                    `;
                    pendingList.appendChild(li);
                });
                // 동적으로 생성된 버튼에 이벤트 리스너 할당
                pendingList.querySelectorAll('.accept-btn').forEach(button => {
                    button.addEventListener('click', (e) => {
                        handleAcceptRequest(e.target.dataset.requestId);
                    });
                });
                pendingList.querySelectorAll('.reject-btn').forEach(button => {
                    button.addEventListener('click', (e) => {
                        handleRejectRequest(e.target.dataset.requestId);
                    });
                });
            } else {
                pendingList.innerHTML = '<li>받은 친구 요청이 없습니다.</li>';
            }

            // 현재 친구 목록 렌더링
            acceptedList.innerHTML = '';
            if (data.accepted_friends && data.accepted_friends.length > 0) {
                data.accepted_friends.forEach(friend => {
                    const li = document.createElement('li');
                    li.innerHTML = `
                        <span class="user-name">${friend.username}</span>
                        <div class="actions">
                            <button class="action-btn message-btn" data-friend-username="${friend.username}"><span class="emoji">💬</span> 대화</button>
                            <button class="action-btn secondary-btn delete-btn" data-friendship-id="${friend.id}"><span class="emoji">💔</span> 삭제</button>
                        </div>
                    `;
                    acceptedList.appendChild(li);
                });
                acceptedList.querySelectorAll('.delete-btn').forEach(button => {
                    button.addEventListener('click', (e) => {
                        handleDeleteFriend(e.target.dataset.friendshipId);
                    });
                });
            } else {
                acceptedList.innerHTML = '<li>현재 등록된 친구가 없습니다.</li>';
            }
        })
        .catch(error => {
            console.error('친구 데이터 로드 오류:', error);
            pendingList.innerHTML = '<li>친구 데이터를 불러오는 데 실패했습니다.</li>';
            acceptedList.innerHTML = '<li>친구 데이터를 불러오는 데 실패했습니다.</li>';
        });
    }

    // 페이지 로드 시 친구 데이터 로드
    loadFriendData();
});
