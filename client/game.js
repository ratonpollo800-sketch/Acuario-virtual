// game.js

// ==============================================================================
// === CONFIGURACIÓN Y CONSTANTES ===============================================
// ==============================================================================
const SERVER_URL = "http://127.0.0.1:5000";
const GOOGLE_CLIENT_ID = "138562970749-203va1opuolk8bmbm5rlthq3kq3gibkq.apps.googleusercontent.com";
const WHATSAPP_NUMBER = "+19719400733";

const canvas = document.getElementById('game-canvas');
const ctx = canvas.getContext('2d');
canvas.width = 800; canvas.height = 600;

const ui = {
    authScreen: document.getElementById('auth-screen'),
    selectionScreen: document.getElementById('selection-screen'),
    verificationScreen: document.getElementById('verification-screen'),
    verificationForm: document.getElementById('verification-form'),
    verificationEmailDisplay: document.getElementById('verification-email-display'),
    showLoginFromVerifyLink: document.getElementById('show-login-from-verify'),
    gameContainer: document.getElementById('game-container'),
    loadingScreen: document.getElementById('loading-screen'),
    loginForm: document.getElementById('login-form'),
    registerForm: document.getElementById('register-form'),
    showRegisterLink: document.getElementById('show-register'),
    showLoginLink: document.getElementById('show-login'),
    prizeName: document.getElementById('prize-name'),
    foodCount: document.getElementById('food-count'),
    foodBagCount: document.getElementById('food-bag-count'),
    progressBar: document.getElementById('progress-bar'),
    progressText: document.getElementById('progress-text'),
    logoutButton: document.getElementById('logout-button'),
    feedButton: document.getElementById('feed-button'),
    loadFoodButton: document.getElementById('load-food-button'),
    tasksButton: document.getElementById('tasks-button'),
    socialButton: document.getElementById('social-button'),
    tasksModal: document.getElementById('tasks-modal'),
    socialModal: document.getElementById('social-modal'),
    userInviteCode: document.getElementById('user-invite-code'),
    tasksList: document.getElementById('tasks-list'),
    toastContainer: document.getElementById('toast-container'),
    buyFoodButton: document.getElementById('buy-food-button'),
    backToMenuButton: document.getElementById('back-to-menu-button'),
    customerServiceButton: document.getElementById('customer-service-button'),
    withdrawButton: document.getElementById('withdraw-button'),
    muteButton: document.getElementById('mute-button')
};

let gameState = {}; let fish, treasureChest; let currentPlayerChoiceId = null; const foodParticles = []; const assets = { images: {}, sounds: {} }; let firstInteraction = false;
let isMuted = false;

class Fish { constructor() { this.x = canvas.width / 2; this.y = canvas.height / 2; this.speedX = Math.random() < 0.5 ? 2 : -2; this.image = assets.images[`fish${currentPlayerChoiceId}`]; this.width = 80; this.height = 80; } updateSize(growth) { const baseSize = 80; const maxSize = 230; const newSize = baseSize + (maxSize - baseSize) * (growth / 100); this.width = newSize; this.height = newSize; } update() { this.x += this.speedX; if (this.x + this.width / 2 > canvas.width || this.x - this.width / 2 < 0) { this.speedX *= -1; } } draw(ctx) { ctx.save(); let drawX = this.x - this.width / 2; let drawY = this.y - this.height / 2; if (this.speedX < 0) { ctx.scale(-1, 1); drawX = -this.x - this.width / 2; } ctx.drawImage(this.image, drawX, drawY, this.width, this.height); ctx.restore(); } }
class Food { constructor(x, y) { this.x = x; this.y = y; this.width = 30; this.height = 30; this.speed = 4; this.image = assets.images.food; } update() { const dx = fish.x - this.x; const dy = fish.y - this.y; const distance = Math.sqrt(dx * dx + dy * dy); if (distance > 1) { this.x += (dx / distance) * this.speed; this.y += (dy / distance) * this.speed; } } draw(ctx) { ctx.drawImage(this.image, this.x - this.width / 2, this.y - this.height / 2, this.width, this.height); } }
class TreasureChest { constructor(x, y) { this.x = x; this.y = y; this.width = 80; this.height = 80; this.image = assets.images.treasure; } draw(ctx) { ctx.drawImage(this.image, this.x - this.width / 2, this.y - this.height / 2, this.width, this.height); } isClicked(mouseX, mouseY) { return (mouseX > this.x - this.width / 2 && mouseX < this.x + this.width / 2 && mouseY > this.y - this.height / 2 && mouseY < this.y + this.height / 2); } }
function isColliding(fish, food) { const dX = fish.x - food.x; const dY = fish.y - food.y; return Math.sqrt(dX*dX + dY*dY) < (fish.width/2 + food.width/2); }

