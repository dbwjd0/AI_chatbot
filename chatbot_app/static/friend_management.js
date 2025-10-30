// static/friend_management.js

document.addEventListener('DOMContentLoaded', function () {
    console.log("friend_management.js loaded and DOMContentLoaded fired.");

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

    const searchInput = document.getElementById('search-user-input');
    const sendRequestBtn = document.getElementById('send-request-btn');
    const searchBtn = document.getElementById('search-btn'); // New search button
    const searchMessage = document.getElementById('search-message');
    const searchResultsDiv = document.getElementById('search-results'); // New search results div
    const pendingList = document.getElementById('pending-requests-list');
    const acceptedList = document.getElementById('accepted-friends-list');

    // ... (CSRF token and existing functions)

    // ----------------------------------------------------
    // 1.1. 사용자 검색
    // ----------------------------------------------------
    searchBtn.addEventListener('click', function() {
        const query = searchInput.value.trim();
        if (!query) {
            searchMessage.textContent = "검색할 사용자 이름을 입력하세요.";
            searchMessage.style.color = 'red';
            searchResultsDiv.innerHTML = '';
            return;
        }

        searchMessage.textContent = "사용자 검색 중...";
        searchMessage.style.color = 'orange';
        searchResultsDiv.innerHTML = '';

        fetch(`/friends/search/?query=${encodeURIComponent(query)}`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': csrftoken
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                if (data.users.length > 0) {
                    searchMessage.textContent = `${data.users.length}명의 사용자를 찾았습니다.`;
                    searchMessage.style.color = 'green';
                    data.users.forEach(user => {
                        const li = document.createElement('li');
                        li.classList.add('user-item');
                        let actionButton = '';
                        if (user.is_friend) {
                            actionButton = '<span class="info-text">친구</span>';
                        } else if (user.has_pending_request_from_me) {
                            actionButton = '<span class="info-text">요청 보냄</span>';
                        } else if (user.has_pending_request_to_me) {
                            actionButton = '<span class="info-text">요청 받음</span>';
                        } else {
                            actionButton = `<button class="action-btn primary-btn send-request-search-btn" data-username="${user.username}">요청 보내기</button>`;
                        }
                        li.innerHTML = `
                            <span class="user-name">${user.username}</span>
                            <div class="actions">${actionButton}</div>
                        `;
                        searchResultsDiv.appendChild(li);
                    });
                    // 동적으로 생성된 요청 보내기 버튼에 이벤트 리스너 할당
                    searchResultsDiv.querySelectorAll('.send-request-search-btn').forEach(button => {
                        button.addEventListener('click', function() {
                            sendFriendRequestFromSearch(this.dataset.username);
                        });
                    });
                } else {
                    searchMessage.textContent = "검색 결과가 없습니다.";
                    searchMessage.style.color = 'orange';
                }
            } else {
                searchMessage.textContent = `오류: ${data.message}`;
                searchMessage.style.color = 'red';
            }
        })
        .catch(error => {
            console.error('사용자 검색 오류:', error);
            searchMessage.textContent = '서버 통신 오류가 발생했습니다.';
            searchMessage.style.color = 'red';
        });
    });

    // 검색 결과에서 친구 요청 보내기
    function sendFriendRequestFromSearch(targetUsername) {
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
                // 요청 성공 후 검색 결과 새로고침
                searchBtn.click(); 
                loadFriendData(); // 친구 목록 및 요청 목록 새로고침
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
    }

    // ----------------------------------------------------
    // 1. 친구 요청 보내기 (기존 버튼 유지, 검색 결과와 별개)
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
                loadFriendData(); // 친구 목록 및 요청 목록 새로고침
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
            const navRequestCountSpan = document.getElementById('nav-request-count');
            const navFriendCountSpan = document.getElementById('nav-friend-count');
            const sectionRequestCountSpan = document.getElementById('request-count-section');
            const sectionFriendCountSpan = document.getElementById('friend-count-section');

            const pendingRequestCount = data.pending_requests ? data.pending_requests.length : 0;
            const acceptedFriendCount = data.accepted_friends ? data.accepted_friends.length : 0;

            if (navRequestCountSpan) {
                navRequestCountSpan.textContent = pendingRequestCount;
                if (pendingRequestCount > 0) {
                    navRequestCountSpan.classList.add('active-notification');
                } else {
                    navRequestCountSpan.classList.remove('active-notification');
                }
            }

            if (navFriendCountSpan) {
                navFriendCountSpan.textContent = acceptedFriendCount;
            }

            if (sectionRequestCountSpan) {
                sectionRequestCountSpan.textContent = pendingRequestCount;
            }

            if (sectionFriendCountSpan) {
                sectionFriendCountSpan.textContent = acceptedFriendCount;
            }

            if (data.pending_requests && data.pending_requests.length > 0) {
                data.pending_requests.forEach(req => {
                    const li = document.createElement('li');
                    li.innerHTML = `
                        <span class="user-name">${req.from_user}</span>
                        <div class="actions">
                            <button class="action-btn accept-btn" data-request-id="${req.id}"><span class="emoji">✅</span> 수락</button>
                            <button class="action-btn reject-btn" data-request-id="${req.id}"><span class="emoji">✖️</span> 거절</button>
                        </div>
                    `;
                    pendingList.appendChild(li);
                });
                // 동적으로 생성된 버튼에 이벤트 리스너 할당
                pendingList.querySelectorAll('.accept-btn').forEach(button => {
                    button.addEventListener('click', (e) => {
                        handleAcceptRequest(e.currentTarget.dataset.requestId);
                    });
                });
                pendingList.querySelectorAll('.reject-btn').forEach(button => {
                    button.addEventListener('click', (e) => {
                        handleRejectRequest(e.currentTarget.dataset.requestId);
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
                        <button class="action-btn secondary-btn delete-btn" data-friendship-id="${friend.id}"><span class="emoji">❌</span></button>
                    `;
                    acceptedList.appendChild(li);
                });
                acceptedList.querySelectorAll('.delete-btn').forEach(button => {
                    button.addEventListener('click', (e) => {
                        handleDeleteFriend(e.currentTarget.dataset.friendshipId);
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

    // ----------------------------------------------------
    // 4. 내부 네비게이션 (친구 찾기, 받은 요청, 내 친구) 처리
    // ----------------------------------------------------
    const navButtons = document.querySelectorAll('.friend-nav .nav-btn');
    const sections = document.querySelectorAll('.friend-section-wrapper');

    navButtons.forEach(button => {
        button.addEventListener('click', function() {
            // 모든 nav 버튼에서 active 클래스 제거
            navButtons.forEach(btn => btn.classList.remove('active'));
            // 클릭된 버튼에 active 클래스 추가
            this.classList.add('active');

            // 모든 섹션 숨기기
            sections.forEach(section => section.classList.remove('active'));

            // 클릭된 버튼의 data-target에 해당하는 섹션 보이기
            const targetId = this.dataset.target;
            document.getElementById(targetId).classList.add('active');
        });
    });

    // 페이지 로드 시 친구 데이터 로드
    loadFriendData();
});
