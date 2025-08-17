/**
 * Gmail Email Clustering - Frontend Application
 * Handles user interface interactions and API communication
 */

class EmailClusteringApp {
    constructor() {
        this.isAuthenticated = false;
        this.userEmail = '';
        this.clusters = [];
        this.currentModal = null;
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.checkAuthStatus();
    }
    
    bindEvents() {
        // Authentication events
        document.addEventListener('click', (e) => {
            if (e.target.id === 'login-btn') {
                this.handleLogin();
            } else if (e.target.id === 'logout-btn') {
                this.handleLogout();
            }
        });
        
        // Email fetching events
        const fetchBtn = document.getElementById('fetch-emails-btn');
        if (fetchBtn) {
            fetchBtn.addEventListener('click', () => this.handleFetchEmails());
        }
        
        const emailInput = document.getElementById('email-input');
        if (emailInput) {
            emailInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.handleFetchEmails();
                }
            });
        }
        
        // Navigation events
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadClusters());
        }
        
        const newAnalysisBtn = document.getElementById('new-analysis-btn');
        if (newAnalysisBtn) {
            newAnalysisBtn.addEventListener('click', () => this.showEmailInput());
        }
        
        const retryBtn = document.getElementById('retry-btn');
        if (retryBtn) {
            retryBtn.addEventListener('click', () => this.hideError());
        }
        
        // Modal events
        this.bindModalEvents();
        
        // Cluster events (delegated)
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('archive-btn')) {
                const clusterId = parseInt(e.target.dataset.clusterId);
                const clusterName = e.target.dataset.clusterName;
                const emailCount = parseInt(e.target.dataset.emailCount);
                this.showArchiveConfirmation(clusterId, clusterName, emailCount);
            } else if (e.target.classList.contains('email-item') || e.target.closest('.email-item')) {
                const emailItem = e.target.classList.contains('email-item') ? e.target : e.target.closest('.email-item');
                const emailData = JSON.parse(emailItem.dataset.email);
                this.showEmailModal(emailData);
            }
        });
    }
    
    bindModalEvents() {
        // Email modal
        const emailModal = document.getElementById('email-modal');
        const emailModalClose = document.getElementById('modal-close');
        
        if (emailModalClose) {
            emailModalClose.addEventListener('click', () => this.hideModal('email-modal'));
        }
        
        if (emailModal) {
            emailModal.addEventListener('click', (e) => {
                if (e.target === emailModal) {
                    this.hideModal('email-modal');
                }
            });
        }
        
        // Archive modal
        const archiveModal = document.getElementById('archive-modal');
        const archiveModalClose = document.getElementById('archive-modal-close');
        const confirmArchiveBtn = document.getElementById('confirm-archive-btn');
        const cancelArchiveBtn = document.getElementById('cancel-archive-btn');
        
        if (archiveModalClose) {
            archiveModalClose.addEventListener('click', () => this.hideModal('archive-modal'));
        }
        
        if (cancelArchiveBtn) {
            cancelArchiveBtn.addEventListener('click', () => this.hideModal('archive-modal'));
        }
        
        if (confirmArchiveBtn) {
            confirmArchiveBtn.addEventListener('click', () => this.handleArchiveCluster());
        }
        
        if (archiveModal) {
            archiveModal.addEventListener('click', (e) => {
                if (e.target === archiveModal) {
                    this.hideModal('archive-modal');
                }
            });
        }
        
        // ESC key to close modals
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.currentModal) {
                this.hideModal(this.currentModal);
            }
        });
    }
    
    async checkAuthStatus() {
        try {
            const response = await fetch('/api/auth/status');
            const data = await response.json();
            
            this.isAuthenticated = data.authenticated;
            this.updateAuthUI();
            
            if (this.isAuthenticated) {
                this.showEmailInput();
            }
        } catch (error) {
            console.error('Error checking auth status:', error);
            this.updateAuthUI();
        }
    }
    
    updateAuthUI() {
        const authSection = document.getElementById('auth-section');
        
        if (this.isAuthenticated) {
            authSection.innerHTML = `
                <span>✅ Authenticated</span>
                <button id="logout-btn" class="btn btn-secondary">Logout</button>
            `;
        } else {
            authSection.innerHTML = `
                <button id="login-btn" class="btn btn-primary">🔐 Login with Gmail</button>
            `;
        }
    }
    
    async handleLogin() {
        try {
            const response = await fetch('/api/auth/login');
            const data = await response.json();
            
            if (data.success) {
                // For desktop app, show authorization URL instead of redirecting
                this.showAuthorizationFlow(data.authorization_url);
            } else {
                this.showError('Failed to initiate login: ' + data.error);
            }
        } catch (error) {
            console.error('Login error:', error);
            this.showError('Login failed. Please try again.');
        }
    }

    showAuthorizationFlow(authUrl) {
        // Create modal or section for manual OAuth flow
        const authSection = document.getElementById('auth-section');
        authSection.innerHTML = `
            <div class="oauth-flow" style="background: #f8f9fa; padding: 20px; border-radius: 8px; max-width: 600px; margin: 20px auto;">
                <h3 style="color: #495057; margin-bottom: 15px;">🔐 Gmail Authorization Required</h3>
                <div style="margin-bottom: 15px;">
                    <strong>Step 1:</strong> 
                    <a href="${authUrl}" target="_blank" class="btn btn-primary">
                        🔗 Click here to authorize with Gmail
                    </a>
                </div>
                <div style="margin-bottom: 15px; padding: 10px; background: #e9ecef; border-radius: 4px;">
                    <strong>Step 2:</strong> After authorizing, Google will show you an authorization code or redirect to a page with the code in the URL. 
                    <br><strong>Note:</strong> If you see "This site can't be reached" or "localhost refused to connect", that's normal! 
                    <br>Just look at the URL in your browser address bar - it will contain <code>code=...</code>
                    <br>Copy everything after <code>code=</code> and before any <code>&</code> symbol.
                </div>
                <div class="input-group" style="display: flex; gap: 10px;">
                    <input type="text" id="auth-code" placeholder="Paste authorization code here" 
                           style="flex: 1; padding: 10px; border: 1px solid #ced4da; border-radius: 4px;" />
                    <button id="submit-code-btn" class="btn btn-secondary">Submit Code</button>
                </div>
                <div style="margin-top: 10px; font-size: 0.9em; color: #6c757d;">
                    The authorization code is a long string of letters and numbers.
                </div>
            </div>
        `;
        
        // Add event listener for code submission
        document.getElementById('submit-code-btn').addEventListener('click', () => {
            this.submitAuthorizationCode();
        });
    }

    async submitAuthorizationCode() {
        const code = document.getElementById('auth-code').value.trim();
        if (!code) {
            this.showError('Please enter the authorization code');
            return;
        }

        try {
            const response = await fetch('/api/auth/callback', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ code: code })
            });
            
            console.log('Response status:', response.status);
            console.log('Response headers:', response.headers);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log('Response data:', data);
            
            if (data.success) {
                this.showMessage('Successfully authenticated!');
                await this.checkAuthStatus();
            } else {
                this.showError('Authentication failed: ' + (data.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Code submission error:', error);
            this.showError('Failed to submit authorization code: ' + error.message);
        }
    }
    
    async handleLogout() {
        try {
            const response = await fetch('/api/auth/logout', {
                method: 'POST'
            });
            
            if (response.ok) {
                this.isAuthenticated = false;
                this.userEmail = '';
                this.clusters = [];
                this.updateAuthUI();
                this.showWelcome();
            }
        } catch (error) {
            console.error('Logout error:', error);
        }
    }
    
    showWelcome() {
        this.hideAllSections();
        document.getElementById('welcome-section').classList.remove('hidden');
    }
    
    showEmailInput() {
        this.hideAllSections();
        document.getElementById('email-input-section').classList.remove('hidden');
        
        // Focus on email input
        const emailInput = document.getElementById('email-input');
        if (emailInput) {
            emailInput.focus();
        }
    }
    
    showLoading(title = 'Processing your emails...', message = 'This may take a few moments') {
        this.hideAllSections();
        
        const loadingSection = document.getElementById('loading-section');
        const loadingTitle = document.getElementById('loading-title');
        const loadingMessage = document.getElementById('loading-message');
        
        loadingTitle.textContent = title;
        loadingMessage.textContent = message;
        
        loadingSection.classList.remove('hidden');
        
        // Reset step statuses
        document.querySelectorAll('.step').forEach(step => {
            step.classList.remove('completed', 'active');
            const status = step.querySelector('.step-status');
            status.textContent = '⏳';
        });
    }
    
    updateLoadingStep(stepId, status = 'active') {
        const step = document.getElementById(stepId);
        if (!step) return;
        
        const statusElement = step.querySelector('.step-status');
        
        if (status === 'completed') {
            step.classList.add('completed');
            step.classList.remove('active');
            statusElement.textContent = '✅';
        } else if (status === 'active') {
            step.classList.add('active');
            step.classList.remove('completed');
            statusElement.textContent = '⏳';
        }
    }
    
    showClusters() {
        this.hideAllSections();
        document.getElementById('clusters-section').classList.remove('hidden');
    }
    
    showError(message) {
        this.hideAllSections();
        
        const errorSection = document.getElementById('error-section');
        const errorMessage = document.getElementById('error-message');
        
        errorMessage.textContent = message;
        errorSection.classList.remove('hidden');
    }
    
    hideError() {
        if (this.clusters.length > 0) {
            this.showClusters();
        } else if (this.isAuthenticated) {
            this.showEmailInput();
        } else {
            this.showWelcome();
        }
    }
    
    hideAllSections() {
        const sections = [
            'welcome-section',
            'email-input-section', 
            'loading-section',
            'clusters-section',
            'error-section'
        ];
        
        sections.forEach(sectionId => {
            const section = document.getElementById(sectionId);
            if (section) {
                section.classList.add('hidden');
            }
        });
    }
    
    async handleFetchEmails() {
        const emailInput = document.getElementById('email-input');
        const fetchBtn = document.getElementById('fetch-emails-btn');
        
        if (!emailInput || !fetchBtn) return;
        
        const email = emailInput.value.trim();
        
        if (!email) {
            this.showError('Please enter your Gmail address');
            return;
        }
        
        if (!this.isValidEmail(email)) {
            this.showError('Please enter a valid email address');
            return;
        }
        
        this.userEmail = email;
        
        // Disable button and show loading
        fetchBtn.disabled = true;
        fetchBtn.querySelector('.btn-text').textContent = 'Processing...';
        fetchBtn.querySelector('.btn-spinner').classList.remove('hidden');
        
        this.showLoading();
        
        try {
            // Step 1: Fetching emails
            this.updateLoadingStep('step-fetch', 'active');
            
            const response = await fetch('/api/emails/fetch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ email: email })
            });
            
            const data = await response.json();
            
            if (!data.success) {
                throw new Error(data.error || 'Failed to fetch emails');
            }
            
            // Step 2: Processing completed
            this.updateLoadingStep('step-fetch', 'completed');
            this.updateLoadingStep('step-process', 'completed');
            this.updateLoadingStep('step-cluster', 'completed');
            
            // Show results
            this.clusters = data.clusters || [];
            this.displayClusters();
            
            // Small delay to show completion
            setTimeout(() => {
                this.showClusters();
            }, 1000);
            
        } catch (error) {
            console.error('Fetch emails error:', error);
            this.showError(error.message || 'Failed to fetch and cluster emails');
        } finally {
            // Re-enable button
            fetchBtn.disabled = false;
            fetchBtn.querySelector('.btn-text').textContent = 'Fetch & Cluster Emails';
            fetchBtn.querySelector('.btn-spinner').classList.add('hidden');
        }
    }
    
    async loadClusters() {
        try {
            const response = await fetch('/api/clusters');
            const data = await response.json();
            
            if (data.success) {
                this.clusters = data.clusters || [];
                this.displayClusters();
            } else {
                this.showError(data.error || 'Failed to load clusters');
            }
        } catch (error) {
            console.error('Load clusters error:', error);
            this.showError('Failed to load clusters');
        }
    }
    
    displayClusters() {
        const container = document.getElementById('clusters-container');
        const clusterCount = document.getElementById('cluster-count');
        const emailCount = document.getElementById('email-count');
        
        if (!container) return;
        
        // Update summary
        const totalEmails = this.clusters.reduce((sum, cluster) => sum + cluster.email_count, 0);
        if (clusterCount) clusterCount.textContent = this.clusters.length;
        if (emailCount) emailCount.textContent = totalEmails;
        
        // Clear container
        container.innerHTML = '';
        
        if (this.clusters.length === 0) {
            container.innerHTML = `
                <div class="no-clusters">
                    <p>No email clusters found. Try fetching your emails first.</p>
                </div>
            `;
            return;
        }
        
        // Create cluster cards
        this.clusters.forEach(cluster => {
            const clusterCard = this.createClusterCard(cluster);
            container.appendChild(clusterCard);
        });
    }
    
    createClusterCard(cluster) {
        const card = document.createElement('div');
        card.className = 'cluster-card fade-in';
        
        const emails = cluster.emails || [];
        const emailsHtml = emails.slice(0, 5).map(email => `
            <div class="email-item" data-email='${JSON.stringify(email)}'>
                <div class="email-subject">${this.escapeHtml(email.subject || 'No Subject')}</div>
                <div class="email-sender">${this.escapeHtml(email.sender || 'Unknown Sender')}</div>
                <div class="email-preview">${this.escapeHtml(this.truncateText(email.body || '', 100))}</div>
            </div>
        `).join('');
        
        const moreEmailsText = emails.length > 5 ? `<div class="more-emails">... and ${emails.length - 5} more emails</div>` : '';
        
        card.innerHTML = `
            <div class="cluster-header">
                <h3 class="cluster-title">${this.escapeHtml(cluster.label)}</h3>
                <p class="cluster-description">${this.escapeHtml(cluster.description)}</p>
                <div class="cluster-meta">
                    <span>${cluster.email_count} emails</span>
                    <span>Cluster #${cluster.id}</span>
                </div>
            </div>
            <div class="cluster-body">
                <div class="email-list">
                    ${emailsHtml}
                    ${moreEmailsText}
                </div>
            </div>
            <div class="cluster-actions">
                <span class="cluster-stats">${cluster.email_count} emails</span>
                <button class="archive-btn" 
                        data-cluster-id="${cluster.id}"
                        data-cluster-name="${this.escapeHtml(cluster.label)}"
                        data-email-count="${cluster.email_count}">
                    📁 Archive Cluster
                </button>
            </div>
        `;
        
        return card;
    }
    
    showEmailModal(email) {
        const modal = document.getElementById('email-modal');
        const subject = document.getElementById('modal-subject');
        const sender = document.getElementById('modal-sender');
        const date = document.getElementById('modal-date');
        const body = document.getElementById('modal-body');
        
        if (!modal) return;
        
        subject.textContent = email.subject || 'No Subject';
        sender.textContent = email.sender || 'Unknown Sender';
        date.textContent = email.date_received ? new Date(email.date_received).toLocaleString() : 'Unknown Date';
        body.textContent = email.body || 'No content available';
        
        this.showModal('email-modal');
    }
    
    showArchiveConfirmation(clusterId, clusterName, emailCount) {
        const modal = document.getElementById('archive-modal');
        const clusterNameSpan = document.getElementById('archive-cluster-name');
        const emailCountSpan = document.getElementById('archive-email-count');
        const confirmBtn = document.getElementById('confirm-archive-btn');
        
        if (!modal) return;
        
        clusterNameSpan.textContent = clusterName;
        emailCountSpan.textContent = emailCount;
        
        // Store cluster ID for confirmation
        confirmBtn.dataset.clusterId = clusterId;
        
        this.showModal('archive-modal');
    }
    
    async handleArchiveCluster() {
        const confirmBtn = document.getElementById('confirm-archive-btn');
        const clusterId = parseInt(confirmBtn.dataset.clusterId);
        
        if (!clusterId || !this.userEmail) return;
        
        // Disable button and show loading
        confirmBtn.disabled = true;
        confirmBtn.textContent = 'Archiving...';
        
        try {
            const response = await fetch(`/api/clusters/${clusterId}/archive`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ email: this.userEmail })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Hide modal
                this.hideModal('archive-modal');
                
                // Remove cluster from display
                this.clusters = this.clusters.filter(cluster => cluster.id !== clusterId);
                this.displayClusters();
                
                // Show success message
                this.showTemporaryMessage('Cluster archived successfully!', 'success');
            } else {
                throw new Error(data.error || 'Failed to archive cluster');
            }
        } catch (error) {
            console.error('Archive error:', error);
            this.showTemporaryMessage(error.message || 'Failed to archive cluster', 'error');
        } finally {
            // Re-enable button
            confirmBtn.disabled = false;
            confirmBtn.textContent = 'Archive Emails';
        }
    }
    
    showModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('hidden');
            this.currentModal = modalId;
            document.body.style.overflow = 'hidden';
        }
    }
    
    hideModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('hidden');
            this.currentModal = null;
            document.body.style.overflow = '';
        }
    }
    
    showTemporaryMessage(message, type = 'info') {
        // Create temporary message element
        const messageEl = document.createElement('div');
        messageEl.className = `temp-message temp-message-${type}`;
        messageEl.textContent = message;
        messageEl.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 1rem 1.5rem;
            border-radius: 8px;
            color: white;
            font-weight: 500;
            z-index: 2000;
            animation: slideIn 0.3s ease-out;
            background: ${type === 'success' ? '#28a745' : type === 'error' ? '#dc3545' : '#667eea'};
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        `;
        
        document.body.appendChild(messageEl);
        
        // Remove after 3 seconds
        setTimeout(() => {
            messageEl.style.animation = 'slideOut 0.3s ease-in';
            setTimeout(() => {
                if (messageEl.parentNode) {
                    messageEl.parentNode.removeChild(messageEl);
                }
            }, 300);
        }, 3000);
    }
    
    // Utility functions
    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    truncateText(text, maxLength) {
        if (!text) return '';
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }
}

// Add CSS animations for temporary messages
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new EmailClusteringApp();
});