async function apiRequest(endpoint, method = 'GET', body = null, requiresAuth = true) { try { const options = { method, headers: {} }; if (body) { options.headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(body); } if (requiresAuth) { const token = localStorage.getItem('jwt_token'); if (!token) { showToast("No autenticado."); logout(); return null; } options.headers['Authorization'] = `Bearer ${token}`; } const response = await fetch(`${SERVER_URL}/${endpoint}`, options); if (response.status === 401 && endpoint !== 'login') { showToast("Sesión expirada."); logout(); return null; } const responseData = await response.json(); if (!response.ok) { throw responseData; } return responseData; } catch (error) { console.error(`Error en la petición a ${endpoint}:`, error); showToast(error.message || "Error de conexión con el servidor."); return error; } }

// ==============================================================================
// === LÓGICA DEL JUEGO =========================================================
// ==============================================================================
function gameLoop() { update(); draw(); requestAnimationFrame(gameLoop); }
function update() { if(fish) fish.update(); foodParticles.forEach((food, i) => { food.update(); if (isColliding(fish, food)) { assets.sounds.eat.play(); foodParticles.splice(i, 1); } }); }
function draw() { const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height); gradient.addColorStop(0, '#add8e6'); gradient.addColorStop(1, '#0a4473'); ctx.fillStyle = gradient; ctx.fillRect(0, 0, canvas.width, canvas.height); if(fish) fish.draw(ctx); foodParticles.forEach(f => f.draw(ctx)); if (treasureChest) treasureChest.draw(ctx); }
function updateLocalGameState(newState) { gameState = newState; if(fish) fish.updateSize(newState.crecimiento); if (newState.chest_visible) { treasureChest = new TreasureChest(newState.chest_x, newState.chest_y); } else { treasureChest = null; } updateUI(); }
function updateUI() {
    ui.prizeName.textContent = gameState.premio_elegido;
    ui.foodCount.textContent = gameState.comida_disponible;
    ui.foodBagCount.textContent = `${gameState.comida_en_bolsa}/5`;
    const growthPercent = Math.min(100, Math.round(gameState.crecimiento));
    ui.progressBar.style.width = `${growthPercent}%`;
    ui.progressText.textContent = `${growthPercent}%`;
    if (gameState.referral_code) { ui.userInviteCode.textContent = gameState.referral_code; }
    if (growthPercent >= 100) {
        ui.withdrawButton.classList.remove('hidden');
        ui.feedButton.classList.add('hidden');
        ui.buyFoodButton.classList.add('hidden');
        ui.loadFoodButton.classList.add('hidden');
    } else {
        ui.withdrawButton.classList.add('hidden');
        ui.feedButton.classList.remove('hidden');
        ui.buyFoodButton.classList.remove('hidden');
        ui.loadFoodButton.classList.remove('hidden');
    }
}

function toggleMute() {
    assets.sounds.click.play();
    isMuted = !isMuted;
    for (const key in assets.sounds) { assets.sounds[key].muted = isMuted; }
    ui.muteButton.textContent = isMuted ? '🔇' : '🔊';
}

