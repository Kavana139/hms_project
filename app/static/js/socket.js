/**
 * MediCore HMS — Global Socket.IO Client
 * Include this in all dashboard pages for real-time features
 */

class MediCoreSocket {
  constructor() {
    this.socket      = null;
    this.connected   = false;
    this.handlers    = {};
    this.reconnectDelay = 2000;
  }

  connect() {
    if (typeof io === 'undefined') {
      console.warn('Socket.IO not loaded');
      return;
    }
    this.socket = io({
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: this.reconnectDelay,
    });

    this.socket.on('connect', () => {
      this.connected = true;
      console.log('MediCore: Socket connected');
      this._updateLiveBadge(true);
    });

    this.socket.on('disconnect', () => {
      this.connected = false;
      this._updateLiveBadge(false);
    });

    this.socket.on('notification', (data) => {
      this._handleNotification(data);
    });

    this.socket.on('bed_changed', (data) => {
      this._trigger('bed_changed', data);
    });

    this.socket.on('ot_changed', (data) => {
      this._trigger('ot_changed', data);
    });

    this.socket.on('pong', () => {
      this.connected = true;
    });

    // Keep-alive ping every 30s
    setInterval(() => {
      if (this.socket && this.connected) {
        this.socket.emit('ping');
      }
    }, 30000);
  }

  on(event, handler) {
    if (!this.handlers[event]) this.handlers[event] = [];
    this.handlers[event].push(handler);
  }

  _trigger(event, data) {
    (this.handlers[event] || []).forEach(h => h(data));
  }

  _handleNotification(data) {
    // Update notification badge
    const badge = document.getElementById('notif-badge');
    if (badge) {
      badge.style.display = 'block';
      const current = parseInt(badge.textContent) || 0;
      badge.textContent  = current + 1 > 9 ? '9+' : current + 1;
    }

    // Show toast notification
    this._showToast(data);

    // Trigger custom handlers
    this._trigger('notification', data);
  }

  _showToast(data) {
    const colors = {
      info:    '#1a6fc4',
      success: '#0f9e75',
      warning: '#b45309',
      danger:  '#dc2626',
    };
    const color = colors[data.notif_type] || colors.info;

    const toast = document.createElement('div');
    toast.style.cssText = `
      position: fixed; bottom: 24px; right: 24px;
      background: ${color}; color: #fff;
      padding: 12px 18px; border-radius: 10px;
      font-size: 13px; max-width: 320px;
      box-shadow: 0 4px 20px rgba(0,0,0,.2);
      z-index: 9999; animation: slideIn .3s ease;
      cursor: pointer; line-height: 1.4;
    `;

    // Add animation keyframes once
    if (!document.getElementById('toast-styles')) {
      const style = document.createElement('style');
      style.id = 'toast-styles';
      style.textContent = `
        @keyframes slideIn {
          from { transform: translateX(120%); opacity: 0; }
          to   { transform: translateX(0);    opacity: 1; }
        }
        @keyframes slideOut {
          from { transform: translateX(0);    opacity: 1; }
          to   { transform: translateX(120%); opacity: 0; }
        }`;
      document.head.appendChild(style);
    }

    toast.innerHTML = `
      <div style="font-weight:600;margin-bottom:2px">${data.title || 'Notification'}</div>
      <div style="opacity:.85;font-size:12px">${data.message || ''}</div>`;

    toast.onclick = () => toast.remove();
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.style.animation = 'slideOut .3s ease forwards';
      setTimeout(() => toast.remove(), 300);
    }, 5000);
  }

  _updateLiveBadge(connected) {
    const badge = document.querySelector('.live-badge');
    const dot   = document.querySelector('.live-dot');
    if (!badge) return;
    if (connected) {
      if (dot) dot.style.background = 'var(--teal, #0f9e75)';
      badge.style.opacity = '1';
    } else {
      if (dot) dot.style.background = '#ef4444';
      badge.style.opacity = '.6';
    }
  }

  emit(event, data) {
    if (this.socket && this.connected) {
      this.socket.emit(event, data);
    }
  }
}

// Global instance
window.mediSocket = new MediCoreSocket();

// Auto-connect when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  window.mediSocket.connect();
});
