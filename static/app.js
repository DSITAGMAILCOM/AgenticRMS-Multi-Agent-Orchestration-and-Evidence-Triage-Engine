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
  const API_BASE = (window.BACKEND_API_URL || localStorage.getItem('backend_api_url') || '').replace(/\/$/, '');

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
    historyPeriod: 'all',
    ticketChats: {},
    queryHistory: []
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

  // DOM Elements - Ticket Follow-Up & Appeal AI Chat
  const ticketChatCard = document.getElementById('ticketChatCard');
  const ticketChatContextBadge = document.getElementById('ticketChatContextBadge');
  const ticketChatStream = document.getElementById('ticketChatStream');
  const ticketChatForm = document.getElementById('ticketChatForm');
  const ticketChatInput = document.getElementById('ticketChatInput');
  const ticketChatMikeBtn = document.getElementById('ticketChatMikeBtn');
  const ticketChatSendBtn = document.getElementById('ticketChatSendBtn');
  const ticketChatChips = document.querySelectorAll('.t-chip');

  // DOM Elements - RMS History
  const historyPeriodFilter = document.getElementById('historyPeriodFilter');
  const metricTotal = document.getElementById('metricTotal');
  const metricResolved = document.getElementById('metricResolved');
  const metricInProgress = document.getElementById('metricInProgress');
  const metricAvgTime = document.getElementById('metricAvgTime');
  const historyTableBody = document.getElementById('historyTableBody');
  const historyViewAllBtn = document.getElementById('historyViewAllBtn');

  // DOM Elements - Sidebar Conversation History
  const sidebarHistoryContainer = document.getElementById('sidebarHistoryContainer');
  const historyGroupToday = document.getElementById('historyGroupToday');
  const historyGroupYesterday = document.getElementById('historyGroupYesterday');
  const historyGroupPrevious = document.getElementById('historyGroupPrevious');
  const historySectionToday = document.getElementById('historySectionToday');
  const historySectionYesterday = document.getElementById('historySectionYesterday');
  const historySectionPrevious = document.getElementById('historySectionPrevious');

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
      const res = await fetch(`${API_BASE}/api/login`, {
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
        await Promise.all([loadTickets(), loadQueryHistory()]);
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
      state.queryHistory = [];
      state.tickets = [];
      renderSidebarHistory();
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
      Promise.all([loadTickets(), loadQueryHistory()]).then(() => renderHistoryView());
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
      const res = await fetch(`${API_BASE}/api/tickets?reg_no=${encodeURIComponent(state.currentStudent.registration_no)}`);
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
  // Query History Loading & Dynamic Sidebar History
  // =========================================================================
  async function loadQueryHistory() {
    if (!state.currentStudent.registration_no) return;
    try {
      const res = await fetch(`${API_BASE}/api/history?reg_no=${encodeURIComponent(state.currentStudent.registration_no)}`);
      if (res.ok) {
        const data = await res.json();
        state.queryHistory = data.history || [];
        renderSidebarHistory();
      }
    } catch (err) {
      console.warn('Query history load error:', err);
    }
  }

  function renderSidebarHistory() {
    if (!historyGroupToday) return;

    const todayItems = [];
    const yesterdayItems = [];
    const olderItems = [];

    const now = new Date();
    const todayStr = now.toISOString().split('T')[0];

    const yDate = new Date();
    yDate.setDate(yDate.getDate() - 1);
    const yesterdayStr = yDate.toISOString().split('T')[0];

    (state.queryHistory || []).forEach(item => {
      const createdStr = item.created_at || '';
      const datePart = createdStr.split(' ')[0] || createdStr.split('T')[0];

      if (datePart === todayStr) {
        todayItems.push(item);
      } else if (datePart === yesterdayStr) {
        yesterdayItems.push(item);
      } else {
        olderItems.push(item);
      }
    });

    const createHistoryHtml = (item) => {
      const q = item.raw_query || 'Inquiry';
      const short = q.length > 34 ? q.substring(0, 32) + '...' : q;
      return `
        <div class="history-item" data-query="${escapeHtml(q)}" title="${escapeHtml(q)}">
          <svg class="chat-bubble-icon" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
          <span class="history-label">${escapeHtml(short)}</span>
        </div>
      `;
    };

    // Render Today
    if (todayItems.length > 0) {
      historyGroupToday.innerHTML = todayItems.map(createHistoryHtml).join('');
      if (historySectionToday) historySectionToday.style.display = 'block';
    } else {
      historyGroupToday.innerHTML = `
        <div class="history-item empty-history" style="opacity: 0.6; font-size: 11px; padding: 6px 10px; cursor: default;">
          <span>No queries logged today yet</span>
        </div>
      `;
    }

    // Render Yesterday
    if (yesterdayItems.length > 0) {
      historyGroupYesterday.innerHTML = yesterdayItems.map(createHistoryHtml).join('');
      if (historySectionYesterday) historySectionYesterday.style.display = 'block';
    } else {
      if (historySectionYesterday) historySectionYesterday.style.display = 'none';
    }

    // Render Older
    if (olderItems.length > 0) {
      historyGroupPrevious.innerHTML = olderItems.map(createHistoryHtml).join('');
      if (historySectionPrevious) historySectionPrevious.style.display = 'block';
    } else {
      if (historySectionPrevious) historySectionPrevious.style.display = 'none';
    }

    // Attach click listeners to all active dynamic history items
    document.querySelectorAll('.history-items-group .history-item:not(.empty-history)').forEach(el => {
      el.addEventListener('click', () => {
        const query = el.getAttribute('data-query');
        if (query) {
          switchView('chat');
          handleSendQuery(query);
          if (window.innerWidth <= 900) {
            sidebar.classList.remove('open');
            if (sidebarBackdrop) sidebarBackdrop.classList.remove('active');
          }
        }
      });
    });
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

    // Render Official Human Committee Resolution Notes with Attribution
    const rmsHumanResolutionCard = document.getElementById('rmsHumanResolutionCard');
    const resOfficerAttribution = document.getElementById('resOfficerAttribution');
    const resNotesText = document.getElementById('resNotesText');

    if (rmsHumanResolutionCard && resNotesText) {
      if (activeTicket.human_resolution_notes && activeTicket.human_resolution_notes.trim()) {
        rmsHumanResolutionCard.classList.remove('hidden');
        if (resOfficerAttribution) {
          resOfficerAttribution.textContent = activeTicket.assigned_officer || 'Human Committee';
        }
        resNotesText.textContent = activeTicket.human_resolution_notes;
      } else {
        rmsHumanResolutionCard.classList.add('hidden');
      }
    }

    // Render Interactive Ticket Follow-Up & Appeal AI Chat
    renderTicketChat(activeTicket);
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
  // Ticket Follow-Up & Appeal AI Chat Logic
  // =========================================================================
  function renderTicketChat(ticket) {
    if (!ticket || !ticketChatStream) return;

    if (ticketChatContextBadge) {
      ticketChatContextBadge.textContent = `RMS #${ticket.ticket_id}`;
    }

    if (!state.ticketChats[ticket.ticket_id]) {
      const studentName = state.currentStudent.student_name ? state.currentStudent.student_name.split(' ')[0] : 'Student';
      const isResolved = (ticket.status || '').toLowerCase() === 'resolved';
      const isAppeal = (ticket.status || '').toUpperCase() === 'APPEAL_UNDER_REVIEW';

      let welcomeText = `Dear ${studentName}, I have loaded the live records for Ticket #${ticket.ticket_id} (${ticket.category || 'General Inquiry'}). `;
      if (isAppeal) {
        welcomeText += `Your ticket is currently under review by the higher committee as an active appeal. How may I assist you further?`;
      } else if (isResolved) {
        welcomeText += `The committee has marked this request as Resolved. If you are not satisfied with this outcome or need any clarification, please let me know and I will gladly register your appeal and assist you.`;
      } else {
        welcomeText += `Your request is currently marked as ${ticket.status || 'In Progress'} with ${ticket.assigned_officer || 'the designated department'}. You can ask questions, seek clarification, or file an appeal at any time.`;
      }

      state.ticketChats[ticket.ticket_id] = [
        {
          role: 'ai',
          sender: 'AI Ticket Specialist',
          text: welcomeText,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ];
    }

    const msgs = state.ticketChats[ticket.ticket_id] || [];
    ticketChatStream.innerHTML = msgs.map(m => `
      <div class="ticket-msg ${m.role}">
        <span class="ticket-msg-meta">${m.role === 'user' ? 'You' : escapeHtml(m.sender || 'AI Assistant')} • ${escapeHtml(m.time || '')}</span>
        <div>${escapeHtml(m.text)}</div>
      </div>
    `).join('');

    ticketChatStream.scrollTop = ticketChatStream.scrollHeight;
  }

  async function handleSendTicketChat(text) {
    const activeTicket = state.tickets.find(t => t.ticket_id === state.selectedTicketId);
    if (!activeTicket) {
      showToast('Please select a ticket to continue.');
      return;
    }
    const query = (text || (ticketChatInput ? ticketChatInput.value : '')).trim();
    if (!query) return;

    if (ticketChatInput) ticketChatInput.value = '';

    const nowTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    if (!state.ticketChats[activeTicket.ticket_id]) {
      state.ticketChats[activeTicket.ticket_id] = [];
    }
    state.ticketChats[activeTicket.ticket_id].push({
      role: 'user',
      sender: 'You',
      text: query,
      time: nowTime
    });
    renderTicketChat(activeTicket);

    if (ticketChatSendBtn) ticketChatSendBtn.disabled = true;
    if (ticketChatInput) ticketChatInput.disabled = true;

    const thinkingNode = document.createElement('div');
    thinkingNode.className = 'ticket-msg ai';
    thinkingNode.id = 'ticketChatThinkingBubble';
    thinkingNode.innerHTML = `
      <span class="ticket-msg-meta">AI Assistant • Ticket Specialist</span>
      <div style="display: flex; align-items: center; gap: 8px; color: #94a3b8;">
        <span>Reviewing ticket records and preparing response</span>
        <span class="loading-dots">...</span>
      </div>
    `;
    ticketChatStream.appendChild(thinkingNode);
    ticketChatStream.scrollTop = ticketChatStream.scrollHeight;

    try {
      const res = await fetch(`${API_BASE}/api/ticket/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticket_id: activeTicket.ticket_id,
          query: query,
          reg_no: state.currentStudent.registration_no
        })
      });

      const data = await res.json();
      const bubble = document.getElementById('ticketChatThinkingBubble');
      if (bubble) bubble.remove();

      if (data.success) {
        state.ticketChats[activeTicket.ticket_id].push({
          role: 'ai',
          sender: 'AI Ticket Specialist',
          text: data.response,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        });

        if (data.reopened || (data.status && data.status !== activeTicket.status)) {
          activeTicket.status = data.status || 'APPEAL_UNDER_REVIEW';
          activeTicket.stage_progress = 2;
          showToast(`Appeal registered: Ticket #${activeTicket.ticket_id} status updated to ${activeTicket.status}`);
          renderTrackRmsView();
        } else {
          renderTicketChat(activeTicket);
        }
      } else {
        state.ticketChats[activeTicket.ticket_id].push({
          role: 'ai',
          sender: 'System',
          text: data.error || 'Unable to process your request at this time. Please try again.',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        });
        renderTicketChat(activeTicket);
      }
    } catch (err) {
      const bubble = document.getElementById('ticketChatThinkingBubble');
      if (bubble) bubble.remove();
      console.error('Ticket chat error:', err);
      state.ticketChats[activeTicket.ticket_id].push({
        role: 'ai',
        sender: 'System',
        text: 'Network error communicating with the ticket assistant. Please try again shortly.',
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      });
      renderTicketChat(activeTicket);
    } finally {
      if (ticketChatSendBtn) ticketChatSendBtn.disabled = false;
      if (ticketChatInput) {
        ticketChatInput.disabled = false;
        ticketChatInput.focus();
      }
    }
  }

  let ticketMediaRecorder = null;
  let ticketAudioChunks = [];
  let isTicketRecording = false;

  async function toggleTicketSpeech() {
    if (!ticketChatMikeBtn || !ticketChatInput) return;

    if (isTicketRecording) {
      if (ticketMediaRecorder && ticketMediaRecorder.state !== 'inactive') {
        ticketMediaRecorder.stop();
      }
      return;
    }

    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        ticketAudioChunks = [];
        ticketMediaRecorder = new MediaRecorder(stream);

        ticketMediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0) ticketAudioChunks.push(e.data);
        };

        ticketMediaRecorder.onstart = () => {
          isTicketRecording = true;
          ticketChatMikeBtn.style.color = '#ef4444';
          showToast('🎤 Microphone listening for ticket follow-up...');
        };

        ticketMediaRecorder.onstop = async () => {
          isTicketRecording = false;
          ticketChatMikeBtn.style.color = '';
          stream.getTracks().forEach(t => t.stop());

          const audioBlob = new Blob(ticketAudioChunks, { type: 'audio/wav' });
          const formData = new FormData();
          formData.append('audio', audioBlob, 'ticket_audio.wav');

          try {
            const res = await fetch(`${API_BASE}/api/transcribe`, {
              method: 'POST',
              body: formData
            });
            const data = await res.json();
            if (data.text && data.text.trim()) {
              ticketChatInput.value = data.text.trim();
              showToast(`Transcribed: "${data.text.trim()}"`);
              handleSendTicketChat(data.text.trim());
            }
          } catch (e) {
            console.warn('Transcription error:', e);
          }
        };

        ticketMediaRecorder.start();
        return;
      } catch (err) {
        console.warn('MediaRecorder error:', err);
      }
    }

    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const rec = new SpeechRecognition();
      rec.continuous = false;
      rec.lang = 'en-US';
      rec.onstart = () => {
        ticketChatMikeBtn.style.color = '#ef4444';
        showToast('Listening... Speak your ticket follow-up.');
      };
      rec.onresult = (e) => {
        const transcript = e.results[0][0].transcript;
        ticketChatInput.value = transcript;
        showToast(`Heard: "${transcript}"`);
        handleSendTicketChat(transcript);
      };
      rec.onerror = () => { ticketChatMikeBtn.style.color = ''; };
      rec.onend = () => { ticketChatMikeBtn.style.color = ''; };
      rec.start();
    } else {
      showToast('Microphone access is not supported in this browser.');
    }
  }

  // =========================================================================
  // Render "RMS History" View
  // =========================================================================
  function renderHistoryView() {
    let filteredTickets = [...(state.tickets || [])];
    const now = new Date();

    if (state.historyPeriod === 'today') {
      const todayStr = now.toISOString().split('T')[0];
      filteredTickets = filteredTickets.filter(t => (t.created_at || '').startsWith(todayStr));
    } else if (state.historyPeriod === 'week') {
      const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      filteredTickets = filteredTickets.filter(t => new Date(t.created_at || 0) >= weekAgo);
    } else if (state.historyPeriod === 'month') {
      const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
      filteredTickets = filteredTickets.filter(t => new Date(t.created_at || 0) >= monthAgo);
    }

    metricTotal.textContent = state.stats.total_requests || state.tickets.length;
    metricResolved.textContent = state.stats.resolved || 0;
    metricInProgress.textContent = state.stats.in_progress || 0;
    metricAvgTime.textContent = `${state.stats.avg_resolution_days || 2.3} Days`;

    if (filteredTickets.length === 0) {
      historyTableBody.innerHTML = `
        <tr>
          <td colspan="5" style="text-align: center; padding: 36px 12px; color: rgba(255,255,255,0.5);">
            No RMS requests found for this filter period. Ask a question to submit a new inquiry.
          </td>
        </tr>
      `;
      return;
    }

    historyTableBody.innerHTML = filteredTickets.map(t => {
      const isResolved = (t.status || '').toLowerCase() === 'resolved';
      const statusClass = isResolved ? 'status-resolved' : 'status-in-progress';
      const resolvedDate = t.resolved_at || '-';

      return `
        <tr data-id="${t.ticket_id}" title="Click to track RMS #${t.ticket_id}">
          <td class="history-row-id">${escapeHtml(t.ticket_id)}</td>
          <td>${escapeHtml(t.category || 'General Issue')}</td>
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

    // Optimistically add to Today's query history in sidebar
    const optimisticItem = {
      raw_query: query,
      created_at: new Date().toISOString()
    };
    state.queryHistory = [optimisticItem, ...(state.queryHistory || [])];
    renderSidebarHistory();

    try {
      const response = await fetch(`${API_BASE}/api/query`, {
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
          ticketId: data.ticket_id,
          tokens: data.telemetry?.total_tokens,
          promptTokens: data.telemetry?.prompt_tokens,
          completionTokens: data.telemetry?.completion_tokens,
          latencyMs: data.telemetry?.latency_ms,
          arizeActive: data.telemetry?.arize_active
        });
        await Promise.all([loadTickets(), loadQueryHistory()]);
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

    let telemetryHtml = '';
    if (meta.latencyMs || meta.tokens) {
      telemetryHtml = `
        <div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.06); display: flex; align-items: center; gap: 8px; font-size: 11px; color: rgba(255,255,255,0.45); flex-wrap: wrap;">
          <span>⏱️ ${meta.latencyMs ? meta.latencyMs + 'ms' : 'Fast'}</span>
          <span>•</span>
          <span>⚡ ${meta.tokens || 0} tokens</span>
          <span>•</span>
          <span style="color: #34d399;">🔭 Arize Tracked</span>
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
          ${telemetryHtml}
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
            const res = await fetch(`${API_BASE}/api/transcribe`, {
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
      renderHistoryView();
      showToast(`Showing requests for: ${e.target.options[e.target.selectedIndex].text}`);
    });
  }

  if (historyViewAllBtn) {
    historyViewAllBtn.addEventListener('click', () => {
      state.historyPeriod = 'all';
      if (historyPeriodFilter) historyPeriodFilter.value = 'all';
      renderHistoryView();
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
        const resp = await fetch(`${API_BASE}/api/feedback`, {
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

  // Ticket Follow-Up Chat Form & Quick Chips Event Handlers
  if (ticketChatForm) {
    ticketChatForm.addEventListener('submit', (e) => {
      e.preventDefault();
      handleSendTicketChat();
    });
  }

  if (ticketChatMikeBtn) {
    ticketChatMikeBtn.addEventListener('click', (e) => {
      e.preventDefault();
      toggleTicketSpeech();
    });
  }

  if (ticketChatChips && ticketChatChips.length > 0) {
    ticketChatChips.forEach(chip => {
      chip.addEventListener('click', (e) => {
        e.preventDefault();
        const msg = chip.getAttribute('data-msg');
        if (msg) handleSendTicketChat(msg);
      });
    });
  }

  // =========================================================================
  // 3D Rotating Cycle Carousel for Suggestion Cards (Pure Mouse/Touch Drag)
  // =========================================================================
  function initSuggestionSlider() {
    const slider = document.getElementById('suggestionCardsSlider');
    const dotsContainer = document.getElementById('sliderDots');

    if (!slider) return;

    const cards = Array.from(slider.querySelectorAll('.suggestion-card'));
    const N = cards.length;
    if (N === 0) return;

    const stepAngle = 360 / N; // 60 degrees per card for 6 cards

    function getRadius() {
      const w = window.innerWidth;
      if (w > 900) return 370;
      if (w > 640) return 290;
      return 210;
    }

    let R = getRadius();
    let rotation = 0;          // Current rotation in degrees
    let velocity = 0;          // Rotational velocity in deg/frame
    let isDragging = false;
    let startX = 0;
    let lastX = 0;
    let lastTime = 0;
    let hasDragged = false;
    let suppressClick = false;
    let targetRotation = null;
    let animFrameId = null;

    // Build Pagination Dots
    if (dotsContainer) {
      dotsContainer.innerHTML = '';
      cards.forEach((card, index) => {
        const dot = document.createElement('button');
        dot.type = 'button';
        dot.className = `slider-dot ${index === 0 ? 'active' : ''}`;
        const title = card.querySelector('.card-title')?.textContent || `Card ${index + 1}`;
        dot.setAttribute('aria-label', `Rotate to ${title}`);
        dot.setAttribute('title', title);
        dot.addEventListener('click', (e) => {
          e.preventDefault();
          rotateToIndex(index);
        });
        dotsContainer.appendChild(dot);
      });
    }

    const dots = dotsContainer ? Array.from(dotsContainer.querySelectorAll('.slider-dot')) : [];

    function rotateToIndex(index) {
      const baseAngle = index * stepAngle;
      let angle = (baseAngle + rotation) % 360;
      if (angle < 0) angle += 360;
      let relAngle = angle > 180 ? angle - 360 : angle;
      targetRotation = rotation - relAngle;
      velocity = 0;
      startAnimation();
    }

    // Render 3D Cylindrical Rotate Cycle
    function renderCycle() {
      let activeIndex = 0;
      let minAbsAngle = Infinity;

      cards.forEach((card, i) => {
        const baseAngle = i * stepAngle;
        let angle = (baseAngle + rotation) % 360;
        if (angle < 0) angle += 360;
        let relAngle = angle > 180 ? angle - 360 : angle; // range -180 to +180

        const absAngle = Math.abs(relAngle);
        if (absAngle < minAbsAngle) {
          minAbsAngle = absAngle;
          activeIndex = i;
        }

        // 3D cylindrical coordinates
        const rad = (relAngle * Math.PI) / 180;
        const x = R * Math.sin(rad);
        const z = R * Math.cos(rad) - R; // z=0 at front center, negative towards sides
        const rotateY = relAngle * 0.72; // subtle inward tilt
        const scale = 0.82 + 0.18 * Math.cos(rad);

        // Visibility & Opacity falloff
        let opacity = 1;
        let isVisible = true;
        let pointerEvents = 'auto';

        if (absAngle > 95) {
          opacity = 0;
          isVisible = false;
          pointerEvents = 'none';
        } else if (absAngle > 58) {
          opacity = Math.max(0, 1 - (absAngle - 58) / 37);
          isVisible = opacity > 0.04;
          pointerEvents = absAngle < 78 ? 'auto' : 'none';
        }

        const zIndex = Math.round(1000 + z);
        const isCenter = absAngle < 28;

        card.style.transform = `translate3d(${x.toFixed(1)}px, 0, ${z.toFixed(1)}px) rotateY(${rotateY.toFixed(1)}deg) scale(${scale.toFixed(3)})`;
        card.style.opacity = opacity.toFixed(2);
        card.style.zIndex = zIndex;
        card.style.visibility = isVisible ? 'visible' : 'hidden';
        card.style.pointerEvents = pointerEvents;
        card.classList.toggle('is-active-center', isCenter);
        card.setAttribute('data-rel-angle', relAngle.toFixed(1));
      });

      // Update Pagination Dots
      dots.forEach((dot, idx) => {
        dot.classList.toggle('active', idx === activeIndex);
      });
    }

    // Animation & Physics Loop (Momentum + Magnetic Snap)
    function animate() {
      let needsNextFrame = false;

      if (!isDragging) {
        if (Math.abs(velocity) > 0.08) {
          rotation += velocity;
          velocity *= 0.92; // smooth friction deceleration
          needsNextFrame = true;
        } else if (targetRotation !== null) {
          const diff = targetRotation - rotation;
          rotation += diff * 0.16; // critically damped spring
          if (Math.abs(diff) < 0.05) {
            rotation = targetRotation;
            targetRotation = null;
          } else {
            needsNextFrame = true;
          }
        } else {
          // Once velocity drops below threshold, magnetically snap to nearest card
          const nearestStep = Math.round(rotation / stepAngle);
          targetRotation = nearestStep * stepAngle;
          needsNextFrame = true;
        }
      }

      renderCycle();

      if (needsNextFrame || isDragging) {
        animFrameId = requestAnimationFrame(animate);
      } else {
        animFrameId = null;
      }
    }

    function startAnimation() {
      if (!animFrameId) {
        animFrameId = requestAnimationFrame(animate);
      }
    }

    // Direct Mouse Dragging
    slider.addEventListener('mousedown', (e) => {
      if (e.button !== 0) return;
      isDragging = true;
      hasDragged = false;
      targetRotation = null;
      velocity = 0;
      startX = e.clientX;
      lastX = e.clientX;
      lastTime = performance.now();
      slider.classList.add('is-dragging');
      startAnimation();
    });

    window.addEventListener('mousemove', (e) => {
      if (!isDragging) return;
      const currentX = e.clientX;
      const deltaX = currentX - lastX;
      const now = performance.now();
      const dt = Math.max(1, now - lastTime);

      if (Math.abs(currentX - startX) > 5) {
        hasDragged = true;
      }

      // Sensitivity: ~240px drag rotates one full card step
      const sensitivity = 0.25;
      rotation += deltaX * sensitivity;

      const instantV = (deltaX / dt) * 16.6 * sensitivity;
      velocity = velocity * 0.5 + instantV * 0.5;
      velocity = Math.max(-14, Math.min(14, velocity));

      lastX = currentX;
      lastTime = now;
    });

    const stopDrag = () => {
      if (!isDragging) return;
      isDragging = false;
      slider.classList.remove('is-dragging');
      if (hasDragged) {
        suppressClick = true;
        setTimeout(() => {
          suppressClick = false;
          hasDragged = false;
        }, 90);
      }
      startAnimation();
    };

    window.addEventListener('mouseup', stopDrag);

    // Touch Dragging (Mobile / Tablet)
    slider.addEventListener('touchstart', (e) => {
      if (e.touches && e.touches[0]) {
        isDragging = true;
        hasDragged = false;
        targetRotation = null;
        velocity = 0;
        startX = e.touches[0].clientX;
        lastX = e.touches[0].clientX;
        lastTime = performance.now();
        slider.classList.add('is-dragging');
        startAnimation();
      }
    }, { passive: true });

    window.addEventListener('touchmove', (e) => {
      if (!isDragging || !e.touches || !e.touches[0]) return;
      const currentX = e.touches[0].clientX;
      const deltaX = currentX - lastX;
      const now = performance.now();
      const dt = Math.max(1, now - lastTime);

      if (Math.abs(currentX - startX) > 6) {
        hasDragged = true;
      }

      const sensitivity = 0.28;
      rotation += deltaX * sensitivity;

      const instantV = (deltaX / dt) * 16.6 * sensitivity;
      velocity = velocity * 0.5 + instantV * 0.5;
      velocity = Math.max(-14, Math.min(14, velocity));

      lastX = currentX;
      lastTime = now;
    }, { passive: true });

    window.addEventListener('touchend', stopDrag);

    // Trackpad / Horizontal Wheel Gesture Support
    slider.addEventListener('wheel', (e) => {
      if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
        e.preventDefault();
        targetRotation = null;
        velocity = -e.deltaX * 0.05;
        rotation += velocity;
        startAnimation();
      }
    }, { passive: false });

    // Keyboard Arrow Keys
    window.addEventListener('keydown', (e) => {
      if (document.activeElement && (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA')) {
        return;
      }
      if (e.key === 'ArrowRight') {
        targetRotation = (Math.round(rotation / stepAngle) - 1) * stepAngle;
        velocity = 0;
        startAnimation();
      } else if (e.key === 'ArrowLeft') {
        targetRotation = (Math.round(rotation / stepAngle) + 1) * stepAngle;
        velocity = 0;
        startAnimation();
      }
    });

    // Window Resize Handler to Adapt 3D Radius
    window.addEventListener('resize', () => {
      R = getRadius();
      renderCycle();
    }, { passive: true });

    // Intercept Card Clicks
    slider.addEventListener('click', (e) => {
      if (suppressClick || hasDragged) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        return;
      }

      const card = e.target.closest('.suggestion-card');
      if (!card) return;

      const relAngle = parseFloat(card.getAttribute('data-rel-angle') || '0');
      // If user clicked a side card, smoothly rotate it to the center
      if (Math.abs(relAngle) >= 25) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        targetRotation = rotation - relAngle;
        velocity = 0;
        startAnimation();
      }
      // If card is already in the front center (abs < 25), the click will proceed to trigger its action!
    }, true);

    // Initial render
    renderCycle();
  }

  // Initialize Suggestion Slider
  initSuggestionSlider();

  // Bootstrap Authentication
  checkAuthOnBoot();
});