function setupEventListeners() {
    ui.logoutButton.addEventListener('click', logout);
    ui.loadFoodButton.addEventListener('click', async () => { assets.sounds.click.play(); const data = await apiRequest(`load_food_bag`, 'POST'); if (data && data.success) { showToast(data.message); updateLocalGameState(data.new_state); } });
    ui.feedButton.addEventListener('click', () => { showToast("¡Haz clic en el agua!"); assets.sounds.click.play(); });
    ui.tasksButton.addEventListener('click', () => toggleModal(ui.tasksModal, true));
    ui.socialButton.addEventListener('click', () => toggleModal(ui.socialModal, true));
    document.querySelectorAll('.close-button').forEach(btn => btn.addEventListener('click', () => { toggleModal(ui.tasksModal, false); toggleModal(ui.socialModal, false); }));
    canvas.addEventListener('click', handleCanvasClick);
    
    document.body.addEventListener('click', () => { 
        if (!firstInteraction) { 
            assets.sounds.music.loop = true; 
            assets.sounds.music.volume = 0.3; 
            if (!isMuted) {
                assets.sounds.music.play().catch(e => console.error("Error al reproducir música:", e)); 
            }
            firstInteraction = true; 
        } 
    }, { once: true });
    
    ui.buyFoodButton.addEventListener('click', async () => { assets.sounds.click.play(); ui.loadingScreen.classList.remove('hidden'); showToast("Generando enlace de pago para comida..."); const data = await apiRequest('generate_food_payment_link', 'POST'); if (data && data.success && data.payment_url) { showToast("Completa el pago en la nueva pestaña."); window.open(data.payment_url, '_blank'); startCheckingForFoodUpdate(); } ui.loadingScreen.classList.add('hidden'); });
    ui.backToMenuButton.addEventListener('click', () => { assets.sounds.click.play(); ui.gameContainer.classList.add('hidden'); showCharacterSelection(); });
    const whatsappUrl = `https://wa.me/${WHATSAPP_NUMBER.replace(/\+/g, '')}`;
    ui.customerServiceButton.addEventListener('click', () => { assets.sounds.click.play(); window.open(whatsappUrl, '_blank'); });
    
    ui.muteButton.addEventListener('click', toggleMute);
    
    ui.withdrawButton.addEventListener('click', async () => { assets.sounds.bonus.play(); showToast("Verificando tu progreso con el servidor..."); ui.loadingScreen.classList.remove('hidden'); const data = await apiRequest('request_withdrawal', 'POST'); ui.loadingScreen.classList.add('hidden'); if (data && data.success) { showToast("¡Felicidades! Contacta a soporte para recibir tu premio."); window.open(whatsappUrl, '_blank'); } else if (data) { showToast(data.message || "Aún no cumples los requisitos para retirar."); } });
}

function startCheckingForFoodUpdate() { const initialFood = gameState.comida_disponible; let checkCounter = 0; const intervalId = setInterval(async () => { checkCounter++; console.log(`Verificando compra de comida... (Intento #${checkCounter})`); const data = await apiRequest('get_game_state'); if (data && data.game_exists) { if (data.state.comida_disponible > initialFood) { showToast("¡Compra exitosa! Tu comida ha sido añadida."); updateLocalGameState(data.state); clearInterval(intervalId); } } else { clearInterval(intervalId); } if (checkCounter >= 60) { clearInterval(intervalId); } }, 5000); }

async function handleCanvasClick(event) {
    const rect = canvas.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;

    // --- CAMBIO REALIZADO: La lógica de reclamar el cofre ahora es la principal forma de obtener recompensas ---
    if (treasureChest && treasureChest.isClicked(mouseX, mouseY)) {
        assets.sounds.bonus.play();
        ui.loadingScreen.classList.remove('hidden');
        const data = await apiRequest(`claim_chest`, 'POST');
        ui.loadingScreen.classList.add('hidden');
        if (data && data.success) {
            showToast(data.message); // El servidor ahora envía un mensaje específico de la recompensa
            updateLocalGameState(data.new_state);
            toggleModal(ui.tasksModal, false); // Cierra el modal de tareas por si estaba abierto
        } else if (data) {
            showToast(data.message);
        }
        return;
    }

    if (gameState.comida_en_bolsa > 0) {
        const data = await apiRequest(`feed_fish`, 'POST');
        if (data && data.success) {
            assets.sounds.click.play();
            foodParticles.push(new Food(mouseX, mouseY));
            updateLocalGameState(data.new_state);
        }
    } else {
        showToast("¡Tu bolsa de comida está vacía!");
    }
}

function toggleModal(modal, show) { if (assets.sounds.click) assets.sounds.click.play(); if (show) { modal.classList.remove('hidden'); if (modal === ui.tasksModal) renderTasks(); } else { modal.classList.add('hidden'); } }

