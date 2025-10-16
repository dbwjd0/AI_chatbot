document.addEventListener('DOMContentLoaded', () => {
    const character = document.getElementById('character');
    const room = document.getElementById('room');
    const computer = document.getElementById('computer');
    const overlay = document.getElementById('fade-overlay');
    const step = 10;

    let charX = parseFloat(getComputedStyle(character).left);
    let charY = parseFloat(getComputedStyle(character).top);

    if (isNaN(charX)) charX = 50;
    if (isNaN(charY)) charY = room.offsetHeight - character.offsetHeight - 50;

    character.style.left = `${charX}px`;
    character.style.top = `${charY}px`;

    computer.addEventListener('click', (event) => {
        event.preventDefault();
        overlay.classList.add('visible');
        setTimeout(() => {
            window.location.href = computer.href;
        }, 200);
    });

    document.addEventListener('keydown', (event) => {
        const roomRect = room.getBoundingClientRect();
        const charRect = character.getBoundingClientRect();

        switch (event.key) {
            case 'ArrowUp':
                charY = Math.max(0, charY - step);
                break;
            case 'ArrowDown':
                charY = Math.min(roomRect.height - charRect.height, charY + step);
                break;
            case 'ArrowLeft':
                charX = Math.max(0, charX - step);
                break;
            case 'ArrowRight':
                charX = Math.min(roomRect.width - charRect.width, charX + step);
                break;
            default:
                return;
        }

        character.style.left = `${charX}px`;
        character.style.top = `${charY}px`;
        
        event.preventDefault();
    });

    // --- Schedule Modal Logic ---
    const scheduleModal = document.getElementById('schedule-modal');
    const scheduleIcon = document.getElementById('schedule-icon');
    const closeButton = scheduleModal.querySelector('.close-button');
    const saveScheduleBtn = document.getElementById('save-schedule-btn');
    const scheduleTextarea = document.getElementById('schedule-textarea');

    // Function to open the modal and fetch schedule
    const openModal = () => {
        scheduleModal.style.display = 'block';
        fetch('/schedule/')
            .then(response => response.json())
            .then(data => {
                scheduleTextarea.value = data.content || '';
            })
            .catch(error => console.error('Error fetching schedule:', error));
    };

    // Function to close the modal
    const closeModal = () => {
        scheduleModal.style.display = 'none';
    };

    // Function to save the schedule
    const saveSchedule = () => {
        const content = scheduleTextarea.value;
        const csrftoken = getCookie('csrftoken');

        fetch('/schedule/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify({ content: content })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert('일정이 저장되었습니다.');
                closeModal();
            } else {
                alert('저장에 실패했습니다: ' + data.message);
            }
        })
        .catch(error => console.error('Error saving schedule:', error));
    };

    // Event Listeners
    scheduleIcon.addEventListener('click', openModal);
    closeButton.addEventListener('click', closeModal);
    saveScheduleBtn.addEventListener('click', saveSchedule);

    // Close modal if user clicks outside of the modal content
    window.addEventListener('click', (event) => {
        if (event.target == scheduleModal) {
            closeModal();
        }
    });
});

// Helper function to get CSRF token
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
