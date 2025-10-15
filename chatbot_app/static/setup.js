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

    // Validation functions
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
        const ageMatch = value.match(/\d+/); // Extract digits
        if (!ageMatch) return false;
        const age = parseInt(ageMatch[0]);
        return age > 0 && age < 150; // Numeric and reasonable age
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

    // Check if setup is complete
    if (setupCompleteFlag && setupCompleteFlag.value === 'true') {
        characterImage.src = FINAL_IMAGE_SRC; // Show final image (char_default.png)
        if (setupForm) {
            setupForm.style.display = 'none';
        }
        
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                window.location.href = '/'; // Redirect directly
            }
        });
        return; 
    }

    // Auto-focus on input when page loads (if setup is not complete)
    answerInput.focus();

    // Attach event listeners only if setup is NOT complete
    setupForm.addEventListener('submit', function(event) {
        // event.preventDefault(); // Removed from here

        const factType = factTypeInput.value;
        const inputValue = answerInput.value.trim();
        const isValid = performValidation(factType, inputValue);

        if (!isValid) {
            event.preventDefault(); // Only prevent default if validation fails
            characterImage.src = ANGRY_IMAGE_SRC;
            questionText.textContent = '뭐야?? 제대로 알려줘!!!';
            answerInput.value = ''; // Clear the input field
            answerInput.disabled = true; // Disable input
            setupForm.querySelector('button[type="submit"]').disabled = true; // Disable submit button

            setTimeout(() => {
                characterImage.src = DEFAULT_IMAGE_SRC;
                questionText.textContent = originalQuestionText;
                answerInput.disabled = false; // Re-enable input
                setupForm.querySelector('button[type="submit"]').disabled = false; // Re-enable submit button
                answerInput.focus(); // Focus for re-entry
            }, 1500); // 1.5-second delay
        } else {
            // If valid, the form will submit naturally because preventDefault was not called
            characterImage.src = DEFAULT_IMAGE_SRC;
            questionText.textContent = originalQuestionText;
            // setupForm.submit(); // Removed this line as it's no longer needed
        }
    });

    // Logic to reset image and question text if user starts typing after an error
    answerInput.addEventListener('input', function() {
        if (characterImage.src === ANGRY_IMAGE_SRC) {
            characterImage.src = DEFAULT_IMAGE_SRC;
            questionText.textContent = originalQuestionText;
        }
    });
});