// --- CAMBIO REALIZADO: La función renderTasks ahora es mucho más dinámica y no maneja reclamos, solo muestra el estado. ---
function renderTasks() {
    ui.tasksList.innerHTML = ''; // Limpiar la lista antes de renderizar

    // Ordenar las tareas para mostrar primero las que se pueden reclamar (tienen cofre)
    const sortedTasks = gameState.tasks_definitions.sort((a, b) => {
        const a_claimable = a.progress >= a.goal && !a.is_claimed;
        const b_claimable = b.progress >= b.goal && !b.is_claimed;
        return b_claimable - a_claimable;
    });
    
    sortedTasks.forEach(task => {
        const li = document.createElement('li');
        li.className = 'task-item';
        
        const progress = Math.min(task.progress, task.goal);
        const goal = task.goal;
        const isCompleted = progress >= goal;
        const isClaimed = task.is_claimed;

        let actionHTML = '';
        if (isClaimed) {
            actionHTML = `<button disabled>Reclamado ✔️</button>`;
        } else if (isCompleted) {
            // Si está completa pero no reclamada, significa que hay un cofre esperando.
            actionHTML = `<button class="task-claimable-button" disabled>¡Busca el Cofre!</button>`;
        } else if (task.id === 'whatsapp_share') {
             // Botón específico para la tarea de compartir
            actionHTML = `<button class="share-whatsapp-btn">Compartir</button>`;
        } else {
            // Tarea en progreso sin acción directa
            actionHTML = `<span>En progreso</span>`;
        }
        
        li.innerHTML = `
            <div class="task-info">
                <strong>${task.name}</strong>
                <span>Recompensa: ${task.reward_text}</span>
            </div>
            <div class="task-progress-container">
                <div class="task-progress-bar" style="width: ${(progress / goal) * 100}%"></div>
                <span>${Math.floor(progress)} / ${goal}</span>
            </div>
            <div class="task-action">
                ${actionHTML}
            </div>
        `;
        ui.tasksList.appendChild(li);
    });

    // --- CAMBIO REALIZADO: La lógica de compartir ahora llama al backend ---
    document.querySelectorAll('.share-whatsapp-btn').forEach(button => {
        button.addEventListener('click', async () => {
            // Abrir WhatsApp
            const gameUrl = window.location.href;
            const message = encodeURIComponent(`¡Te invito a jugar Acuario Virtual y ganar premios! Entra aquí: ${gameUrl}`);
            window.open(`https://wa.me/?text=${message}`, '_blank');
            
            // Notificar al servidor que se ha compartido
            ui.loadingScreen.classList.remove('hidden');
            const data = await apiRequest('track_share', 'POST');
            ui.loadingScreen.classList.add('hidden');

            if (data && data.success) {
                showToast("¡Gracias por compartir!");
                updateLocalGameState(data.new_state); // Actualizar estado del juego
                renderTasks(); // Volver a renderizar las tareas con el nuevo progreso
            }
        });
    });

    // Ya no se necesitan botones de reclamo, se eliminó el event listener.
}


function showToast(message) { const toast = document.createElement('div'); toast.className = 'toast'; toast.textContent = message; ui.toastContainer.appendChild(toast); setTimeout(() => { toast.style.opacity = '0'; toast.addEventListener('transitionend', () => toast.remove()); }, 3000); }

// ==============================================================================
// === AUTENTICACIÓN Y FLUJO DE LA APP (Sin cambios en esta sección) ============
// ==============================================================================
async function handleGoogleCredentialResponse(response) { ui.loadingScreen.classList.remove('hidden'); const data = await apiRequest('google-login', 'POST', { credential: response.credential }, false); ui.loadingScreen.classList.add('hidden'); if (data && data.access_token) { localStorage.setItem('jwt_token', data.access_token); showToast("¡Bienvenido!"); initializeApp(); } else { showToast("Error en el inicio de sesión con Google."); } }
function initializeGoogleSignIn() { if (typeof google === 'undefined') { console.error("La librería de Google no se ha cargado."); return; } google.accounts.id.initialize({ client_id: GOOGLE_CLIENT_ID, callback: handleGoogleCredentialResponse }); google.accounts.id.renderButton(document.getElementById("google-signin-button"), { theme: "outline", size: "large", type: "standard", shape: "rectangular", width: "318"}); }
function showVerificationScreen(email) { ui.authScreen.classList.add('hidden'); ui.selectionScreen.classList.add('hidden'); ui.verificationScreen.classList.remove('hidden'); ui.verificationEmailDisplay.textContent = email; }
function showAuthScreen() { ui.authScreen.classList.remove('hidden'); ui.selectionScreen.classList.add('hidden'); ui.verificationScreen.classList.add('hidden'); ui.loginForm.classList.remove('hidden'); ui.registerForm.classList.add('hidden'); }

