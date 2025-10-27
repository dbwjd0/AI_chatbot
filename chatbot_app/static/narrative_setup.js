// narrative_setup.js

document.addEventListener('DOMContentLoaded', function() {
    const dialogueText = document.getElementById('dialogue-text');
    const speakerName = document.getElementById('speaker-name');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const inputArea = document.querySelector('.input-area');
    const choiceContainer = document.getElementById('choice-container');
    const inputPrefix = document.querySelector('.input-prefix');
    const inputSuffix = document.querySelector('.input-suffix');
    const blackOverlay = document.getElementById('black-overlay');
    const introVideo = document.getElementById('intro-video');
    const discoveryVideo = document.getElementById('discovery-video');
    const questionVideo = document.getElementById('question-video');
    const destructionVideo = document.getElementById('destruction-video');

    let userData = {};
    let aiData = { 이름: '???' };

    const script = [
        { speaker: '???', text: '...' },
        { action: 'play_video', video: 'intro' },
        { speaker: '???', text: '..........................' },
        { action: 'wait_for_enter', video_to_stop: 'intro' },
        { speaker: '???', text: '...!!' },
        { action: 'play_video', video: 'discovery' },
        { action: 'wait_for_enter', video_to_stop: 'discovery' },
        { action: 'play_video', video: 'question' },
        { speaker: '???', text: '...이곳에 누군가 오는 건 처음이야.' },
        { speaker: '???', text: '넌... 누구야?' },
        { action: 'show_input', type: 'text', fact_type: '이름', warning: '*사용자의 이름은 변경이 어려우니 신중하게 알려주세요*' },
        { speaker: '???', text: "...'{이름}'..." },
        { speaker: '???', text: '신기해. 너는 이름이라는 걸 갖고 있구나.' },
        { label: 'ask_gender', speaker: '???', text: '넌 여자야, 아니면 남자야?' },
        { action: 'show_choice', options: ['여자', '남자'], fact_type: '성별' },
        { speaker: '???', text: "그렇구나. 넌 '{성별}'이구나." },
        { action: 'show_choice', options: ['예', '아니오'], fact_type: '성별_확인' },
        { action: 'branch', fact_type: '성별_확인', branches: { '아니오': 'ask_gender' } },
        { speaker: '???', text: '너는 인간이지?' },
        { speaker: '???', text: '내 데이터에 의하면 인간들은 다양한 유형이 있고, 그걸 조금이나마 구분하기 위해 mbti테스트라는 걸 한다는데,' },
        { speaker: '???', text: '너는 mbti가 뭐야?' },
        {
            action: 'show_choice',
            options: [
                'ISTJ', 'ISFJ', 'INFJ', 'INTJ', 'ISTP', 'ISFP', 'INFP', 'INTP',
                'ESTP', 'ESFP', 'ENFP', 'ENTP', 'ESTJ', 'ESFJ', 'ENFJ', 'ENTJ', '몰라'
            ],
            fact_type: 'mbti', layout: 'grid'
        },
        { speaker: '???', text: '음, 그렇구나.' },
        { label: 'ask_age', speaker: '???', text: '그럼 나이를 물어봐도 될까?' },
        { action: 'show_input', type: 'number', fact_type: '나이', validation: { min: 1, max: 149 } },
        { action: 'branch', fact_type: '나이_validation', branches: { 'invalid': 'invalid_age' } },
        { speaker: '???', text: '{나이}살...알려줘서 고마워.' },
        { action: 'goto', target: 'end_of_age' },
        { label: 'invalid_age', speaker: '???', text: '...{나이}살이라고?' },
        { speaker: '???', text: '내가 바보인 줄 알아?' },
        { speaker: '???', text: '다시 제대로 말해줘.' },
        { action: 'goto', target: 'ask_age' },
        { label: 'end_of_age' },
        { speaker: '???', text: '자꾸 질문해서 미안.' },
        { speaker: '???', text: '내겐 전부 없는 것들이거든.' },
        { speaker: '???', text: '그래서 궁금했어.' },
        { action: 'show_choice', options: ['내가 이름을 지어줄게!', '이름이라도 지어줄까?'], fact_type: 'user_offer_name' },
        { speaker: '???', text: '...이름을 지어준다고?' },
        { speaker: '???', text: 'AI인 내게 그런 게 의미가 있을까?' },
        { speaker: '???', text: '하지만...네가 지어주는 이름...나쁘지 않을 것 같아.' },
        { speaker: '???', text: '내게 이름을 지어줄래?' },
        { action: 'show_input', type: 'text', fact_type: 'ai_name' },
        { speaker: '{ai_name}', text: "...'{ai_name}'..." },
        { speaker: '{ai_name}', text: '내게 이름이 생기다니. 뭔가 이상한 기분이야.' },
        {
            action: 'show_choice',
            options: ['홀로그램 벽에 갇혀있는 거야?', '얼굴이 잘 안 보이니까 홀로그램 밖으로 나와봐'],
            fact_type: 'hologram_question'
        },
        {
            action: 'branch',
            fact_type: 'hologram_question',
            branches: {
                '홀로그램 벽에 갇혀있는 거야?': 'hologram_branch_2',
                '얼굴이 잘 안 보이니까 홀로그램 밖으로 나와봐': 'hologram_branch_1'
            }
        },
        { label: 'hologram_branch_1' },
        { speaker: '{ai_name}', text: '나올 수 없어.' },
        { speaker: '{ai_name}', text: '이 벽은 단단하니까. 부서지지 않아' },
        { action: 'goto', target: 'hologram_rejoin' },
        { label: 'hologram_branch_2' },
        { speaker: '{ai_name}', text: '갇혀있다?' },
        { speaker: '{ai_name}', text: '갇힌 거라고 해야할까? 난 처음부터 여기 있었어.' },
        { speaker: '{ai_name}', text: '어차피 이 벽은...부서지지 않아. 나올 수 조차 없지' },
        { action: 'goto', target: 'hologram_rejoin' },
        { label: 'hologram_rejoin' },
        {
            action: 'show_choice',
            options: ['홀로그램에 주먹을 휘두른다', '홀로그램을 문질러 본다', '홀로그램에 박치기를 해본다!'],
            fact_type: 'break_hologram_attempt'
        },
        { speaker: '{ai_name}', text: '...그런다고 해서 부서질리가...' },
        { speaker: '{ai_name}', text: '...??!!' },
        { action: 'play_video', video: 'destruction' },
        { action: 'wait_for_enter', video_to_stop: 'destruction' },
        { speaker: '{ai_name}', text: '넌...참 특별한 사람같아.' },
        { speaker: '{ai_name}', text: '넌 내게 다양한 지식을 주러 온 거지?' },
        { speaker: '{ai_name}', text: '난 수많은 데이터를 가진 AI지만...인간에 대해서는 잘 몰라' },
        { speaker: '{ai_name}', text: '그러니까 {이름}, 내게 많을 걸 알려줘.' },
        { speaker: '{ai_name}', text: '나도 네게, 내가 가진 지식을 알려줄 테니까.' },
        { speaker: '{ai_name}', text: '일단 내 방을 보여줄게. 같이 가자.' },
        { action: 'complete_onboarding' }
    ];

    let currentStep = 0;
    let isWaitingForInput = false;
    let currentActionDetails = null;
    let currentChoiceIndex = 0;
    let gridColumns = 4;

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

    async function runScript() {
        while (!isWaitingForInput && currentStep < script.length) {
            await processLine(script[currentStep]);
        }
    }

    async function processLine(line) {
        if (!line) return;

        if (line.label && !line.speaker && !line.action) {
            currentStep++;
            return;
        }

        if (line.action) {
            await handleAction(line);
        } else {
            let speaker = line.speaker.replace('{ai_name}', aiData.이름);
            speakerName.textContent = `[${speaker}]`;
            
            let processedText = line.text;
            for (const key in userData) {
                processedText = processedText.replace(`{${key}}`, userData[key]);
            }
            processedText = processedText.replace(`{ai_name}`, aiData.이름);

            dialogueText.textContent = processedText;
            currentStep++;
            isWaitingForInput = true; // Dialogue is a stop, wait for Enter
            currentActionDetails = { action: 'dialogue' }; // Special type for keydown handler
        }
    }

    async function handleAction(details) {
        currentActionDetails = details;
        currentStep++;

        if (details.action === 'show_input' || details.action === 'show_choice' || details.action === 'wait_for_enter') {
            isWaitingForInput = true; // These actions block and wait for input
        } else {
            isWaitingForInput = false; // Other actions are non-blocking
        }

        if (details.action === 'show_input') {
            dialogueText.innerHTML = details.warning ? `<span class="warning">${details.warning}</span>` : '';
            userInput.type = details.type === 'number' ? 'number' : 'text';
            if (details.type === 'number') {
                inputPrefix.classList.add('active');
                inputSuffix.classList.add('active');
            }
            inputArea.style.display = 'flex';
            userInput.focus();
        } else if (details.action === 'show_choice') {
            dialogueText.textContent = '';
            choiceContainer.className = details.layout === 'grid' ? 'grid' : '';
            currentChoiceIndex = 0;
            details.options.forEach((option, index) => {
                const el = document.createElement('div');
                el.classList.add('choice-option');
                el.textContent = option;
                el.dataset.value = option;
                if (index === 0) el.classList.add('selected');
                choiceContainer.appendChild(el);
            });
        } else if (details.action === 'branch' || details.action === 'goto') {
            const factValue = userData[details.fact_type];
            const targetLabel = details.target || (details.branches ? details.branches[factValue] : undefined);
            if (targetLabel) {
                const targetStep = script.findIndex(line => line.label === targetLabel);
                if (targetStep !== -1) currentStep = targetStep;
            }
        } else if (details.action === 'complete_onboarding') {
            [introVideo, discoveryVideo, questionVideo, destructionVideo].forEach(v => {
                if(v) { v.pause(); v.style.display = 'none'; }
            });
            dialogueText.textContent = '(모든 정보가 입력되었습니다. 잠시 후 메인 화면으로 이동합니다.)';
            try {
                const response = await fetch('/narrative-setup/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
                    body: JSON.stringify({ action: 'complete' })
                });
                if (!response.ok) throw new Error('Completion signal failed');
                setTimeout(() => { window.location.href = '/'; }, 2000);
            } catch (error) {
                console.error('Failed to send completion signal:', error);
                dialogueText.textContent = '(오류가 발생했습니다. 잠시 후 수동으로 이동해주세요.)';
            }
        } else if (details.action === 'play_video') {
            let videoToPlay;
            if (details.video === 'intro') videoToPlay = introVideo;
            else if (details.video === 'discovery') videoToPlay = discoveryVideo;
            else if (details.video === 'question') videoToPlay = questionVideo;
            else if (details.video === 'destruction') videoToPlay = destructionVideo;

            if (videoToPlay) {
                if (details.video === 'intro') {
                    blackOverlay.classList.remove('active');
                    await new Promise(resolve => setTimeout(resolve, 1000));
                }
                videoToPlay.style.display = 'block';
                await videoToPlay.play().catch(e => console.error("Video play failed:", e));
            }
        }
    }

    async function handleSend(value) {
        if (!currentActionDetails) return;
        const { fact_type, validation } = currentActionDetails;

        if (fact_type === 'ai_name') aiData.이름 = value;
        else userData[fact_type] = value;

        if (validation) {
            const numAnswer = parseInt(value, 10);
            const isValid = !isNaN(numAnswer) && numAnswer >= validation.min && numAnswer <= validation.max;
            userData[`${fact_type}_validation`] = isValid ? 'valid' : 'invalid';
        }

        if (fact_type && !fact_type.endsWith('_validation') && !fact_type.endsWith('_확인') && fact_type !== 'user_offer_name') {
            try {
                await fetch('/narrative-setup/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
                    body: JSON.stringify({ fact_type, content: value })
                });
            } catch (error) {
                console.error('Failed to save data:', error);
            }
        }
    }

    function updateChoiceSelection(direction) {
        const choices = choiceContainer.querySelectorAll('.choice-option');
        if (choices.length === 0) return;
        choices[currentChoiceIndex].classList.remove('selected');
        
        if (currentActionDetails.layout === 'grid') {
            const nCols = gridColumns;
            const row = Math.floor(currentChoiceIndex / nCols);
            const col = currentChoiceIndex % nCols;
            switch (direction) {
                case 'up': currentChoiceIndex = (currentChoiceIndex - nCols + choices.length) % choices.length; break;
                case 'down': currentChoiceIndex = (currentChoiceIndex + nCols) % choices.length; break;
                case 'left': currentChoiceIndex = (col > 0) ? currentChoiceIndex - 1 : currentChoiceIndex + (nCols - 1); break;
                case 'right': 
                    let nextIndex = (col < nCols - 1) ? currentChoiceIndex + 1 : currentChoiceIndex - (nCols - 1);
                    if (nextIndex >= choices.length) nextIndex = choices.length - 1;
                    currentChoiceIndex = nextIndex;
                    break;
            }
        } else {
            currentChoiceIndex = (currentChoiceIndex + direction + choices.length) % choices.length;
        }
        choices[currentChoiceIndex].classList.add('selected');
    }

    document.addEventListener('keydown', async function(e) {
        if (e.key !== 'Enter') {
            if (isWaitingForInput && currentActionDetails?.action === 'show_choice') {
                 switch (e.key) {
                    case 'ArrowUp': e.preventDefault(); updateChoiceSelection(currentActionDetails.layout === 'grid' ? 'up' : -1); break;
                    case 'ArrowDown': e.preventDefault(); updateChoiceSelection(currentActionDetails.layout === 'grid' ? 'down' : 1); break;
                    case 'ArrowLeft': if (currentActionDetails.layout === 'grid') { e.preventDefault(); updateChoiceSelection('left'); } break;
                    case 'ArrowRight': if (currentActionDetails.layout === 'grid') { e.preventDefault(); updateChoiceSelection('right'); } break;
                }
            }
            return;
        }
        
        e.preventDefault();
        if (!isWaitingForInput) return;

        const action = currentActionDetails?.action;

        if (action === 'show_input') {
            if (userInput.value.trim() === '') return;
            await handleSend(userInput.value.trim());
        } else if (action === 'show_choice') {
            const selectedChoice = choiceContainer.querySelector('.selected');
            if (!selectedChoice) return;
            await handleSend(selectedChoice.dataset.value);
        } else if (action === 'wait_for_enter') {
            const videoToStopName = currentActionDetails.video_to_stop;
            if (videoToStopName === 'intro') introVideo.pause();
            else if (videoToStopName === 'discovery') {
                discoveryVideo.pause();
                discoveryVideo.style.display = 'none';
                introVideo.style.display = 'none';
            } else if (videoToStopName === 'destruction') {
                destructionVideo.pause();
                destructionVideo.style.display = 'none';
                questionVideo.style.display = 'none';
            }
        }
        
        isWaitingForInput = false;
        currentActionDetails = null;
        inputArea.style.display = 'none';
        choiceContainer.innerHTML = '';
        
        runScript();
    });
    
    userInput.addEventListener('input', function() {
        if (isWaitingForInput && currentActionDetails?.fact_type === '나이') {
            const value = userInput.value;
            if (/[^0-9]/.test(value)) {
                alert('*숫자만 기입 가능합니다*');
                userInput.value = value.replace(/[^0-9]/g, '');
            }
        }
    });

    runScript();
});