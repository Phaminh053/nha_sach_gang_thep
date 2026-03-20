/**
 * Chatbox Admin Functions
 * Advanced controls for managing chatbox behavior
 */

class ChatboxAdmin {
    constructor() {
        this.chatbox = window.chatbox;
        this.analyticsData = {
            totalMessages: 0,
            userMessages: 0,
            botMessages: 0,
            sessionStart: new Date(),
            averageResponseTime: 0,
            commonQuestions: {}
        };
        
        this.init();
    }
    
    init() {
        this.trackAnalytics();
        this.createAdminPanel();
    }
    
    trackAnalytics() {
        if (!this.chatbox) return;
        
        // Override the original addMessage method to track analytics
        const originalAddMessage = this.chatbox.addMessage.bind(this.chatbox);
        
        this.chatbox.addMessage = (text, sender) => {
            // Call original method
            originalAddMessage(text, sender);
            
            // Track analytics
            this.analyticsData.totalMessages++;
            
            if (sender === 'user') {
                this.analyticsData.userMessages++;
                this.trackCommonQuestions(text);
            } else {
                this.analyticsData.botMessages++;
            }
            
            this.updateAnalyticsDisplay();
        };
    }
    
    trackCommonQuestions(question) {
        const normalizedQuestion = question.toLowerCase().trim();
        
        // Simple keyword extraction
        const keywords = normalizedQuestion.split(' ').filter(word => word.length > 3);
        
        keywords.forEach(keyword => {
            if (!this.analyticsData.commonQuestions[keyword]) {
                this.analyticsData.commonQuestions[keyword] = 0;
            }
            this.analyticsData.commonQuestions[keyword]++;
        });
    }
    