function setupAuthListeners() {
    ui.showRegisterLink.addEventListener('click', (e) => { e.preventDefault(); ui.loginForm.classList.add('hidden'); ui.registerForm.classList.remove('hidden'); });
    ui.showLoginLink.addEventListener('click', (e) => { e.preventDefault(); ui.registerForm.classList.add('hidden'); ui.loginForm.classList.remove('hidden'); });
    ui.showLoginFromVerifyLink.addEventListener('click', (e) => { e.preventDefault(); showAuthScreen(); });

    ui.registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        ui.loadingScreen.classList.remove('hidden');
        const email = document.getElementById('register-email').value;
        const password = document.getElementById('register-password').value;
        const referralCode = document.getElementById('referral-code').value; 
        const data = await apiRequest('register', 'POST', { email, password, referral_code: referralCode }, false);
        ui.loadingScreen.classList.add('hidden');
        if (data && data.success) { showToast(data.message); showVerificationScreen(email); } else if (data) { showToast(data.message); }
    });

    ui.verificationForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        ui.loadingScreen.classList.remove('hidden');
        const email = ui.verificationEmailDisplay.textContent;
        const code = document.getElementById('verification-code').value;
        const data = await apiRequest('verify', 'POST', { email, code }, false);
        ui.loadingScreen.classList.add('hidden');
        if (data && data.success) { showToast(data.message); document.getElementById('verification-code').value = ''; showAuthScreen(); } else if (data) { showToast(data.message); }
    });

    ui.loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        ui.loadingScreen.classList.remove('hidden');
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;
        const data = await apiRequest('login', 'POST', { email, password }, false);
        ui.loadingScreen.classList.add('hidden');
        if (data && data.access_token) { localStorage.setItem('jwt_token', data.access_token); showToast("¡Bienvenido!"); initializeApp(); } else if (data) { showToast(data.message); if (data.code === 'ACCOUNT_NOT_VERIFIED') { showVerificationScreen(email); } }
    });

    initializeGoogleSignIn();
}

function logout() { localStorage.removeItem('jwt_token'); document.body.classList.remove('game-active'); window.location.reload(); }

async function startGame(gameStateData) { 
    ui.authScreen.classList.add('hidden'); 
    ui.selectionScreen.classList.add('hidden'); 
    ui.gameContainer.classList.remove('hidden'); 
    document.body.classList.add('game-active');
    ui.loadingScreen.classList.remove('hidden'); 
    try { 
        await Promise.all([ 
            loadAssets('image', { fish1: 'assets/images/fish1.png', fish2: 'assets/images/fish2.png', fish3: 'assets/images/fish3.png', food: 'assets/images/food.png', treasure: 'assets/images/treasure.png', }), 
            loadAssets('sound', { click: 'assets/sounds/click.wav', eat: 'assets/sounds/eat.wav', bonus: 'assets/sounds/bonus.wav', music: 'assets/sounds/music.mp3', }) 
        ]); 
        const prizeToId = { "Premio: 500 Soles": "1", "Premio: 870 Soles": "2", "Premio: 1230 Soles": "3" }; 
        currentPlayerChoiceId = prizeToId[gameStateData.premio_elegido]; 
        fish = new Fish(); 
        updateLocalGameState(gameStateData); 
        ui.loadingScreen.classList.add('hidden'); 
        setupEventListeners(); 
        requestAnimationFrame(gameLoop); 
    } catch (error) { console.error("Fallo al inicializar el juego:", error); ui.loadingScreen.innerHTML = "<p>Error al cargar recursos.</p>"; } 
}

