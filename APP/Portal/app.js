(() => {
  'use strict';

  const pageNames = {
    home: 'Home', schedule: 'Schedule', grades: 'Grades', attendance: 'Attendance',
    subjects: 'Subjects', forum: 'Forum', messages: 'Messages',
    notifications: 'Notifications', profile: 'Profile'
  };
  const API_BASE = window.PORTAL_API_BASE || '';
  const portalData = {
    profile: null, schedule: [], scheduleToday: [], attendance: [],
    summary: null, grades: [], subjects: [], synchronizedAt: null
  };

  const authGate = document.querySelector('#authGate');
  const portalShell = document.querySelector('#portalShell');
  const bottomNav = document.querySelector('#bottomNav');
  const loginForm = document.querySelector('#studentLoginForm');
  const loginSubmit = document.querySelector('#loginSubmit');
  const loginError = document.querySelector('#loginError');
  const sidebar = document.querySelector('#sidebar');
  const menuToggle = document.querySelector('#menuToggle');
  const drawerScrim = document.querySelector('#drawerScrim');
  const pageLabel = document.querySelector('#pageLabel');
  const toast = document.querySelector('#toast');
  let toastTimer;

  const escapeHtml = (value) => String(value ?? '—').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
  }[char]));

  function getCookie(name) {
    return document.cookie.split(';').map((part) => part.trim()).find((part) => part.startsWith(`${name}=`))?.slice(name.length + 1) || '';
  }

  async function apiRequest(path, options = {}) {
    const method = options.method || 'GET';
    const headers = { Accept: 'application/json', ...(options.headers || {}) };
    if (method !== 'GET') {
      headers['Content-Type'] = 'application/json';
      headers['X-CSRFToken'] = decodeURIComponent(getCookie('csrftoken'));
    }
    const response = await fetch(`${API_BASE}${path}`, {
      method,
      credentials: 'include',
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined
    });
    let payload = {};
    try { payload = await response.json(); } catch (error) { /* handled below */ }
    if (!response.ok || payload.success === false) {
      const requestError = new Error(payload.error || `Request failed: ${response.status}`);
      requestError.status = response.status;
      throw requestError;
    }
    return payload;
  }

  function formatDate(value, options = { day: '2-digit', month: 'short', year: 'numeric' }) {
    if (!value) return '—';
    const date = new Date(`${value}T00:00:00`);
    return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('en-GB', options).format(date);
  }

  function showToast(message) {
    toast.textContent = message;
    toast.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => toast.classList.remove('is-visible'), 2800);
  }

  function showLogin(message = '') {
    portalShell.hidden = true;
    bottomNav.hidden = true;
    authGate.hidden = false;
    authGate.removeAttribute('aria-hidden');
    loginError.textContent = message;
    loginError.hidden = !message;
    document.body.classList.add('is-auth-view');
  }

  function showPortal() {
    authGate.hidden = true;
    authGate.setAttribute('aria-hidden', 'true');
    portalShell.hidden = false;
    bottomNav.hidden = false;
    document.body.classList.remove('is-auth-view');
  }

  function setStatus(title, copy, tag, state = 'connected') {
    document.querySelector('#portalStatusTitle').textContent = title;
    document.querySelector('#portalStatusCopy').textContent = copy;
    document.querySelector('#portalStatusTag').textContent = tag;
    document.querySelector('#portalStatusDot').dataset.state = state;
    document.querySelector('#connectionLabel').textContent = state === 'connected' ? 'Connected' : 'Sync issue';
  }

  function renderProfile() {
    const profile = portalData.profile;
    if (!profile) return;
    const initial = (profile.full_name || 'U').trim().charAt(0).toUpperCase();
    const className = profile.class_name || 'Class not assigned';
    document.querySelector('#profileName').textContent = profile.full_name;
    document.querySelector('#profileMeta').textContent = `${profile.student_id} · ${className}`;
    document.querySelector('#profileInitial').textContent = initial;
    document.querySelector('#sidebarAvatar').textContent = initial;
    document.querySelector('#topbarAvatar').textContent = initial;
    document.querySelector('#sidebarName').textContent = profile.full_name;
    document.querySelector('#sidebarMeta').textContent = `${profile.student_id} · ${className}`;
    document.querySelector('#profilePageName').textContent = profile.full_name;
    document.querySelector('#profilePageId').textContent = profile.student_id;
    document.querySelector('#profilePageClass').textContent = className;
    document.querySelector('#profilePageEmail').textContent = profile.email || 'Not provided';
  }

  function renderTodaySchedule() {
    const target = document.querySelector('#todaySchedule');
    const empty = document.querySelector('#scheduleEmpty');
    if (!portalData.scheduleToday.length) {
      target.hidden = true;
      empty.hidden = false;
      return;
    }
    empty.hidden = true;
    target.hidden = false;
    target.innerHTML = portalData.scheduleToday.map((item) => `
      <article class="today-item">
        <div><strong>${escapeHtml(item.subject_name)}</strong><span>${escapeHtml(item.subject_id)} · ${escapeHtml(item.teacher || 'Teacher not assigned')}</span></div>
        <div><strong>${escapeHtml(item.time_range)}</strong><span>${escapeHtml(item.room || item.classroom)}</span></div>
      </article>`).join('');
  }

  function renderWeeklySchedule() {
    const target = document.querySelector('#weeklySchedule');
    if (!portalData.schedule.length) {
      target.innerHTML = '<div class="empty-panel"><div><h3>No active classes</h3><p>Your weekly timetable will appear after an administrator assigns your class.</p></div></div>';
      return;
    }
    const groups = new Map();
    portalData.schedule.forEach((item) => {
      if (!groups.has(item.day_name)) groups.set(item.day_name, []);
      groups.get(item.day_name).push(item);
    });
    target.innerHTML = [...groups.entries()].map(([day, items]) => `
      <section class="schedule-day"><h2>${escapeHtml(day)}</h2><div>${items.map((item) => `
        <article class="schedule-row"><time>${escapeHtml(item.time_range)}</time><div><strong>${escapeHtml(item.subject_name)}</strong><span>${escapeHtml(item.subject_id)} · ${escapeHtml(item.teacher || 'Teacher not assigned')}</span></div><span>${escapeHtml(item.room || item.classroom)}</span></article>`).join('')}</div></section>`).join('');
  }

  function renderNextClass() {
    const target = document.querySelector('#nextClass');
    if (!portalData.scheduleToday.length) {
      target.innerHTML = '<p>No classes are scheduled for today.</p><span class="inline-status">CLEAR DAY</span>';
      return;
    }
    const now = new Date();
    const minuteOfDay = now.getHours() * 60 + now.getMinutes();
    const upcoming = portalData.scheduleToday.find((item) => {
      const [hour, minute] = String(item.time_range || '').split(' - ')[0].split(':').map(Number);
      return Number.isFinite(hour) && hour * 60 + minute >= minuteOfDay;
    });
    if (!upcoming) {
      target.innerHTML = '<p>All scheduled classes for today have finished.</p><span class="inline-status">DAY COMPLETE</span>';
      return;
    }
    target.innerHTML = `<div class="next-class-detail"><strong>${escapeHtml(upcoming.subject_name)}</strong><span>${escapeHtml(upcoming.time_range)} · ${escapeHtml(upcoming.room || upcoming.classroom)}</span><small>${escapeHtml(upcoming.teacher || 'Teacher not assigned')}</small></div>`;
  }

  function renderAttendance() {
    const target = document.querySelector('#attendanceRows');
    if (!portalData.attendance.length) {
      target.innerHTML = '<tr><td colspan="6">No attendance records yet.</td></tr>';
      return;
    }
    const labels = {
      ON_TIME: 'On time', LATE_LEVEL_1: 'Late — Level 1', LATE_ONE_PERIOD: 'Late — 1 period',
      ABSENT_TWO_PERIODS: 'Absent — 2 periods', ABSENT: 'Absent'
    };
    target.innerHTML = portalData.attendance.map((item) => `<tr>
      <td>${escapeHtml(formatDate(item.date))}</td>
      <td><strong>${escapeHtml(item.subject_name || 'General attendance')}</strong><small>${escapeHtml(item.subject_id || '—')}</small></td>
      <td>${escapeHtml(item.scheduled_time || '—')}</td><td>${escapeHtml(item.check_in_time || '—')}</td>
      <td><span class="attendance-status status-${escapeHtml(item.status)}">${escapeHtml(labels[item.attendance_code] || item.status)}</span></td>
      <td>${item.late_minutes ? `${escapeHtml(item.late_minutes)} minutes` : '—'}</td></tr>`).join('');
  }

  function renderGrades() {
    const target = document.querySelector('#gradesRows');
    if (!portalData.grades.length) {
      target.innerHTML = '<tr><td colspan="4">No grades available yet.</td></tr>';
      return;
    }
    target.innerHTML = portalData.grades.map((item) => `<tr><td><strong>${escapeHtml(item.subject_name)}</strong><small>${escapeHtml(item.subject_id)}</small></td><td>${escapeHtml(item.semester || '—')}</td><td>${escapeHtml(item.assessment_type)}</td><td><strong>${escapeHtml(Number(item.score).toFixed(2))}</strong></td></tr>`).join('');
  }

  function renderSubjects() {
    const target = document.querySelector('#subjectRows');
    if (!portalData.subjects.length) {
      target.innerHTML = '<tr><td colspan="4">No subject data available yet.</td></tr>';
      return;
    }
    target.innerHTML = portalData.subjects.map((item) => `<tr><td><strong>${escapeHtml(item.subject_name)}</strong><small>${escapeHtml(item.subject_id)}</small></td><td>${escapeHtml(item.late_periods)} periods <small>${escapeHtml(item.late_events)} events</small></td><td>${escapeHtml(item.absent_periods)} periods</td><td><span class="attendance-status ${item.exam_prohibited ? 'status-absent' : 'status-present'}">${escapeHtml(item.exam_status)}</span></td></tr>`).join('');
  }

  function renderPortal() {
    renderProfile();
    const summary = portalData.summary || {};
    document.querySelector('#summaryOnTime').textContent = summary.on_time ?? 0;
    document.querySelector('#summaryLate').textContent = (summary.late_level_1 ?? 0) + (summary.late_one_period ?? 0);
    document.querySelector('#summaryAbsent').textContent = (summary.absent_two_periods ?? 0) + (summary.absent ?? 0);
    document.querySelector('#todayDate').textContent = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: '2-digit', month: 'long' }).format(new Date()).toUpperCase();
    renderTodaySchedule();
    renderWeeklySchedule();
    renderNextClass();
    renderAttendance();
    renderGrades();
    renderSubjects();
  }

  async function loadPortal({ announce = false } = {}) {
    document.body.setAttribute('aria-busy', 'true');
    try {
      const response = await apiRequest('/api/student/me/dashboard/');
      const data = response.data || {};
      portalData.profile = data.profile;
      portalData.schedule = data.schedule || [];
      portalData.scheduleToday = data.schedule_today || [];
      portalData.attendance = data.attendance || [];
      portalData.summary = data.attendance_summary || {};
      portalData.grades = data.grades || [];
      portalData.subjects = data.subjects || [];
      portalData.synchronizedAt = data.synchronized_at;
      renderPortal();
      showPortal();
      const time = portalData.synchronizedAt ? new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit' }).format(new Date(portalData.synchronizedAt)) : 'now';
      setStatus('Data synchronized', `Your academic data was updated at ${time}.`, 'CONNECTED');
      if (announce) showToast('Academic data synchronized.');
      return true;
    } catch (error) {
      if (error.status === 401 || error.status === 403) {
        showLogin(error.status === 403 ? error.message : '');
        return false;
      }
      setStatus('Unable to synchronize data', 'Check the server connection and try again.', 'ERROR', 'error');
      if (announce) showToast('Unable to synchronize data.');
      throw error;
    } finally {
      document.body.removeAttribute('aria-busy');
    }
  }

  function setRoute(route) {
    const activeRoute = pageNames[route] ? route : 'home';
    pageLabel.textContent = pageNames[activeRoute];
    document.querySelectorAll('[data-route]').forEach((link) => {
      const active = link.dataset.route === activeRoute;
      link.classList.toggle('is-active', active);
      if (active && (link.closest('.side-nav') || link.closest('.bottom-nav'))) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
    const dedicatedRoutes = new Set(['home', 'schedule', 'grades', 'attendance', 'subjects', 'profile']);
    document.querySelectorAll('[id^="page-"]').forEach((page) => { page.hidden = page.id !== `page-${activeRoute}`; });
    const other = document.querySelector('#page-other');
    other.hidden = dedicatedRoutes.has(activeRoute);
    if (!dedicatedRoutes.has(activeRoute)) {
      document.querySelector('#placeholderTitle').textContent = pageNames[activeRoute];
      document.querySelector('#placeholderCopy').textContent = `${pageNames[activeRoute]} will use the same student identity and access permissions when its backend is available.`;
    }
    sidebar.classList.remove('is-open');
    menuToggle.setAttribute('aria-expanded', 'false');
    drawerScrim.hidden = true;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const studentId = document.querySelector('#loginStudentId').value.trim();
    const className = document.querySelector('#loginClassName').value.trim();
    loginError.hidden = true;
    if (!studentId || !className) {
      loginError.textContent = 'Enter both your Student ID and class.';
      loginError.hidden = false;
      return;
    }
    loginSubmit.disabled = true;
    loginSubmit.querySelector('span').textContent = 'Signing in…';
    try {
      await apiRequest('/api/student/login/', { method: 'POST', body: { student_id: studentId, class_name: className } });
      await loadPortal();
      loginForm.reset();
      setRoute(window.location.hash.slice(1) || 'home');
    } catch (error) {
      loginError.textContent = error.message || 'Unable to sign in. Try again.';
      loginError.hidden = false;
      document.querySelector('#loginStudentId').focus();
    } finally {
      loginSubmit.disabled = false;
      loginSubmit.querySelector('span').textContent = 'Sign in';
    }
  });

  document.querySelector('#logoutButton').addEventListener('click', async () => {
    try { await apiRequest('/api/student/logout/', { method: 'POST' }); } catch (error) { /* local state still resets */ }
    Object.assign(portalData, { profile: null, schedule: [], scheduleToday: [], attendance: [], summary: null, grades: [], subjects: [], synchronizedAt: null });
    window.location.hash = 'home';
    showLogin();
    document.querySelector('#loginStudentId').focus();
  });

  window.addEventListener('hashchange', () => setRoute(window.location.hash.slice(1)));
  document.querySelectorAll('[data-route]').forEach((link) => link.addEventListener('click', () => setRoute(link.dataset.route)));
  menuToggle.addEventListener('click', () => {
    const open = sidebar.classList.toggle('is-open');
    menuToggle.setAttribute('aria-expanded', String(open));
    drawerScrim.hidden = !open;
    if (open) sidebar.querySelector('.nav-item')?.focus();
  });
  drawerScrim.addEventListener('click', () => {
    sidebar.classList.remove('is-open');
    menuToggle.setAttribute('aria-expanded', 'false');
    drawerScrim.hidden = true;
    menuToggle.focus();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && sidebar.classList.contains('is-open')) {
      sidebar.classList.remove('is-open');
      menuToggle.setAttribute('aria-expanded', 'false');
      drawerScrim.hidden = true;
      menuToggle.focus();
    }
  });
  document.querySelector('#refreshButton').addEventListener('click', async (event) => {
    event.currentTarget.disabled = true;
    try { await loadPortal({ announce: true }); } finally { event.currentTarget.disabled = false; }
  });
  document.querySelector('#themeToggle').addEventListener('click', (event) => {
    const button = event.currentTarget;
    const dark = document.body.classList.toggle('dark-preview');
    button.setAttribute('aria-pressed', String(dark));
    button.querySelector('b').textContent = dark ? 'Dark' : 'Light';
    showToast(dark ? 'Dark mode enabled.' : 'Light mode enabled.');
  });

  setRoute(window.location.hash.slice(1) || 'home');
  loadPortal().catch(() => {});
})();
