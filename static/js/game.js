/**
 * game.js
 * Flappy Bird Game Logic
 */
import { state } from './config.js';
import { startCommunication } from './main.js';

let canvas, ctx;
let bird, pipes, score, gameOver, gravity, flapStrength, pipeGap, pipeWidth, pipeSpeed, frameCount;
let menuOptions = ['retryBtn', 'quitBtn'];
let menuIndex = 0;
let inGameOverMenu = false;
let gameStarted = false;

export function initGame() {
    console.log("Initializing Flappy Bird...");
    canvas = document.getElementById('flappyCanvas');
    if (!canvas) return; // Exit if we aren't on the game page
    ctx = canvas.getContext('2d');

    // Auto-select user and start stream if possible (Game needs blink input)
    setTimeout(() => {
        if (state.currentSelectedUser) {
            startCommunication(); 
        } else {
            // Try to force select test user if available
            const userSelect = document.getElementById('userSelect');
            if(userSelect && userSelect.value) {
                state.currentSelectedUser = userSelect.value;
                startCommunication();
            }
        }
    }, 500);

    // Initial setup
    resetGame();
    
    // UI Button Listeners
    document.getElementById('retryBtn')?.addEventListener('click', resetGame);
    document.getElementById('quitBtn')?.addEventListener('click', () => window.location.href = '/');
    
    // Keyboard fallback for debugging
    document.addEventListener('keydown', handleKeyboardInput);
}

// Received from socketClient.js
export function handleGameBlink(type) {
    if (!gameStarted && type === 'dash') {
        gameStarted = true;
        requestAnimationFrame(gameLoop);
        return;
    }
    
    if (!inGameOverMenu) {
        // While playing
        if (type === 'dot') flap();
    } else {
        // In Game Over Menu
        if (type === 'dot') {
            menuIndex = (menuIndex + 1) % menuOptions.length;
            highlightMenuOption(menuIndex);
        } else if (type === 'dash') {
            selectMenuOption();
        }
    }
}

function handleKeyboardInput(e) {
    if (!gameStarted && e.key === 'Enter') {
        gameStarted = true;
        requestAnimationFrame(gameLoop);
    } else if (!inGameOverMenu && (e.code === 'Space' || e.key === 'w')) {
        flap();
    } else if (inGameOverMenu) {
        if (e.key === 'ArrowRight' || e.key === 'd') {
            menuIndex = (menuIndex + 1) % menuOptions.length;
            highlightMenuOption(menuIndex);
        } else if (e.key === 'Enter') {
            selectMenuOption();
        }
    }
}

function resetGame() {
    bird = { x: 80, y: canvas.height / 2, radius: 20, velocity: 0 };
    pipes = [];
    score = 0;
    gameOver = false;
    gravity = 0.5;
    flapStrength = -8;
    pipeGap = 150;
    pipeWidth = 60;
    pipeSpeed = 2.5;
    frameCount = 0;
    inGameOverMenu = false;
    gameStarted = false;
    
    document.getElementById('gameOverMenu').style.display = 'none';
    highlightMenuOption(menuIndex);
    drawStartScreen();
}

function gameLoop() {
    if (!gameStarted) {
        drawStartScreen();
        return;
    }
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!gameOver) {
        updateBird();
        if (frameCount % 90 === 0) addPipe();
        updatePipes();
        checkScore();
        drawPipes();
        drawBird();
        drawScore();
        
        if (checkCollision()) {
            gameOver = true;
            setTimeout(showGameOverMenu, 500);
        }
        frameCount++;
        requestAnimationFrame(gameLoop);
    } else {
        drawPipes();
        drawBird();
        drawScore();
    }
}

// --- Helper Game Functions ---
function drawStartScreen() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#70c5ce';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.font = 'bold 36px Arial';
    ctx.fillStyle = '#fff';
    ctx.textAlign = 'center';
    ctx.fillText('Flappy Bird', canvas.width / 2, canvas.height / 2 - 60);
    ctx.font = '24px Arial';
    ctx.fillText('Long blink to start', canvas.width / 2, canvas.height / 2);
}

function updateBird() {
    bird.velocity += gravity;
    bird.y += bird.velocity;
}

function flap() {
    if (!gameOver && !inGameOverMenu && gameStarted) {
        bird.velocity = flapStrength;
    }
}

function addPipe() {
    let top = Math.random() * (canvas.height - pipeGap - 100) + 50;
    pipes.push({ x: canvas.width, top: top, bottom: top + pipeGap, passed: false });
}

function updatePipes() {
    pipes.forEach(pipe => pipe.x -= pipeSpeed);
    if (pipes.length && pipes[0].x + pipeWidth < 0) pipes.shift();
}

function checkCollision() {
    if (bird.y + bird.radius > canvas.height || bird.y - bird.radius < 0) return true;
    for (let pipe of pipes) {
        if (bird.x + bird.radius > pipe.x && bird.x - bird.radius < pipe.x + pipeWidth &&
           (bird.y - bird.radius < pipe.top || bird.y + bird.radius > pipe.bottom)) {
            return true;
        }
    }
    return false;
}

function checkScore() {
    pipes.forEach(pipe => {
        if (!pipe.passed && bird.x > pipe.x + pipeWidth) {
            score++;
            pipe.passed = true;
        }
    });
}

function drawBird() {
    ctx.beginPath();
    ctx.arc(bird.x, bird.y, bird.radius, 0, Math.PI * 2);
    ctx.fillStyle = '#FFD700';
    ctx.fill();
    ctx.stroke();
}

function drawPipes() {
    ctx.fillStyle = '#228B22';
    pipes.forEach(pipe => {
        ctx.fillRect(pipe.x, 0, pipeWidth, pipe.top);
        ctx.fillRect(pipe.x, pipe.bottom, pipeWidth, canvas.height - pipe.bottom);
    });
}

function drawScore() {
    ctx.font = '32px Arial';
    ctx.fillStyle = '#fff';
    ctx.strokeStyle = '#000';
    ctx.strokeText(score, canvas.width / 2 - 10, 60);
    ctx.fillText(score, canvas.width / 2 - 10, 60);
}

function showGameOverMenu() {
    inGameOverMenu = true;
    document.getElementById('gameOverMenu').style.display = 'block';
    menuIndex = 0;
    highlightMenuOption(menuIndex);
}

function highlightMenuOption(idx) {
    menuOptions.forEach((id, i) => {
        const btn = document.getElementById(id);
        if (btn) i === idx ? btn.classList.add('highlighted') : btn.classList.remove('highlighted');
    });
}

function selectMenuOption() {
    if (menuOptions[menuIndex] === 'retryBtn') resetGame();
    else if (menuOptions[menuIndex] === 'quitBtn') window.location.href = '/';
}