async function showCharacterSelection() {
    document.body.classList.add('game-active');
    ui.authScreen.classList.add('hidden');
    ui.selectionScreen.classList.remove('hidden');
    ui.loadingScreen.classList.remove('hidden');
    const data = await apiRequest('get_game_state');
    ui.loadingScreen.classList.add('hidden');
    const unlocked_fish_ids = (data && data.unlocked_fish_ids) ? data.unlocked_fish_ids : [];
    const active_fish_id = (data && data.game_exists && data.state.active_fish_id) ? data.state.active_fish_id : null;
    document.querySelectorAll('.fish-choice').forEach(choice => {
        const choiceId = choice.dataset.id;
        const isUnlocked = unlocked_fish_ids.includes(choiceId);
        const isActive = choiceId === active_fish_id;
        const newChoice = choice.cloneNode(true);
        choice.parentNode.replaceChild(newChoice, choice);
        const lockIcon = newChoice.querySelector('.lock-icon');
        const priceTag = newChoice.querySelector('.price-tag');
        if (isActive) {
            if(lockIcon) lockIcon.style.display = 'none';
            priceTag.textContent = 'En Juego';
            priceTag.style.backgroundColor = '#ffc107';
            newChoice.style.borderColor = '#ffc107';
            newChoice.addEventListener('click', () => { ui.selectionScreen.classList.add('hidden'); ui.gameContainer.classList.remove('hidden'); });
        } else if (isUnlocked) {
            if(lockIcon) lockIcon.style.display = 'none';
            priceTag.textContent = 'Jugar Gratis';
            priceTag.style.backgroundColor = '#28a745';
            newChoice.addEventListener('click', async () => {
                ui.loadingScreen.classList.remove('hidden');
                const startGameData = await apiRequest('start_free_game', 'POST', { choice_id: choiceId });
                ui.loadingScreen.classList.add('hidden');
                if (startGameData && startGameData.success) { showToast("¡Empezando nueva aventura!"); await startGame(startGameData.new_state); } else if (startGameData) { showToast(startGameData.message); }
            });
        } else {
            if(lockIcon) lockIcon.style.display = 'block';
            newChoice.addEventListener('click', async () => {
                 if(active_fish_id) {
                    showToast("Primero debes terminar tu partida actual para comprar otro pez.");
                 } else {
                    ui.loadingScreen.classList.remove('hidden');
                    showToast("Generando enlace de pago seguro...");
                    const paymentData = await apiRequest('generate_payment_link', 'POST', { choice_id: choiceId });
                    if (paymentData && paymentData.success && paymentData.payment_url) { showToast("¡Listo! Completa el pago en la nueva pestaña."); window.open(paymentData.payment_url, '_blank'); }
                    ui.loadingScreen.classList.add('hidden');
                 }
            });
        }
    });
}

function loadAssets(type, assetsToLoad) { return Promise.all(Object.entries(assetsToLoad).map(([name, path]) => new Promise((resolve, reject) => { if (type === 'image') { const img = new Image(); img.onload = () => { assets.images[name] = img; resolve(); }; img.onerror = () => reject(`No se pudo cargar la imagen: ${path}`); img.src = path; } else if (type === 'sound') { const sound = new Audio(); sound.oncanplaythrough = () => { assets.sounds[name] = sound; resolve(); }; sound.onerror = () => reject(`No se pudo cargar el sonido: ${path}`); sound.src = path; } }))); }

async function initializeApp() { 
    ui.loadingScreen.classList.remove('hidden'); 
    if (!localStorage.getItem('jwt_token')) { 
        ui.authScreen.classList.remove('hidden'); 
        ui.loadingScreen.classList.add('hidden'); 
        setupAuthListeners(); 
    } else { 
        const data = await apiRequest('get_game_state'); 
        if (data && data.game_exists) { 
            startGame(data.state); 
        } else if (data && !data.game_exists) { 
            ui.loadingScreen.classList.add('hidden'); 
            showCharacterSelection(); 
        } else { 
            ui.loadingScreen.classList.add('hidden'); 
            showToast("Error al cargar datos. Inicia sesión de nuevo."); 
            logout(); 
        } 
    } 
}

window.onload = initializeApp;