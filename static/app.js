/* static/app.js */
/**
 * RMS Query — Client Application Logic
 * Integrates frontend glassmorphism UI with Python Multi-Agent Backend:
 * - Mandatory Registration Number Login Gate before agent interaction
 * - Multi-View Routing: Chat Assistant, Track Your RMS, and RMS History
 * - Real-Time Stepper & Request Summary Routing Timeline
 * - KPI Metrics Cards & Interactive Request History Table
 * - Query routing & execution via /api/query
 * - Markdown parser with table rendering
 * - Voice dictation (Web Speech API)
 */

document.addEventListener('DOMContentLoaded', () => {
  // Application State
  const state = {
    isAuthenticated: false,
    currentStudent: {
      registration_no: '',
      student_name: 'Unauthenticated',
      department: '',
      semester: 0
    },
    currentView: 'chat', // 'chat' | 'track' | 'history'
    activeAgent: 'orchestrator',
    isProcessing: false,
    chatActive: false,
    tickets: [],
    stats: {
      total_requests: 0,
      resolved: 0,
      in_progress: 0,
      avg_resolution_days: 2.3
    },
    selectedTicketId: null,
    searchTerm: '',
    statusFilter: 'all',
    historyPeriod: '6months'
  };

  // DOM Elements - Views & Navigation
  const chatView = document.getElementById('chatView');
  const trackRmsView = document.getElementById('trackRmsView');
  const rmsHistoryView = document.getElementById('rmsHistoryView');
  const bottomDockWrapper = document.querySelector('.bottom-dock-wrapper');
  const viewPillBtns = document.querySelectorAll('.view-pill-btn');
  const sidebarNavItems = document.querySelectorAll('.sidebar-nav-item');
  const activeRmsBadge = document.getElementById('activeRmsBadge');
  const historyRmsBadge = document.getElementById('historyRmsBadge');

  // DOM Elements - Chat
  const heroContainer = document.getElementById('heroContainer');
  const chatStream = document.getElementById('chatStream');
  const messagesList = document.getElementById('messagesList');
  const chatForm = document.getElementById('chatForm');
  const queryInput = document.getElementById('queryInput');
  const micBtn = document.getElementById('mikeBtn') || document.getElementById('micBtn');
  const attachBtn = document.getElementById('attachBtn');
  const newChatBtn = document.getElementById('newChatBtn');
  const agentSelectorBtn = document.getElementById('agentSelectorBtn');
  const agentMenu = document.getElementById('agentMenu');
  const userProfileBtn = document.getElementById('userProfileBtn');
  const userNameLabel = document.getElementById('userNameLabel');
  const userRoleLabel = document.getElementById('userRoleLabel');
  const userAvatar = document.getElementById('userAvatar');
  const logoutBtn = document.getElementById('logoutBtn');
  const appLayout = document.querySelector('.app-layout');
  const sidebar = document.getElementById('sidebar');
  const sidebarCollapseBtn = document.getElementById('sidebarCollapseBtn');
  const sidebarSlideToggle = document.getElementById('sidebarSlideToggle') || document.getElementById('mobileSidebarToggle');
  const sidebarBackdrop = document.getElementById('sidebarBackdrop');
  const toast = document.getElementById('toast');

  // DOM Elements - Login Gate
  const loginModal = document.getElementById('loginModal');
  const loginForm = document.getElementById('loginForm');
  const loginRegInput = document.getElementById('loginRegInput');
  const loginErrorMsg = document.getElementById('loginErrorMsg');
  const loginSubmitBtn = document.getElementById('loginSubmitBtn');
  const demoChips = document.querySelectorAll('.demo-chip');

  // DOM Elements - Track Your RMS
  const rmsSearchInput = document.getElementById('rmsSearchInput');
  const rmsStatusFilter = document.getElementById('rmsStatusFilter');
  const rmsTicketsList = document.getElementById('rmsTicketsList');
  const activeCategoryIcon = document.getElementById('activeCategoryIcon');
  const activeRmsId = document.getElementById('activeRmsId');
  const activeRmsSubject = document.getElementById('activeRmsSubject');
  const activeRmsStatusBadge = document.getElementById('activeRmsStatusBadge');
  const rmsStepper = document.getElementById('rmsStepper');
  const handlerAvatar = document.getElementById('handlerAvatar');
  const handlerName = document.getElementById('handlerName');
  const handlerEmail = document.getElementById('handlerEmail');
  const expectedResolutionTime = document.getElementById('expectedResolutionTime');
  const summaryEstTime = document.getElementById('summaryEstTime');
  const vtCurrentStageName = document.getElementById('vtCurrentStageName');
  const vtNextStageName = document.getElementById('vtNextStageName');

  // DOM Elements - RMS History
  const historyPeriodFilter = document.getElementById('historyPeriodFilter');
  const metricTotal = document.getElementById('metricTotal');
  const metricResolved = document.getElementById('metricResolved');
  const metricInProgress = document.getElementById('metricInProgress');
  const metricAvgTime = document.getElementById('metricAvgTime');
  const historyTableBody = document.getElementById('historyTableBody');
  const historyViewAllBtn = document.getElementById('historyViewAllBtn');

  // Category Icon Map
  const categoryIcons = {
    'Hostel Related': '🛏️',
    'Certificate': '📜',
    'Fee Payment': '💳',
    'Course Registration': '🎓',
    'Internship NOC': '💼',
    'Examination': '📝',
    'Academic Mentor': '👨‍🏫',
    'IT Support': '💻',
    'Transport': '🚌',
    'Attendance': '⏱️',
    'Scholarship': '🏆'
  };

  // =========================================================================
  // MANDATORY LOGIN GATE LOGIC
  // =========================================================================
  async function checkAuthOnBoot() {
    const savedReg = sessionStorage.getItem('rms_authenticated_reg');
    if (savedReg) {
      await authenticateStudent(savedReg, false);
    } else {
      showLoginModal();
    }
  }

  function showLoginModal() {
    state.isAuthenticated = false;
    loginErrorMsg.classList.add('hidden');
    loginErrorMsg.textContent = '';
    loginRegInput.value = '';
    loginModal.showModal();
    loginRegInput.focus();
  }

  // Prevent closing login modal without authenticating
  loginModal.addEventListener('cancel', (e) => {
    if (!state.isAuthenticated) {
      e.preventDefault();
      showToast('Registration Number required to access portal.');
    }
  });

  loginModal.addEventListener('click', (e) => {
    if (e.target === loginModal && !state.isAuthenticated) {
      e.stopPropagation();
      showToast('Please enter your Registration Number to continue.');
    }
  });

  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const regNo = loginRegInput.value.trim();
    if (!regNo) return;

    loginSubmitBtn.disabled = true;
    loginSubmitBtn.innerHTML = `<span>Verifying...</span>`;

    const success = await authenticateStudent(regNo, true);
    loginSubmitBtn.disabled = false;
    loginSubmitBtn.innerHTML = `
      <span>Verify & Access Portal</span>
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
        <line x1="5" y1="12" x2="19" y2="12"></line>
        <polyline points="12 5 19 12 12 19"></polyline>
      </svg>
    `;

    if (success) {
      loginModal.close();
      showToast(`Welcome back, ${state.currentStudent.student_name}!`);
    }
  });

  // Quick Demo Account Chips
  demoChips.forEach(chip => {
    chip.addEventListener('click', () => {
      const reg = chip.getAttribute('data-reg');
      loginRegInput.value = reg;
      loginRegInput.focus();
    });
  });

  async function authenticateStudent(regNo, displayErrorInModal = true) {
    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ registration_no: regNo })
      });

      const data = await res.json();
      if (res.ok && data.success && data.student) {
        state.isAuthenticated = true;
        state.currentStudent = {
          registration_no: data.student.university_id,
          university_id: data.student.university_id,
          student_name: data.student.student_name,
          full_name: data.student.student_name,
          department: data.student.department,
          semester: data.student.semester,
          email: data.student.email
        };

        sessionStorage.setItem('rms_authenticated_reg', state.currentStudent.registration_no);

        // Update UI
        userNameLabel.textContent = state.currentStudent.student_name;
        userRoleLabel.textContent = `${state.currentStudent.registration_no} • Sem ${state.currentStudent.semester}`;
        const initials = state.currentStudent.student_name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
        userAvatar.textContent = initials || 'AS';

        // Load Tickets and Data
        await loadTickets();
        return true;
      } else {
        if (displayErrorInModal) {
          loginErrorMsg.textContent = data.error || `Registration No. '${regNo}' is not recognized in university database.`;
          loginErrorMsg.classList.remove('hidden');
        } else {
          showLoginModal();
        }
        return false;
      }
    } catch (err) {
      if (displayErrorInModal) {
        loginErrorMsg.textContent = 'Server connection error. Please ensure backend is running.';
        loginErrorMsg.classList.remove('hidden');
      }
      return false;
    }
  }

  // Logout / Switch Account
  if (logoutBtn) {
    logoutBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      sessionStorage.removeItem('rms_authenticated_reg');
      state.isAuthenticated = false;
      state.chatActive = false;
      messagesList.innerHTML = '';
      chatStream.classList.add('hidden');
      heroContainer.classList.remove('hidden');
      switchView('chat');
      showLoginModal();
      showToast('Logged out. Please authenticate with your Registration Number.');
    });
  }

  // =========================================================================
  // View Switching Router
  // =========================================================================
  function switchView(targetView) {
    if (!targetView) return;

    if (!state.isAuthenticated && targetView !== 'chat') {
      showLoginModal();
      return;
    }

    state.currentView = targetView;

    // Toggle Panels
    if (targetView === 'chat') {
      chatView.classList.remove('hidden');
      trackRmsView.classList.add('hidden');
      rmsHistoryView.classList.add('hidden');
      bottomDockWrapper.style.display = 'flex';
    } else if (targetView === 'track') {
      chatView.classList.add('hidden');
      trackRmsView.classList.remove('hidden');
      rmsHistoryView.classList.add('hidden');
      bottomDockWrapper.style.display = 'none';
      loadTickets().then(() => renderTrackRmsView());
    } else if (targetView === 'history') {
      chatView.classList.add('hidden');
      trackRmsView.classList.add('hidden');
      rmsHistoryView.classList.remove('hidden');
      bottomDockWrapper.style.display = 'none';
      loadTickets().then(() => renderHistoryView());
    }

    // Sync Top Nav Buttons (only buttons with data-view)
    viewPillBtns.forEach(btn => {
      const v = btn.getAttribute('data-view');
      if (v) {
        btn.classList.toggle('active', v === targetView);
      }
    });

    // Sync Sidebar Items (only items with data-view)
    sidebarNavItems.forEach(item => {
      const v = item.getAttribute('data-view');
      if (v) {
        item.classList.toggle('active', v === targetView);
      }
    });

    if (window.innerWidth <= 900) {
      sidebar.classList.remove('open');
      if (sidebarBackdrop) sidebarBackdrop.classList.remove('active');
    }
  }

  // =========================================================================
  // Tickets & Metrics Loading
  // =========================================================================
  async function loadTickets() {
    if (!state.currentStudent.registration_no) return;
    try {
      const res = await fetch(`/api/tickets?reg_no=${encodeURIComponent(state.currentStudent.registration_no)}`);
      if (res.ok) {
        const data = await res.json();
        state.tickets = data.tickets || [];
        state.stats = data.stats || state.stats;

        // Update badges
        if (activeRmsBadge) activeRmsBadge.textContent = `${state.stats.in_progress} Active`;
        if (historyRmsBadge) historyRmsBadge.textContent = `${state.stats.total_requests} Total`;

        // Default selected ticket
        if (state.tickets.length > 0) {
          const inProg = state.tickets.find(t => (t.status || '').toLowerCase() === 'in progress');
          state.selectedTicketId = inProg ? inProg.ticket_id : state.tickets[0].ticket_id;
        }

        if (state.currentView === 'track') renderTrackRmsView();
        if (state.currentView === 'history') renderHistoryView();
      }
    } catch (err) {
      console.warn('Tickets load error:', err);
    }
  }

  // =========================================================================
  // Render "Track Your RMS" View
  // =========================================================================
  function renderTrackRmsView() {
    const filtered = state.tickets.filter(t => {
      const matchesSearch = !state.searchTerm || 
        (t.ticket_id || '').toLowerCase().includes(state.searchTerm.toLowerCase()) ||
        (t.category || '').toLowerCase().includes(state.searchTerm.toLowerCase()) ||
        (t.query_text || '').toLowerCase().includes(state.searchTerm.toLowerCase());
      
      const matchesStatus = state.statusFilter === 'all' || 
        (t.status || '').toLowerCase() === state.statusFilter.toLowerCase();

      return matchesSearch && matchesStatus;
    });

    if (filtered.length === 0) {
      rmsTicketsList.innerHTML = `
        <div style="text-align: center; padding: 30px 10px; color: rgba(255,255,255,0.5);">
          <p>No matching RMS requests found for Reg No. ${state.currentStudent.registration_no}.</p>
        </div>
      `;
    } else {
      rmsTicketsList.innerHTML = filtered.map(t => {
        const isSelected = t.ticket_id === state.selectedTicketId;
        const icon = categoryIcons[t.category] || '📋';
        const isResolved = (t.status || '').toLowerCase() === 'resolved';
        const statusClass = isResolved ? 'status-resolved' : 'status-in-progress';

        return `
          <div class="rms-ticket-item ${isSelected ? 'active' : ''}" data-id="${t.ticket_id}">
            <div class="rms-icon-circle">${icon}</div>
            <div class="rms-ticket-item-content">
              <span class="rms-item-id">RMS #${escapeHtml(t.ticket_id)}</span>
              <h4 class="rms-item-subject">${escapeHtml(t.category || 'General Issue')}</h4>
              <span class="rms-item-date">Submitted on: ${escapeHtml(t.created_at || 'Recent')}</span>
            </div>
            <span class="rms-status-pill ${statusClass}">${escapeHtml(t.status || 'Active')}</span>
          </div>
        `;
      }).join('');

      document.querySelectorAll('.rms-ticket-item').forEach(card => {
        card.addEventListener('click', () => {
          const id = card.getAttribute('data-id');
          state.selectedTicketId = id;
          renderTrackRmsView();
        });
      });
    }

    const activeTicket = state.tickets.find(t => t.ticket_id === state.selectedTicketId) || filtered[0] || state.tickets[0];
    if (!activeTicket) return;

    const icon = categoryIcons[activeTicket.category] || '📋';
    const isResolved = (activeTicket.status || '').toLowerCase() === 'resolved';

    activeCategoryIcon.textContent = icon;
    activeRmsId.textContent = `RMS #${activeTicket.ticket_id}`;
    activeRmsSubject.textContent = activeTicket.query_text ? activeTicket.query_text.substring(0, 50) + (activeTicket.query_text.length > 50 ? '...' : '') : activeTicket.category;
    activeRmsStatusBadge.textContent = activeTicket.status || 'In Progress';
    activeRmsStatusBadge.className = `rms-status-badge ${isResolved ? 'status-resolved' : 'status-in-progress'}`;

    handlerName.textContent = activeTicket.assigned_officer || 'Hostel Office';
    handlerEmail.textContent = activeTicket.handler_email || 'support@lpu.in';
    expectedResolutionTime.textContent = activeTicket.estimated_resolution || 'In 2-3 Working Days';
    summaryEstTime.textContent = activeTicket.estimated_resolution || '2-3 Working Days';

    renderStepper(activeTicket);

    vtCurrentStageName.textContent = activeTicket.current_stage || activeTicket.assigned_officer || 'Hostel Office';
    vtNextStageName.textContent = activeTicket.next_stage || 'Dean (Hostel Affairs)';
  }

  function renderStepper(ticket) {
    const isResolved = (ticket.status || '').toLowerCase() === 'resolved';
    const progress = isResolved ? 4 : (ticket.stage_progress || 2);

    rmsStepper.innerHTML = `
      <!-- Step 1: Submitted -->
      <div class="step-node ${progress >= 1 ? 'step-completed' : 'step-pending'}">
        <div class="step-icon-circle">✓</div>
        <span class="step-title">Submitted</span>
        <span class="step-time">${escapeHtml(ticket.created_at || 'Recent')}</span>
      </div>

      <div class="step-line ${progress >= 2 ? 'step-line-completed' : ''}"></div>

      <!-- Step 2: Under Review -->
      <div class="step-node ${progress >= 2 ? (progress > 2 ? 'step-completed' : 'step-active') : 'step-pending'}">
        <div class="step-icon-circle">${progress >= 2 ? '✓' : ''}</div>
        <span class="step-title">Under Review</span>
        <span class="step-time">Same Day</span>
      </div>

      <div class="step-line ${progress >= 3 ? 'step-line-completed' : ''}"></div>

      <!-- Step 3: Assigned to Office -->
      <div class="step-node ${progress >= 3 ? (progress > 3 ? 'step-completed' : 'step-active') : 'step-pending'}">
        <div class="step-icon-circle">${progress >= 3 ? '✓' : ''}</div>
        <span class="step-title">Assigned to ${escapeHtml(ticket.assigned_officer || 'Office')}</span>
      </div>

      <div class="step-line ${progress >= 4 ? 'step-line-completed' : ''}"></div>

      <!-- Step 4: Resolution -->
      <div class="step-node ${progress >= 4 ? 'step-completed' : 'step-pending'}">
        <div class="step-icon-circle">${progress >= 4 ? '✓' : ''}</div>
        <span class="step-title">Resolution</span>
        <span class="step-time">${ticket.resolved_at ? escapeHtml(ticket.resolved_at) : 'Completed'}</span>
      </div>
    `;
  }

  // =========================================================================
  // Render "RMS History" View
  // =========================================================================
  function renderHistoryView() {
    metricTotal.textContent = state.stats.total_requests || state.tickets.length;
    metricResolved.textContent = state.stats.resolved || 0;
    metricInProgress.textContent = state.stats.in_progress || 0;
    metricAvgTime.textContent = `${state.stats.avg_resolution_days || 2.3} Days`;

    historyTableBody.innerHTML = state.tickets.map(t => {
      const isResolved = (t.status || '').toLowerCase() === 'resolved';
      const statusClass = isResolved ? 'status-resolved' : 'status-in-progress';
      const resolvedDate = t.resolved_at || '-';

      return `
        <tr data-id="${t.ticket_id}" title="Click to track RMS #${t.ticket_id}">
          <td class="history-row-id">${escapeHtml(t.ticket_id)}</td>
          <td>${escapeHtml(t.category || 'General')}</td>
          <td>${escapeHtml(t.created_at || 'Recent')}</td>
          <td><span class="rms-status-pill ${statusClass}">${escapeHtml(t.status || 'Active')}</span></td>
          <td>${escapeHtml(resolvedDate)}</td>
        </tr>
      `;
    }).join('');

    document.querySelectorAll('#historyTableBody tr').forEach(row => {
      row.addEventListener('click', () => {
        const id = row.getAttribute('data-id');
        if (id) {
          state.selectedTicketId = id;
          switchView('track');
          showToast(`Tracking RMS #${id}`);
        }
      });
    });
  }

  // =========================================================================
  // Query Dispatch & Chat Flow
  // =========================================================================
  async function handleSendQuery(text) {
    if (!state.isAuthenticated) {
      showLoginModal();
      showToast('Please authenticate with your Registration Number first.');
      return;
    }

    const query = (text || queryInput.value || '').trim();
    if (!query || state.isProcessing) return;

    if (state.currentView !== 'chat') {
      switchView('chat');
    }

    state.isProcessing = true;
    queryInput.value = '';

    if (!state.chatActive) {
      state.chatActive = true;
      heroContainer.classList.add('hidden');
      chatStream.classList.remove('hidden');
    }

    appendUserBubble(query);
    const typingRow = appendTypingIndicator();
    scrollChatToBottom();

    try {
      const response = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query,
          registration_no: state.currentStudent.registration_no,
          student_name: state.currentStudent.student_name,
          four_digit_number: (state.currentStudent.registration_no || '').slice(-4)
        })
      });

      const data = await response.json();
      typingRow.remove();

      if (data.success) {
        appendAgentBubble(data.response, {
          domain: data.domain,
          isFaq: data.is_faq,
          hops: data.total_hops,
          action: data.action,
          ticketId: data.ticket_id
        });
        await loadTickets();
        if (data.action === 'OPEN_TRACKER' && data.ticket_id) {
          state.selectedTicketId = data.ticket_id;
        }
      } else {
        if (response.status === 401 || response.status === 403) {
          showLoginModal();
        }
        appendAgentBubble(`⚠️ **System Notice**: ${data.error || 'The university service encountered an unexpected error.'}`);
      }
    } catch (err) {
      typingRow.remove();
      appendAgentBubble(`⚠️ **Network Error**: Unable to reach backend server. Please verify that the application server is running.`);
    } finally {
      state.isProcessing = false;
      scrollChatToBottom();
      queryInput.focus();
    }
  }

  function appendUserBubble(text) {
    const row = document.createElement('div');
    row.className = 'message-row-user';
    row.innerHTML = `<div class="bubble-user">${escapeHtml(text)}</div>`;
    messagesList.appendChild(row);
  }

  function appendTypingIndicator() {
    const row = document.createElement('div');
    row.className = 'message-row-agent';
    row.innerHTML = `
      <div class="agent-avatar-disc">🌱</div>
      <div class="bubble-agent">
        <div class="typing-indicator">
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
        </div>
      </div>
    `;
    messagesList.appendChild(row);
    return row;
  }

  function appendAgentBubble(rawMarkdown, meta = {}) {
    const row = document.createElement('div');
    row.className = 'message-row-agent';

    let domainTitle = 'University Agent';
    let domainIcon = '🎓';

    if (meta.domain === 'administration') {
      domainTitle = 'Administration & Fees';
      domainIcon = '🏛️';
    } else if (meta.domain === 'academic') {
      domainTitle = 'Chief Academic Dean';
      domainIcon = '🎓';
    } else if (meta.domain === 'examination') {
      domainTitle = 'Controller of Examinations';
      domainIcon = '📝';
    } else if (meta.domain === 'edu_revolution') {
      domainTitle = 'Edu-Revolution & Career';
      domainIcon = '💼';
    }

    const faqBadgeHtml = meta.isFaq 
      ? `<span class="faq-deflection-pill">⚡ Instant FAQ Deflection (Zero Model Cost)</span>` 
      : '';

    const formattedContent = parseMarkdown(rawMarkdown);

    let actionBtnHtml = '';
    if (meta.action === 'OPEN_TRACKER') {
      actionBtnHtml = `
        <div style="margin-top: 14px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.08);">
          <button class="quick-view-action-btn" data-action="track" data-tid="${meta.ticketId || ''}" style="background: rgba(59,130,246,0.15); color: #60a5fa; border: 1px solid rgba(59,130,246,0.35); padding: 7px 14px; border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; transition: all 0.2s ease;">
            📍 Open in Live RMS Tracker ➔
          </button>
        </div>
      `;
    } else if (meta.action === 'OPEN_HISTORY') {
      actionBtnHtml = `
        <div style="margin-top: 14px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.08);">
          <button class="quick-view-action-btn" data-action="history" style="background: rgba(16,185,129,0.15); color: #34d399; border: 1px solid rgba(16,185,129,0.35); padding: 7px 14px; border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; transition: all 0.2s ease;">
            📊 View Full RMS History Dashboard ➔
          </button>
        </div>
      `;
    }

    row.innerHTML = `
      <div class="agent-avatar-disc">${domainIcon}</div>
      <div class="bubble-agent">
        <div class="agent-badge-header">
          <span class="agent-name-badge">${escapeHtml(domainTitle)}</span>
          ${faqBadgeHtml}
        </div>
        <div class="agent-content-body">
          ${formattedContent}
          ${actionBtnHtml}
        </div>
      </div>
    `;

    // Bind Quick Navigation Button
    const actBtn = row.querySelector('.quick-view-action-btn');
    if (actBtn) {
      actBtn.addEventListener('click', () => {
        const act = actBtn.getAttribute('data-action');
        const tid = actBtn.getAttribute('data-tid');
        if (tid) state.selectedTicketId = tid;
        switchView(act);
      });
    }

    messagesList.appendChild(row);
  }

  function scrollChatToBottom() {
    chatStream.scrollTo({
      top: chatStream.scrollHeight,
      behavior: 'smooth'
    });
  }

  // =========================================================================
  // Lightweight Markdown & Table Parser
  // =========================================================================
  function parseMarkdown(md) {
    if (!md) return '';

    const lines = md.split('\n');
    let outputHtml = '';
    let inTable = false;
    let tableRows = [];

    function flushTable() {
      if (tableRows.length > 0) {
        let tableHtml = '<table>';
        let isFirstRowHeader = true;
        tableRows.forEach((row, idx) => {
          if (/^\|?(\s*:?-+:?\s*\|?)+$/.test(row.trim())) return;
          const cells = row.split('|').map(c => c.trim()).filter((c, i, arr) => {
            if ((i === 0 || i === arr.length - 1) && c === '') return false;
            return true;
          });

          if (cells.length > 0) {
            tableHtml += '<tr>';
            cells.forEach(cell => {
              if (idx === 0 && isFirstRowHeader) {
                tableHtml += `<th>${inlineFormat(cell)}</th>`;
              } else {
                tableHtml += `<td>${inlineFormat(cell)}</td>`;
              }
            });
            tableHtml += '</tr>';
          }
        });
        tableHtml += '</table>';
        outputHtml += tableHtml;
        tableRows = [];
        inTable = false;
      }
    }

    lines.forEach(line => {
      const trimmed = line.trim();

      if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
        inTable = true;
        tableRows.push(trimmed);
        return;
      } else if (inTable) {
        flushTable();
      }

      if (trimmed.startsWith('### ')) {
        outputHtml += `<h3>${inlineFormat(trimmed.substring(4))}</h3>`;
      } else if (trimmed.startsWith('## ')) {
        outputHtml += `<h2>${inlineFormat(trimmed.substring(3))}</h2>`;
      } else if (trimmed.startsWith('# ')) {
        outputHtml += `<h1>${inlineFormat(trimmed.substring(2))}</h1>`;
      } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        outputHtml += `<li>${inlineFormat(trimmed.substring(2))}</li>`;
      } else if (trimmed === '') {
        outputHtml += '<br/>';
      } else {
        outputHtml += `<p>${inlineFormat(trimmed)}</p>`;
      }
    });

    if (inTable) flushTable();
    return outputHtml;
  }

  function inlineFormat(text) {
    if (!text) return '';
    let s = escapeHtml(text);
    s = s.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/\*(.*?)\*/g, '<em>$1</em>');
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
    return s;
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // =========================================================================
  // Voice Dictation (Web Speech API)
  // =========================================================================
  // Speech-to-Text Integration (Faster-Whisper CPU Backend)
  // =========================================================================
  let mediaRecorder = null;
  let audioChunks = [];
  let isRecording = false;

  async function toggleSpeech() {
    if (!micBtn) return;

    if (isRecording) {
      if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
      }
      return;
    }

    // Try MediaRecorder API with Faster-Whisper backend
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioChunks = [];
        mediaRecorder = new MediaRecorder(stream);

        mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0) audioChunks.push(e.data);
        };

        mediaRecorder.onstart = () => {
          isRecording = true;
          micBtn.classList.add('recording');
          const label = micBtn.querySelector('.mike-label') || micBtn.querySelector('span');
          if (label) label.textContent = 'Listening...';
          showToast('🎤 Mike listening... Speak your query (Faster-Whisper STT).');
        };

        mediaRecorder.onstop = async () => {
          isRecording = false;
          micBtn.classList.remove('recording');
          const label = micBtn.querySelector('.mike-label') || micBtn.querySelector('span');
          if (label) label.textContent = 'Transcribing...';

          // Release tracks
          stream.getTracks().forEach(t => t.stop());

          const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
          const formData = new FormData();
          formData.append('audio', audioBlob, 'query_audio.wav');

          try {
            const res = await fetch('/api/transcribe', {
              method: 'POST',
              body: formData
            });
            const data = await res.json();
            if (data.success && data.text) {
              queryInput.value = data.text;
              showToast(`Heard: "${data.text}"`);
              handleSendQuery(data.text);
            } else {
              showToast(data.error || 'No speech detected.');
            }
          } catch (err) {
            showToast('Transcription service unavailable.');
          } finally {
            if (label) label.textContent = 'Mike';
          }
        };

        mediaRecorder.start();
        return;
      } catch (err) {
        console.warn('MediaRecorder error, falling back to Web Speech API:', err);
      }
    }

    // Web Speech API Fallback
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        micBtn.classList.add('recording');
        const label = micBtn.querySelector('.mike-label') || micBtn.querySelector('span');
        if (label) label.textContent = 'Listening...';
        showToast('Listening... Speak your query.');
      };

      recognition.onresult = (e) => {
        const transcript = e.results[0][0].transcript;
        queryInput.value = transcript;
        showToast(`Heard: "${transcript}"`);
        handleSendQuery(transcript);
      };

      recognition.onerror = (e) => {
        micBtn.classList.remove('recording');
        const label = micBtn.querySelector('.mike-label') || micBtn.querySelector('span');
        if (label) label.textContent = 'Mike';
        showToast(`Voice input: ${e.error || 'speech canceled'}`);
      };

      recognition.onend = () => {
        micBtn.classList.remove('recording');
        const label = micBtn.querySelector('.mike-label') || micBtn.querySelector('span');
        if (label) label.textContent = 'Mike';
      };

      recognition.start();
    } else {
      showToast('Microphone access is not supported in this browser.');
    }
  }

  // =========================================================================
  // Toast Notifications
  // =========================================================================
  let toastTimer = null;
  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.remove('hidden');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toast.classList.add('hidden');
    }, 3200);
  }

  // =========================================================================
  // Event Listeners
  // =========================================================================
  viewPillBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      const target = btn.getAttribute('data-view');
      if (target) {
        switchView(target);
      }
    });
  });

  sidebarNavItems.forEach(item => {
    item.addEventListener('click', (e) => {
      const target = item.getAttribute('data-view');
      if (target) {
        switchView(target);
      }
    });
  });

  if (chatForm) {
    chatForm.addEventListener('submit', (e) => {
      e.preventDefault();
      handleSendQuery();
    });
  }

  if (micBtn) {
    micBtn.addEventListener('click', toggleSpeech);
  }

  if (attachBtn) {
    attachBtn.addEventListener('click', () => {
      showToast('File attachment: Upload simulated.');
    });
  }

  // Dedicated Card 3: Track RMS Status
  const cardTrackRms = document.getElementById('cardTrackRms');
  if (cardTrackRms) {
    cardTrackRms.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      switchView('track');
    });
    cardTrackRms.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        e.stopPropagation();
        switchView('track');
      }
    });
  }

  // Dedicated Sidebar Track RMS button
  const navTrackBtn = document.getElementById('navTrackBtn');
  if (navTrackBtn) {
    navTrackBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      switchView('track');
    });
  }

  // Helpdesk & Tickets Modal close handlers
  const ticketsModal = document.getElementById('ticketsModal');
  const closeModalBtn = document.getElementById('closeModalBtn');
  const refreshTicketsBtn = document.getElementById('refreshTicketsBtn');
  if (closeModalBtn && ticketsModal) {
    closeModalBtn.addEventListener('click', () => {
      ticketsModal.close();
    });
  }
  if (ticketsModal) {
    ticketsModal.addEventListener('click', (e) => {
      if (e.target === ticketsModal) {
        ticketsModal.close();
      }
    });
  }
  if (refreshTicketsBtn) {
    refreshTicketsBtn.addEventListener('click', async () => {
      await loadTickets();
      showToast('Tickets refreshed.');
    });
  }

  // Generic Query Cards (Card 1: Ask Query) - excluding feedback card and track card
  document.querySelectorAll('.suggestion-card').forEach(card => {
    if (card.id === 'openFeedbackCard' || card.id === 'cardTrackRms') return;
    card.addEventListener('click', () => {
      const prompt = card.getAttribute('data-prompt');
      if (prompt) handleSendQuery(prompt);
    });
  });

  document.querySelectorAll('.history-item').forEach(item => {
    item.addEventListener('click', () => {
      const query = item.getAttribute('data-query');
      if (query) handleSendQuery(query);
      if (window.innerWidth <= 900) sidebar.classList.remove('open');
    });
  });

  newChatBtn.addEventListener('click', () => {
    switchView('chat');
    state.chatActive = false;
    messagesList.innerHTML = '';
    chatStream.classList.add('hidden');
    heroContainer.classList.remove('hidden');
    queryInput.value = '';
    queryInput.focus();
    showToast('Started new conversation session.');
  });

  if (rmsSearchInput) {
    rmsSearchInput.addEventListener('input', (e) => {
      state.searchTerm = e.target.value.trim();
      renderTrackRmsView();
    });
  }

  if (rmsStatusFilter) {
    rmsStatusFilter.addEventListener('change', (e) => {
      state.statusFilter = e.target.value;
      renderTrackRmsView();
    });
  }

  if (historyPeriodFilter) {
    historyPeriodFilter.addEventListener('change', (e) => {
      state.historyPeriod = e.target.value;
      showToast(`Showing requests for: ${e.target.options[e.target.selectedIndex].text}`);
    });
  }

  if (historyViewAllBtn) {
    historyViewAllBtn.addEventListener('click', () => {
      showToast(`Displaying all ${state.tickets.length} historical requests.`);
    });
  }

  agentSelectorBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    agentMenu.classList.toggle('hidden');
  });

  document.querySelectorAll('.agent-menu-item').forEach(item => {
    item.addEventListener('click', (e) => {
      e.stopPropagation();
      document.querySelectorAll('.agent-menu-item').forEach(i => i.classList.remove('active'));
      item.classList.add('active');
      const agentKey = item.getAttribute('data-agent');
      state.activeAgent = agentKey;
      agentMenu.classList.add('hidden');
      showToast(`Selected mode: ${item.querySelector('strong').textContent}`);
    });
  });

  document.addEventListener('click', () => {
    if (!agentMenu.classList.contains('hidden')) {
      agentMenu.classList.add('hidden');
    }
  });

  userProfileBtn.addEventListener('click', () => {
    if (state.isAuthenticated) {
      showToast(`Logged in: ${state.currentStudent.student_name} (${state.currentStudent.registration_no})`);
    } else {
      showLoginModal();
    }
  });

  // =========================================================================
  // Sliding Sidebar Toggle Engine (Desktop & Mobile)
  // =========================================================================
  function toggleSidebar(forceCollapse) {
    const isMobile = window.innerWidth <= 900;
    
    if (isMobile) {
      if (forceCollapse === true) {
        sidebar.classList.remove('open');
        if (sidebarBackdrop) sidebarBackdrop.classList.remove('active');
      } else if (forceCollapse === false) {
        sidebar.classList.add('open');
        if (sidebarBackdrop) sidebarBackdrop.classList.add('active');
      } else {
        const isOpen = sidebar.classList.toggle('open');
        if (sidebarBackdrop) sidebarBackdrop.classList.toggle('active', isOpen);
      }
    } else {
      if (forceCollapse === true) {
        appLayout.classList.add('sidebar-collapsed');
      } else if (forceCollapse === false) {
        appLayout.classList.remove('sidebar-collapsed');
      } else {
        appLayout.classList.toggle('sidebar-collapsed');
      }
      const isCollapsed = appLayout.classList.contains('sidebar-collapsed');
      localStorage.setItem('rms_sidebar_collapsed', isCollapsed ? 'true' : 'false');
      if (sidebarSlideToggle) {
        sidebarSlideToggle.title = isCollapsed ? 'Open sidebar (Slide to open • Cmd+B)' : 'Collapse sidebar (Slide to close • Cmd+B)';
      }
    }
  }

  // Restore user desktop preference
  if (window.innerWidth > 900 && localStorage.getItem('rms_sidebar_collapsed') === 'true') {
    appLayout.classList.add('sidebar-collapsed');
    if (sidebarSlideToggle) {
      sidebarSlideToggle.title = 'Open sidebar (Slide to open • Cmd+B)';
    }
  }

  window.addEventListener('resize', () => {
    if (window.innerWidth > 900) {
      if (sidebarBackdrop) sidebarBackdrop.classList.remove('active');
      if (sidebar) sidebar.classList.remove('open');
      const isCollapsed = localStorage.getItem('rms_sidebar_collapsed') === 'true';
      appLayout.classList.toggle('sidebar-collapsed', isCollapsed);
    }
  });

  if (sidebarCollapseBtn) {
    sidebarCollapseBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleSidebar(true);
    });
  }

  if (sidebarSlideToggle) {
    sidebarSlideToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      toggleSidebar();
    });
  }

  if (sidebarBackdrop) {
    sidebarBackdrop.addEventListener('click', () => {
      toggleSidebar(true);
    });
  }

  // Global Keyboard Shortcut: Cmd/Ctrl + B
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'b' && !['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
      e.preventDefault();
      toggleSidebar();
    }
  });

  // =========================================================================
  // Student Feedback System (Multiple-Choice & Free-Text)
  // =========================================================================
  const feedbackModal = document.getElementById('feedbackModal');
  const feedbackModalBackdrop = document.getElementById('feedbackModalBackdrop');
  const closeFeedbackModalBtn = document.getElementById('closeFeedbackModalBtn');
  const cancelFeedbackBtn = document.getElementById('cancelFeedbackBtn');
  const openFeedbackCard = document.getElementById('openFeedbackCard');
  const navFeedbackBtn = document.getElementById('navFeedbackBtn');
  const sidebarFeedbackBtn = document.getElementById('sidebarFeedbackBtn');
  const feedbackForm = document.getElementById('feedbackForm');
  const feedbackRatingInput = document.getElementById('feedbackRatingInput');
  const starRatingText = document.getElementById('starRatingText');
  const feedbackStudentDisplay = document.getElementById('feedbackStudentDisplay');
  const feedbackAnonymousCheck = document.getElementById('feedbackAnonymousCheck');
  const submitFeedbackBtn = document.getElementById('submitFeedbackBtn');
  const starBtns = document.querySelectorAll('.star-btn');

  const ratingDescriptions = {
    1: '1.0 — Poor',
    2: '2.0 — Fair',
    3: '3.0 — Good',
    4: '4.0 — Very Good',
    5: '5.0 — Excellent'
  };

  function openFeedbackModal() {
    if (!feedbackModal) return;
    const name = state.currentStudent ? (state.currentStudent.student_name || state.currentStudent.full_name) : null;
    const uid = state.currentStudent ? (state.currentStudent.registration_no || state.currentStudent.university_id) : null;
    if (name && uid) {
      feedbackStudentDisplay.textContent = `${name} (${uid})`;
    } else {
      feedbackStudentDisplay.textContent = 'Aditya Sharma (12204521)';
    }
    setRating(5);
    feedbackModal.classList.add('open');
    if (typeof feedbackModal.showModal === 'function') {
      try { 
        if (!feedbackModal.open) {
          feedbackModal.showModal(); 
        }
      } catch (e) {
        feedbackModal.setAttribute('open', '');
      }
    } else {
      feedbackModal.setAttribute('open', '');
    }
  }

  function closeFeedbackModal() {
    if (!feedbackModal) return;
    feedbackModal.classList.remove('open');
    if (typeof feedbackModal.close === 'function') {
      try { 
        if (feedbackModal.open) {
          feedbackModal.close(); 
        }
      } catch (e) {}
    }
    feedbackModal.removeAttribute('open');
  }

  // Hook dialog native events to ensure complete cleanup and prevent screen interference
  if (feedbackModal) {
    feedbackModal.addEventListener('cancel', () => {
      closeFeedbackModal();
    });
    feedbackModal.addEventListener('close', () => {
      feedbackModal.classList.remove('open');
      feedbackModal.removeAttribute('open');
    });
    feedbackModal.addEventListener('click', (e) => {
      if (e.target === feedbackModal || e.target === feedbackModalBackdrop) {
        closeFeedbackModal();
      }
    });
    const feedbackCard = feedbackModal.querySelector('.feedback-card');
    if (feedbackCard) {
      feedbackCard.addEventListener('click', (e) => {
        e.stopPropagation();
      });
    }
  }

  function setRating(val) {
    if (!feedbackRatingInput) return;
    feedbackRatingInput.value = val;
    if (starRatingText) {
      starRatingText.textContent = ratingDescriptions[val] || `${val}.0`;
    }
    starBtns.forEach(btn => {
      const btnVal = parseInt(btn.getAttribute('data-value'), 10);
      btn.classList.toggle('active', btnVal <= val);
    });
  }

  starBtns.forEach(btn => {
    btn.addEventListener('mouseenter', () => {
      const val = parseInt(btn.getAttribute('data-value'), 10);
      starBtns.forEach(b => {
        const bVal = parseInt(b.getAttribute('data-value'), 10);
        b.classList.toggle('hovered', bVal <= val);
      });
      if (starRatingText) {
        starRatingText.textContent = ratingDescriptions[val] || `${val}.0`;
      }
    });

    btn.addEventListener('mouseleave', () => {
      starBtns.forEach(b => b.classList.remove('hovered'));
      const current = parseInt(feedbackRatingInput.value || 5, 10);
      if (starRatingText) {
        starRatingText.textContent = ratingDescriptions[current] || `${current}.0`;
      }
    });

    btn.addEventListener('click', () => {
      const val = parseInt(btn.getAttribute('data-value'), 10);
      setRating(val);
    });
  });

  if (openFeedbackCard) {
    openFeedbackCard.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      openFeedbackModal();
    });
    openFeedbackCard.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        e.stopPropagation();
        openFeedbackModal();
      }
    });
  }

  if (navFeedbackBtn) {
    navFeedbackBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      openFeedbackModal();
    });
  }

  if (sidebarFeedbackBtn) {
    sidebarFeedbackBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      openFeedbackModal();
      if (window.innerWidth <= 900 && sidebar) {
        sidebar.classList.remove('open');
        if (sidebarBackdrop) sidebarBackdrop.classList.remove('active');
      }
    });
  }

  if (closeFeedbackModalBtn) {
    closeFeedbackModalBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      closeFeedbackModal();
    });
  }
  if (cancelFeedbackBtn) {
    cancelFeedbackBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      closeFeedbackModal();
    });
  }
  if (feedbackModalBackdrop) {
    feedbackModalBackdrop.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      closeFeedbackModal();
    });
  }

  if (feedbackAnonymousCheck) {
    feedbackAnonymousCheck.addEventListener('change', (e) => {
      if (e.target.checked) {
        feedbackStudentDisplay.textContent = 'Anonymous Student (Identity Hidden)';
      } else {
        const name = state.currentStudent ? (state.currentStudent.student_name || state.currentStudent.full_name) : null;
        const uid = state.currentStudent ? (state.currentStudent.registration_no || state.currentStudent.university_id) : null;
        if (name && uid) {
          feedbackStudentDisplay.textContent = `${name} (${uid})`;
        } else {
          feedbackStudentDisplay.textContent = 'Aditya Sharma (12204521)';
        }
      }
    });
  }

  if (feedbackForm) {
    feedbackForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const commentsInput = document.getElementById('feedbackCommentsInput');
      const likesInput = document.getElementById('feedbackLikesInput');
      const comments = commentsInput ? commentsInput.value.trim() : '';
      const suggestions = likesInput ? likesInput.value.trim() : '';

      if (!comments) {
        showToast('Please provide detailed feedback comments.', 'error');
        if (commentsInput) commentsInput.focus();
        return;
      }

      const categoryEl = feedbackForm.querySelector('input[name="category"]:checked');
      const category = categoryEl ? categoryEl.value : 'General Support';
      const rating = parseInt(feedbackRatingInput.value || 5, 10);
      const resQualityEl = feedbackForm.querySelector('input[name="resolution_quality"]:checked');
      const resolution_quality = resQualityEl ? resQualityEl.value : 'Satisfactory / Clear';
      const recEl = feedbackForm.querySelector('input[name="recommendation"]:checked');
      const recommendation = recEl ? recEl.value : 'Likely';
      const is_anonymous = feedbackAnonymousCheck ? feedbackAnonymousCheck.checked : false;

      const student_name = is_anonymous ? 'Anonymous Student' : (state.currentStudent ? (state.currentStudent.student_name || state.currentStudent.full_name || 'Aditya Sharma') : 'Aditya Sharma');
      const university_id = is_anonymous ? '' : (state.currentStudent ? (state.currentStudent.registration_no || state.currentStudent.university_id || '12204521') : '12204521');

      submitFeedbackBtn.disabled = true;
      submitFeedbackBtn.innerHTML = '<span>Submitting...</span>';

      try {
        const resp = await fetch('/api/feedback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            category,
            rating,
            resolution_quality,
            recommendation,
            comments,
            suggestions,
            is_anonymous,
            student_name,
            university_id
          })
        });

        const result = await resp.json();
        if (result.success) {
          showToast(`⭐ ${result.message || 'Feedback submitted successfully!'}`, 'success');
          feedbackForm.reset();
          setRating(5);
          closeFeedbackModal();
        } else {
          showToast(`Error: ${result.error || 'Failed to submit feedback.'}`, 'error');
        }
      } catch (err) {
        showToast(`Network error: ${err.message}`, 'error');
      } finally {
        submitFeedbackBtn.disabled = false;
        submitFeedbackBtn.innerHTML = `<span>Submit Feedback</span>
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>`;
      }
    });
  }

  // Bootstrap Authentication
  checkAuthOnBoot();
});
