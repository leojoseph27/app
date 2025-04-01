// Timer functionality
let timers = {};
let timerStates = {};

function startTimer(questionId, duration) {
    const timerElement = document.querySelector(`#timer-${questionId}`);
    if (!timerElement) return;

    // Initialize timer state if not exists
    if (!timerStates[questionId]) {
        timerStates[questionId] = {
            timeLeft: duration,
            isPaused: false,
            isExpired: false,
            lastPausedTime: null
        };
    }

    // If timer is expired, don't start it
    if (timerStates[questionId].isExpired) {
        timerElement.classList.add('expired');
        timerElement.textContent = 'Time\'s Up!';
        disableQuestion(questionId);
        return;
    }

    // If timer is paused, resume from last paused time
    if (timerStates[questionId].isPaused) {
        const timeSincePause = Date.now() - timerStates[questionId].lastPausedTime;
        timerStates[questionId].timeLeft = Math.max(0, timerStates[questionId].timeLeft - Math.floor(timeSincePause / 1000));
        timerStates[questionId].isPaused = false;
    }

    // Clear existing timer if any
    if (timers[questionId]) {
        clearInterval(timers[questionId]);
    }

    // Start new timer
    timers[questionId] = setInterval(() => {
        if (!timerStates[questionId].isPaused) {
            timerStates[questionId].timeLeft--;
            
            if (timerStates[questionId].timeLeft <= 0) {
                clearInterval(timers[questionId]);
                timerStates[questionId].isExpired = true;
                timerElement.classList.add('expired');
                timerElement.textContent = 'Time\'s Up!';
                disableQuestion(questionId);
            } else {
                const minutes = Math.floor(timerStates[questionId].timeLeft / 60);
                const seconds = timerStates[questionId].timeLeft % 60;
                timerElement.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
            }
        }
    }, 1000);
}

function pauseTimer(questionId) {
    if (timerStates[questionId] && !timerStates[questionId].isExpired) {
        timerStates[questionId].isPaused = true;
        timerStates[questionId].lastPausedTime = Date.now();
        const timerElement = document.querySelector(`#timer-${questionId}`);
        if (timerElement) {
            timerElement.classList.add('paused');
        }
    }
}

function resumeTimer(questionId) {
    if (timerStates[questionId] && !timerStates[questionId].isExpired) {
        timerStates[questionId].isPaused = false;
        const timerElement = document.querySelector(`#timer-${questionId}`);
        if (timerElement) {
            timerElement.classList.remove('paused');
        }
        startTimer(questionId, timerStates[questionId].timeLeft);
    }
}

function disableQuestion(questionId) {
    const questionElement = document.querySelector(`#question-${questionId}`);
    if (questionElement) {
        questionElement.classList.add('disabled');
        const options = questionElement.querySelectorAll('.option');
        options.forEach(option => {
            option.classList.add('disabled');
            option.style.pointerEvents = 'none';
        });
    }
}

// Update navigation functions to handle timers
function nextQuestion() {
    const currentQuestion = document.querySelector('.question.active');
    if (currentQuestion) {
        const currentQuestionId = currentQuestion.id.split('-')[1];
        pauseTimer(currentQuestionId);
        
        const nextQuestionElement = currentQuestion.nextElementSibling;
        if (nextQuestionElement) {
            currentQuestion.classList.remove('active');
            nextQuestionElement.classList.add('active');
            const nextQuestionId = nextQuestionElement.id.split('-')[1];
            resumeTimer(nextQuestionId);
            updateProgress();
        }
    }
}

function previousQuestion() {
    const currentQuestion = document.querySelector('.question.active');
    if (currentQuestion) {
        const currentQuestionId = currentQuestion.id.split('-')[1];
        pauseTimer(currentQuestionId);
        
        const previousQuestionElement = currentQuestion.previousElementSibling;
        if (previousQuestionElement) {
            currentQuestion.classList.remove('active');
            previousQuestionElement.classList.add('active');
            const previousQuestionId = previousQuestionElement.id.split('-')[1];
            resumeTimer(previousQuestionId);
            updateProgress();
        }
    }
}

// Initialize timers for all questions
function initializeTimers() {
    const questions = document.querySelectorAll('.question');
    questions.forEach(question => {
        const questionId = question.id.split('-')[1];
        const timerElement = question.querySelector('.question-timer');
        if (timerElement) {
            const duration = parseInt(timerElement.dataset.duration) || 300; // Default 5 minutes
            startTimer(questionId, duration);
        }
    });
}

// Call initializeTimers when the page loads
document.addEventListener('DOMContentLoaded', initializeTimers); 