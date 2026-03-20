/**
 * Chatbox JavaScript Module
 * Handles chatbot interaction and UI management
 */

class Chatbox {
    constructor(options = {}) {
        this.options = {
            apiUrl: '/api/chat/message',
            position: 'bottom-right',
            autoOpen: false,
            welcomeMessage: 'Xin chào! Tôi là trợ lý ảo của Nhà sách Gang Thép. Tôi có thể giúp bạn tìm sách, tra cứu đơn hàng và trả lời các câu hỏi về cửa hàng.',
            placeholder: 'Nhập tin nhắn của bạn...',
            ...options
        };
        
        this.isOpen = false;
        this.isTyping = false;
        this.messageHistory = [];
        this.storageKey = 'chatbox_history';
        this.userSessionKey = 'chatbox_user_session';
        
        this.init();
    }
    
    init() {
        this.createChatboxHTML();
        this.bindEvents();
        this.loadChatHistory();
        this.showWelcomeMessage();
        this.setupAuthListener();
        this.startAIShakeAnimation();
        
        // Auto open if specified
        if (this.options.autoOpen) {
            setTimeout(() => this.open(), 1000);
        }
    }
    
    createChatboxHTML() {
        const chatboxHTML = `
            <div class="chatbox-container">
                <button class="chatbox-toggle" id="chatbox-toggle">
                    <svg class="chatbox-icon chat-icon" viewBox="0 0 24 24">
                        <path d="M20 2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h4l2 2 2-2h8c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/>
                    </svg>
                    <svg class="chatbox-icon close-icon" viewBox="0 0 24 24">
                        <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                    </svg>
                    <div class="notification-badge" id="notification-badge" style="display: none;">1</div>
                </button>
                
                <div class="chatbox-window" id="chatbox-window">
                    <div class="chatbox-header">
                        <div class="chatbox-title">
                            <div class="status-indicator"></div>
                            Trợ lý ảo Nhà sách Gang Thép
                        </div>
                        <button class="minimize-btn" id="minimize-btn">−</button>
                    </div>
                    
                    <div class="chatbox-messages" id="chatbox-messages">
                        <div class="welcome-message">
                            <h3>👋 Chào mừng bạn!</h3>
                            <p>${this.options.welcomeMessage}</p>
                            <div class="quick-actions">
                                <div class="quick-action" data-message="Tôi muốn tìm sách cho trẻ em">📚 Sách trẻ em</div>
                                <div class="quick-action" data-message="Có sách nào giảm giá không?">🏷️ Sách giảm giá</div>
                                <div class="quick-action" data-message="Chính sách giao hàng như thế nào?">🚚 Giao hàng</div>
                                <div class="quick-action" data-message="Làm sao để đặt hàng?">🛒 Đặt hàng</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="typing-indicator" id="typing-indicator">
                        <div class="message-avatar">🤖</div>
                        <div class="typing-text">Đang trả lời</div>
                        <div class="typing-dots">
                            <div class="typing-dot"></div>
                            <div class="typing-dot"></div>
                            <div class="typing-dot"></div>
                        </div>
                    </div>
                    
                    <div class="chatbox-input">
                        <textarea 
                            class="message-input" 
                            id="message-input" 
                            placeholder="${this.options.placeholder}"
                            rows="1"
                        ></textarea>
                        <button class="send-btn" id="send-btn" disabled>
                            <svg class="send-icon" viewBox="0 0 24 24">
                                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', chatboxHTML);
    }
    
    bindEvents() {
        const toggle = document.getElementById('chatbox-toggle');
        const minimize = document.getElementById('minimize-btn');
        const input = document.getElementById('message-input');
        const sendBtn = document.getElementById('send-btn');
        const messagesContainer = document.getElementById('chatbox-messages');
        
        // Toggle chatbox
        toggle.addEventListener('click', () => {
            this.isOpen ? this.close() : this.open();
        });
        
        // Minimize button
        minimize.addEventListener('click', () => {
            this.close();
        });
        
        // Input events
        input.addEventListener('input', (e) => {
            this.adjustTextareaHeight(e.target);
            sendBtn.disabled = !e.target.value.trim();
        });
        
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Send button
        sendBtn.addEventListener('click', () => {
            this.sendMessage();
        });
        
        // Quick actions
        messagesContainer.addEventListener('click', (e) => {
            if (e.target.classList.contains('quick-action')) {
                const message = e.target.dataset.message;
                this.sendMessage(message);
            }
        });
        
        // Click outside to close (optional)
        document.addEventListener('click', (e) => {
            const chatboxContainer = e.target.closest('.chatbox-container');
            if (!chatboxContainer && this.isOpen) {
                // Uncomment to close on outside click
                // this.close();
            }
        });
    }
    
    open() {
        const window = document.getElementById('chatbox-window');
        const toggle = document.getElementById('chatbox-toggle');
        const badge = document.getElementById('notification-badge');
        
        window.classList.add('active');
        toggle.classList.add('active');
        badge.style.display = 'none';
        
        this.isOpen = true;
        
        // Focus input after animation
        setTimeout(() => {
            document.getElementById('message-input').focus();
        }, 300);
    }
    
    close() {
        const window = document.getElementById('chatbox-window');
        const toggle = document.getElementById('chatbox-toggle');
        
        window.classList.remove('active');
        toggle.classList.remove('active');
        
        this.isOpen = false;
    }
    
    showWelcomeMessage() {
        // Welcome message is shown by default in HTML
    }
    
    adjustTextareaHeight(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 80) + 'px';
    }
    
    sendMessage(messageText = null) {
        const input = document.getElementById('message-input');
        const message = messageText || input.value.trim();
        
        if (!message) return;
        
        // Add user message
        this.addMessage(message, 'user');
        
        // Clear input
        if (!messageText) {
            input.value = '';
            input.style.height = 'auto';
            document.getElementById('send-btn').disabled = true;
        }
        
        // Show typing indicator
        this.showTyping();
        
        // Send to API
        this.callChatAPI(message);
    }
    
    async callChatAPI(message) {
        try {
            const response = await fetch(this.options.apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache'
                },
                body: JSON.stringify({ 
                    message: message,
                    timestamp: Date.now() // Add timestamp to prevent caching
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Hide typing indicator
            this.hideTyping();
            
            if (data.status === 'success') {
                this.addMessage(data.response, 'bot');
            } else {
                // Show error message from API if available, otherwise show generic message
                const errorMessage = data.response || data.error || 'Xin lỗi, có lỗi xảy ra khi xử lý yêu cầu của bạn. Vui lòng thử lại sau.';
                this.addMessage(errorMessage, 'bot');
            }
            
        } catch (error) {
            console.error('Chat API Error:', error);
            this.hideTyping();
            this.addMessage('Xin lỗi, không thể kết nối đến server. Vui lòng kiểm tra kết nối internet và thử lại.', 'bot');
        }
    }
    
    addMessage(text, sender) {
        const messagesContainer = document.getElementById('chatbox-messages');
        const welcomeMessage = messagesContainer.querySelector('.welcome-message');
        
        // Hide welcome message after first interaction
        if (welcomeMessage) {
            welcomeMessage.style.display = 'none';
        }
        
        const messageElement = document.createElement('div');
        messageElement.className = `message ${sender}`;
        
        const currentTime = new Date().toLocaleTimeString('vi-VN', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        
        const avatar = sender === 'user' ? '👤' : '🤖';
        
        messageElement.innerHTML = `
            <div class="message-avatar">${avatar}</div>
            <div class="message-bubble">
                ${this.formatMessage(text)}
                <div class="message-time">${currentTime}</div>
            </div>
        `;
        
        messagesContainer.appendChild(messageElement);
        
        // Scroll to bottom
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
        // Store in history
        this.messageHistory.push({ text, sender, time: currentTime });
        
        // Save to session storage if user is logged in
        this.saveChatHistory();
        
        // Show notification if closed
        if (!this.isOpen && sender === 'bot') {
            this.showNotification();
        }
    }
    
    formatMessage(text) {
        // Basic formatting for URLs, line breaks, etc.
        return text
            .replace(/\n/g, '<br>')
            .replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>');
    }
    
    showTyping() {
        const typingIndicator = document.getElementById('typing-indicator');
        typingIndicator.classList.add('active');
        this.isTyping = true;
        
        // Scroll to bottom
        const messagesContainer = document.getElementById('chatbox-messages');
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    
    hideTyping() {
        const typingIndicator = document.getElementById('typing-indicator');
        typingIndicator.classList.remove('active');
        this.isTyping = false;
    }
    
    showNotification() {
        const badge = document.getElementById('notification-badge');
        badge.style.display = 'flex';
    }
    
    // Public methods
    openChat() {
        this.open();
    }
    
    closeChat() {
        this.close();
    }
    
    sendQuickMessage(message) {
        if (!this.isOpen) {
            this.open();
        }
        setTimeout(() => {
            this.sendMessage(message);
        }, 300);
    }
    
    // Authentication and session management
    isUserLoggedIn() {
        // Check multiple sources to determine if user is logged in
        // 1. Check session storage for user info
        const hasSessionData = sessionStorage.getItem('user_id') || 
                              sessionStorage.getItem('fuji_user_info') ||
                              localStorage.getItem('fuji_user_info');
        
        // 2. Check if there's a user session in the DOM (from server-side rendering)
        const userDropdown = document.getElementById('userDropdown');
        const hasUserDropdown = userDropdown !== null;
        
        // 3. Check if there's user info in the page
        const hasUserSession = document.body.classList.contains('user-logged-in') ||
                              document.querySelector('[data-user-id]') !== null;
        
        return hasSessionData || hasUserDropdown || hasUserSession;
    }
    
    getCurrentUserId() {
        // Try to get user ID from multiple sources
        let userId = sessionStorage.getItem('user_id');
        
        if (!userId) {
            const userInfo = sessionStorage.getItem('fuji_user_info') || 
                           localStorage.getItem('fuji_user_info');
            if (userInfo) {
                try {
                    const user = JSON.parse(userInfo);
                    userId = user.id;
                } catch (e) {
                    console.warn('Failed to parse user info:', e);
                }
            }
        }
        
        if (!userId) {
            const userElement = document.querySelector('[data-user-id]');
            if (userElement) {
                userId = userElement.getAttribute('data-user-id');
            }
        }
        
        return userId;
    }
    
    setupAuthListener() {
        // Listen for custom authentication events
        window.addEventListener('userLogin', (e) => {
            console.log('Received userLogin event');
            this.onUserLogin();
        });
        
        window.addEventListener('userLogout', (e) => {
            console.log('Received userLogout event');
            this.onUserLogout();
        });
        
        // Listen for authentication state changes
        const originalPushState = history.pushState;
        const originalReplaceState = history.replaceState;
        
        // Monitor navigation changes
        history.pushState = function(...args) {
            originalPushState.apply(history, args);
            setTimeout(() => this.checkAuthStateChange(), 100);
        }.bind(this);
        
        history.replaceState = function(...args) {
            originalReplaceState.apply(history, args);
            setTimeout(() => this.checkAuthStateChange(), 100);
        }.bind(this);
        
        // Monitor page visibility changes
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this.checkAuthStateChange();
            }
        });
        
        // Monitor storage changes (for multiple tabs)
        window.addEventListener('storage', (e) => {
            if (e.key === this.userSessionKey || e.key === 'fuji_user_info') {
                this.checkAuthStateChange();
            }
        });
        
        // Check initially
        this.checkAuthStateChange();
    }
    
    startAIShakeAnimation() {
        const toggleButton = document.getElementById('chatbox-toggle');
        if (!toggleButton) return;
        
        // Add shake animation to indicate AI chat
        toggleButton.classList.add('ai-shake');
        
        // Stop shaking when user interacts
        toggleButton.addEventListener('click', () => {
            toggleButton.classList.remove('ai-shake');
        });
        
        // Resume shaking after 30 seconds if chat is not open
        setInterval(() => {
            if (!this.isOpen && !toggleButton.classList.contains('ai-shake')) {
                toggleButton.classList.add('ai-shake');
            }
        }, 30000); // 30 seconds
    }
    
    checkAuthStateChange() {
        const currentlyLoggedIn = this.isUserLoggedIn();
        const wasLoggedIn = sessionStorage.getItem(this.userSessionKey) === 'true';
        
        if (currentlyLoggedIn && !wasLoggedIn) {
            // User just logged in
            this.onUserLogin();
        } else if (!currentlyLoggedIn && wasLoggedIn) {
            // User just logged out
            this.onUserLogout();
        }
        
        // Update session state
        sessionStorage.setItem(this.userSessionKey, currentlyLoggedIn.toString());
    }
    
    onUserLogin() {
        console.log('User logged in - restoring chat history');
        this.loadChatHistory();
    }
    
    onUserLogout() {
        console.log('User logged out - clearing chat history');
        this.clearChatHistory();
    }
    
    saveChatHistory() {
        if (this.isUserLoggedIn()) {
            const userId = this.getCurrentUserId();
            const storageKey = userId ? `${this.storageKey}_${userId}` : this.storageKey;
            
            const historyData = {
                messages: this.messageHistory,
                timestamp: Date.now(),
                userId: userId
            };
            
            try {
                sessionStorage.setItem(storageKey, JSON.stringify(historyData));
            } catch (e) {
                console.warn('Failed to save chat history:', e);
            }
        }
    }
    
    loadChatHistory() {
        if (!this.isUserLoggedIn()) {
            return;
        }
        
        const userId = this.getCurrentUserId();
        const storageKey = userId ? `${this.storageKey}_${userId}` : this.storageKey;
        
        try {
            const stored = sessionStorage.getItem(storageKey);
            if (stored) {
                const historyData = JSON.parse(stored);
                
                // Verify the history belongs to current user
                if (!userId || historyData.userId === userId) {
                    this.messageHistory = historyData.messages || [];
                    this.restoreChatMessages();
                }
            }
        } catch (e) {
            console.warn('Failed to load chat history:', e);
        }
    }
    
    restoreChatMessages() {
        const messagesContainer = document.getElementById('chatbox-messages');
        if (!messagesContainer) return;
        
        // Clear existing messages but keep welcome message
        const welcomeMessage = messagesContainer.querySelector('.welcome-message');
        messagesContainer.innerHTML = '';
        
        if (this.messageHistory.length === 0) {
            // No history, show welcome message
            if (welcomeMessage) {
                messagesContainer.appendChild(welcomeMessage);
            }
            return;
        }
        
        // Hide welcome message if there are messages
        if (welcomeMessage) {
            welcomeMessage.style.display = 'none';
            messagesContainer.appendChild(welcomeMessage);
        }
        
        // Restore messages
        this.messageHistory.forEach(msg => {
            const messageElement = document.createElement('div');
            messageElement.className = `message ${msg.sender}`;
            
            const avatar = msg.sender === 'user' ? '👤' : '🤖';
            
            messageElement.innerHTML = `
                <div class="message-avatar">${avatar}</div>
                <div class="message-bubble">
                    ${this.formatMessage(msg.text)}
                    <div class="message-time">${msg.time}</div>
                </div>
            `;
            
            messagesContainer.appendChild(messageElement);
        });
        
        // Scroll to bottom
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
    
    clearChatHistory() {
        // Clear from memory
        this.messageHistory = [];
        
        // Clear from storage
        const userId = this.getCurrentUserId();
        const storageKey = userId ? `${this.storageKey}_${userId}` : this.storageKey;
        
        try {
            sessionStorage.removeItem(storageKey);
        } catch (e) {
            console.warn('Failed to clear chat history from storage:', e);
        }
        
        // Reset UI
        this.clearHistory();
    }
    
    clearHistory() {
        const messagesContainer = document.getElementById('chatbox-messages');
        messagesContainer.innerHTML = `
            <div class="welcome-message">
                <h3>👋 Chào mừng bạn!</h3>
                <p>${this.options.welcomeMessage}</p>
                <div class="quick-actions">
                    <div class="quick-action" data-message="Tôi muốn tìm sách cho trẻ em">📚 Sách trẻ em</div>
                    <div class="quick-action" data-message="Có sách nào giảm giá không?">🏷️ Sách giảm giá</div>
                    <div class="quick-action" data-message="Chính sách giao hàng như thế nào?">🚚 Giao hàng</div>
                    <div class="quick-action" data-message="Làm sao để đặt hàng?">🛒 Đặt hàng</div>
                </div>
            </div>
        `;
        this.messageHistory = [];
        
        // Also clear from storage when manually clearing
        this.saveChatHistory();
    }
    
    updateOptions(newOptions) {
        this.options = { ...this.options, ...newOptions };
    }
    
    destroy() {
        const chatboxContainer = document.querySelector('.chatbox-container');
        if (chatboxContainer) {
            chatboxContainer.remove();
        }
    }
}

// Auto-initialize chatbox when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Check if chatbox should be initialized
    if (typeof initChatbox === 'undefined' || initChatbox !== false) {
        window.chatbox = new Chatbox({
            // You can customize options here
            autoOpen: false,
            // apiUrl: '/api/chat/message' // Already default
        });
    }
});

// Make Chatbox available globally
window.Chatbox = Chatbox;