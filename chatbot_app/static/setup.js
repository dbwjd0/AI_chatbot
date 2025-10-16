document.addEventListener('DOMContentLoaded', function() {
    const characterImage = document.getElementById('character-image');
    const answerInput = document.getElementById('answer-input');
    const questionText = document.getElementById('question-text');
    const setupForm = document.getElementById('setup-form');
    const factTypeInput = document.getElementById('fact-type');
    const setupCompleteFlag = document.getElementById('setup-complete-flag');

    const originalQuestionText = questionText.textContent.trim();
    const defaultImageSrc = characterImage.src;
    
    function getStaticUrl(path) {
        const imgIndex = defaultImageSrc.lastIndexOf('img/');
        const staticRoot = imgIndex !== -1 ? defaultImageSrc.substring(0, imgIndex) : '/static/';
        return staticRoot + path;
    }

    const ANGRY_IMAGE_SRC = getStaticUrl('img/char_carrot_angry.png');
    const DEFAULT_IMAGE_SRC = getStaticUrl('img/char_carrot_default.png');
    const FINAL_IMAGE_SRC = getStaticUrl('img/char_default.png');

    // 유효성 검사 함수
    function isValidName(value) {
        const trimmedValue = value.trim();
        if (trimmedValue.length < 2) return false;
        if (/^\d+$/.test(trimmedValue)) return false;
        return true;
    }

    function isValidGender(value) {
        const lowerValue = value.trim().toLowerCase();
        return lowerValue.includes('남자') || lowerValue.includes('여자');
    }

    function isValidAge(value) {
        const ageMatch = value.match(/\d+/); // 숫자 추출
        if (!ageMatch) return false;
        const age = parseInt(ageMatch[0]);
        return age > 0 && age < 150; // 숫자 형식 및 적절한 나이
    }

    function isValidMBTI(value) {
        const mbtiPattern = /[IE][NS][TF][JP]/i;
        const match = value.toUpperCase().match(mbtiPattern);
        return match && match[0].length === 4;
    }

    function performValidation(factType, inputValue) {
        let isValid = true;
        if (factType === '이름') {
            isValid = isValidName(inputValue);
        } else if (factType === '성별') {
            isValid = isValidGender(inputValue);
        } else if (factType === '나이') {
            isValid = isValidAge(inputValue);
        } else if (factType === 'mbti') {
            isValid = isValidMBTI(inputValue);
        }
        return isValid;
    }

    // 설정이 완료되었는지 확인
    if (setupCompleteFlag && setupCompleteFlag.value === 'true') {
        characterImage.src = FINAL_IMAGE_SRC; // 최종 이미지 표시 (char_default.png)
        if (setupForm) {
            setupForm.style.display = 'none';
        }
        
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                window.location.href = '/'; // 바로 리디렉션
            }
        });
        return; 
    }

    // 페이지 로드 시 입력창에 자동 포커스 (설정이 완료되지 않은 경우)
    answerInput.focus();

    // 설정이 완료되지 않은 경우에만 이벤트 리스너 연결
    setupForm.addEventListener('submit', function(event) {
        // event.preventDefault(); // 여기서 제거됨

        const factType = factTypeInput.value;
        const inputValue = answerInput.value.trim();
        const isValid = performValidation(factType, inputValue);

        if (!isValid) {
            event.preventDefault(); // 유효성 검사에 실패한 경우에만 기본 동작 방지
            characterImage.src = ANGRY_IMAGE_SRC;
            questionText.textContent = '뭐야?? 제대로 알려줘!!!';
            answerInput.value = ''; // 입력 필드 지우기
            answerInput.disabled = true; // 입력 비활성화
            setupForm.querySelector('button[type="submit"]').disabled = true; // 제출 버튼 비활성화

            setTimeout(() => {
                characterImage.src = DEFAULT_IMAGE_SRC;
                questionText.textContent = originalQuestionText;
                answerInput.disabled = false; // 입력 다시 활성화
                setupForm.querySelector('button[type="submit"]').disabled = false; // 제출 버튼 다시 활성화
                answerInput.focus(); // 재입력을 위해 포커스
            }, 1500); // 1.5초 지연
        } else {
            // 유효한 경우, preventDefault가 호출되지 않았으므로 폼이 자연스럽게 제출됨
            characterImage.src = DEFAULT_IMAGE_SRC;
            questionText.textContent = originalQuestionText;
            // setupForm.submit(); // 더 이상 필요하지 않으므로 이 줄 제거
        }
    });

    // 오류 후 사용자가 입력을 시작하면 이미지와 질문 텍스트를 재설정하는 로직
    answerInput.addEventListener('input', function() {
        if (characterImage.src === ANGRY_IMAGE_SRC) {
            characterImage.src = DEFAULT_IMAGE_SRC;
            questionText.textContent = originalQuestionText;
        }
    });
});