    createAdminPanel() {
        const adminPanelHTML = `
            <div id="chatbox-admin-panel" style="display: none; position: fixed; top: 20px; left: 20px; 
                 background: white; border: 1px solid #ddd; border-radius: 10px; padding: 20px; 
                 box-shadow: 0 5px 20px rgba(0,0,0,0.2); z-index: 9999; width: 300px; font-family: Arial, sans-serif;">
                <div style="display: flex; justify-content: between; align-items: center; margin-bottom: 15px;">
                    <h4 style="margin: 0; color: #333;">🛠️ Chatbox Admin</h4>
                    <button onclick="chatboxAdmin.toggleAdminPanel()" style="background: none; border: none; font-size: 18px; cursor: pointer;">×</button>
                </div>
                
                <div style="margin-bottom: 15px;">
                    <h5 style="margin: 0 0 10px 0; color: #666;">📊 Analytics</h5>
                    <div id="analytics-display" style="font-size: 12px; color: #666;">
                        <div>Total Messages: <span id="total-messages">0</span></div>
                        <div>User Messages: <span id="user-messages">0</span></div>
                        <div>Bot Messages: <span id="bot-messages">0</span></div>
                        <div>Session Duration: <span id="session-duration">0</span></div>
                    </div>
                </div>
                
                <div style="margin-bottom: 15px;">
                    <h5 style="margin: 0 0 10px 0; color: #666;">🎛️ Controls</h5>
                    <div style="display: flex; flex-direction: column; gap: 5px;">
                        <button onclick="chatboxAdmin.openChatbox()" style="padding: 8px; border: 1px solid #ddd; border-radius: 5px; background: #f8f9fa; cursor: pointer;">Open Chatbox</button>
                        <button onclick="chatboxAdmin.closeChatbox()" style="padding: 8px; border: 1px solid #ddd; border-radius: 5px; background: #f8f9fa; cursor: pointer;">Close Chatbox</button>
                        <button onclick="chatboxAdmin.clearHistory()" style="padding: 8px; border: 1px solid #ddd; border-radius: 5px; background: #f8f9fa; cursor: pointer;">Clear History</button>
                        <button onclick="chatboxAdmin.exportAnalytics()" style="padding: 8px; border: 1px solid #ddd; border-radius: 5px; background: #f8f9fa; cursor: pointer;">Export Analytics</button>
                    </div>
                </div>
                
                <div>
                    <h5 style="margin: 0 0 10px 0; color: #666;">💬 Quick Messages</h5>
                    <div style="display: flex; flex-direction: column; gap: 5px;">
                        <button onclick="chatboxAdmin.sendTestMessage('System test message')" style="padding: 5px; border: 1px solid #ddd; border-radius: 3px; background: #e3f2fd; cursor: pointer; font-size: 11px;">Test Message</button>
                        <button onclick="chatboxAdmin.simulateTyping()" style="padding: 5px; border: 1px solid #ddd; border-radius: 3px; background: #e8f5e8; cursor: pointer; font-size: 11px;">Simulate Typing</button>
                    </div>
                </div>
            </div>
            
            <!-- Admin Toggle Button -->
            <div id="admin-toggle" style="position: fixed; top: 20px; left: 20px; z-index: 9998;">
                <button onclick="chatboxAdmin.toggleAdminPanel()" 
                        style="width: 40px; height: 40px; border-radius: 50%; background: #667eea; 
                               border: none; color: white; cursor: pointer; font-size: 16px; 
                               box-shadow: 0 2px 10px rgba(0,0,0,0.2);">
                    🛠️
                </button>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', adminPanelHTML);
        
        // Start session timer
        this.startSessionTimer();
    }
    
    startSessionTimer() {
        setInterval(() => {
            const duration = Math.floor((new Date() - this.analyticsData.sessionStart) / 1000);
            const minutes = Math.floor(duration / 60);
            const seconds = duration % 60;
            document.getElementById('session-duration').textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
        }, 1000);
    }
    
    updateAnalyticsDisplay() {
        const elements = {
            'total-messages': this.analyticsData.totalMessages,
            'user-messages': this.analyticsData.userMessages,
            'bot-messages': this.analyticsData.botMessages
        };
        
        Object.keys(elements).forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = elements[id];
            }
        });
    }
    
    toggleAdminPanel() {
        const panel = document.getElementById('chatbox-admin-panel');
        const isVisible = panel.style.display !== 'none';
        panel.style.display = isVisible ? 'none' : 'block';
    }
    
    // Control Methods
    openChatbox() {
        if (this.chatbox) {
            this.chatbox.openChat();
        }
    }
    
    closeChatbox() {
        if (this.chatbox) {
            this.chatbox.closeChat();
        }
    }
    
    clearHistory() {
        if (this.chatbox) {
            this.chatbox.clearHistory();
            // Reset analytics
            this.analyticsData.totalMessages = 0;
            this.analyticsData.userMessages = 0;
            this.analyticsData.botMessages = 0;
            this.analyticsData.commonQuestions = {};
            this.updateAnalyticsDisplay();
        }
    }
    
    sendTestMessage(message) {
        if (this.chatbox) {
            if (!this.chatbox.isOpen) {
                this.chatbox.openChat();
            }
            setTimeout(() => {
                this.chatbox.sendMessage(message);
            }, 300);
        }
    }
    
    simulateTyping() {
        if (this.chatbox) {
            this.chatbox.showTyping();
            setTimeout(() => {
                this.chatbox.hideTyping();
                this.chatbox.addMessage('This is a simulated response for testing purposes.', 'bot');
            }, 2000);
        }
    }
    
    exportAnalytics() {
        const data = {
            ...this.analyticsData,
            sessionDuration: Math.floor((new Date() - this.analyticsData.sessionStart) / 1000),
            exportTime: new Date().toISOString()
        };
        
        // Convert to JSON and download
        const dataStr = JSON.stringify(data, null, 2);
        const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
        
        const exportFileDefaultName = `chatbox-analytics-${new Date().toISOString().split('T')[0]}.json`;
        
        const linkElement = document.createElement('a');
        linkElement.setAttribute('href', dataUri);
        linkElement.setAttribute('download', exportFileDefaultName);
        linkElement.click();
    }
    
    // Advanced Features
    injectCustomMessage(message, sender = 'bot') {
        if (this.chatbox) {
            this.chatbox.addMessage(message, sender);
        }
    }
    
    getAnalytics() {
        return { ...this.analyticsData };
    }
    
    setAutoResponse(trigger, response) {
        // This could be extended to create auto-responses for specific keywords
        console.log(`Auto-response set: "${trigger}" -> "${response}"`);
    }
}

// Initialize admin panel only in development or for admin users
document.addEventListener('DOMContentLoaded', function() {
    // Check if admin mode is enabled (you can modify this condition)
    const isAdminMode = window.location.search.includes('admin=true') || 
                       localStorage.getItem('chatbox-admin') === 'true' ||
                       document.body.classList.contains('admin-mode');
    
    if (isAdminMode) {
        window.chatboxAdmin = new ChatboxAdmin();
        
        // Add some helpful console messages
        console.log('🛠️ Chatbox Admin Panel loaded');
        console.log('Use chatboxAdmin.toggleAdminPanel() to show/hide admin controls');
        console.log('Use chatboxAdmin.getAnalytics() to get current analytics data');
    }
});

// Expose globally
window.ChatboxAdmin = ChatboxAdmin;