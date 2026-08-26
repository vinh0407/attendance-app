(() => {
  const pageNames = {home:'Trang chủ',schedule:'Lịch học',grades:'Điểm số',attendance:'Điểm danh',subjects:'Môn học',forum:'Diễn đàn',messages:'Tin nhắn',notifications:'Thông báo',profile:'Hồ sơ cá nhân'};
  const sidebar = document.querySelector('#sidebar');
  const menuToggle = document.querySelector('#menuToggle');
  const drawerScrim = document.querySelector('#drawerScrim');
  const pageLabel = document.querySelector('#pageLabel');
  const home = document.querySelector('#page-home');
  const attendancePage = document.querySelector('#page-attendance');
  const gradesPage = document.querySelector('#page-grades');
  const subjectsPage = document.querySelector('#page-subjects');
  const other = document.querySelector('#page-other');
  const placeholderTitle = document.querySelector('#placeholderTitle');
  const placeholderCopy = document.querySelector('#placeholderCopy');
  const toast = document.querySelector('#toast');
  let toastTimer;
  const API_BASE = window.PORTAL_API_BASE || '';
  const portalData = { profile: null, schedule: [], attendance: [], summary: null, grades: [], subjects: [] };

  async function apiGet(path) {
    const response = await fetch(`${API_BASE}${path}`, { credentials: 'include', headers: { Accept: 'application/json' } });
    let payload = {};
    try { payload = await response.json(); } catch (error) { /* handled below */ }
    if (!response.ok || payload.success === false) {
      const error = new Error(payload.error || `Request failed: ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return payload;
  }

  const escapeHtml = (value) => String(value ?? '—').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));

  function renderSchedule() {
    const target = document.querySelector('#todaySchedule');
    const empty = document.querySelector('#scheduleEmpty');
    if (!portalData.schedule.length) { target.hidden = true; empty.hidden = false; return; }
    empty.hidden = true;
    target.hidden = false;
    target.innerHTML = portalData.schedule.map((item) => `<article class="today-item"><div><strong>${escapeHtml(item.subject_name)}</strong><span>${escapeHtml(item.subject_id)} · ${escapeHtml(item.teacher || 'Chưa có giảng viên')}</span></div><div><strong>${escapeHtml(item.time_range)}</strong><span>${escapeHtml(item.room || item.classroom)}</span></div></article>`).join('');
  }

  function renderAttendance() {
    const target = document.querySelector('#attendanceRows');
    if (!portalData.attendance.length) { target.innerHTML = '<tr><td colspan="6">Chưa có bản ghi điểm danh.</td></tr>'; return; }
    target.innerHTML = portalData.attendance.map((item) => `<tr><td>${escapeHtml(item.date)}</td><td><strong>${escapeHtml(item.subject_name)}</strong><small>${escapeHtml(item.subject_id)}</small></td><td>${escapeHtml(item.scheduled_time)}</td><td>${escapeHtml(item.check_in_time)}</td><td><span class="attendance-status status-${escapeHtml(item.status)}">${escapeHtml(item.attendance_label || item.status)}</span></td><td>${item.late_minutes ? `${escapeHtml(item.late_minutes)} phút` : '—'}</td></tr>`).join('');
  }

  function renderGrades() {
    const target = document.querySelector('#gradesRows');
    if (!portalData.grades.length) { target.innerHTML = '<tr><td colspan="4">Chưa có dữ liệu điểm.</td></tr>'; return; }
    target.innerHTML = portalData.grades.map((item) => `<tr><td><strong>${escapeHtml(item.subject_name)}</strong><small>${escapeHtml(item.subject_id)}</small></td><td>${escapeHtml(item.semester || '—')}</td><td>${escapeHtml(item.assessment_type)}</td><td><strong>${escapeHtml(item.score)}</strong></td></tr>`).join('');
  }

  function renderSubjects() {
    const target = document.querySelector('#subjectRows');
    if (!portalData.subjects.length) { target.innerHTML = '<tr><td colspan="4">Chưa có dữ liệu môn học.</td></tr>'; return; }
    target.innerHTML = portalData.subjects.map((item) => `<tr><td><strong>${escapeHtml(item.subject_name)}</strong><small>${escapeHtml(item.subject_id)}</small></td><td>${escapeHtml(item.late_periods)} tiết <small>${escapeHtml(item.late_events)} lần</small></td><td>${escapeHtml(item.absent_periods)} tiết</td><td><span class="attendance-status ${item.exam_prohibited ? 'status-absent' : 'status-present'}">${escapeHtml(item.exam_status)}</span></td></tr>`).join('');
  }

  function renderPortal() {
    const profile = portalData.profile;
    if (profile) {
      document.querySelector('#profileName').textContent = profile.full_name;
      document.querySelector('#profileMeta').textContent = `${profile.student_id} · ${profile.class_name || 'Chưa có lớp'}`;
      document.querySelector('#profileInitial').textContent = (profile.full_name || 'U').trim().charAt(0).toUpperCase();
    }
    const summary = portalData.summary || {};
    document.querySelector('#summaryOnTime').textContent = summary.on_time ?? '—';
    document.querySelector('#summaryLate').textContent = (summary.late_level_1 ?? 0) + (summary.late_one_period ?? 0);
    document.querySelector('#summaryAbsent').textContent = (summary.absent_two_periods ?? 0) + (summary.absent ?? 0);
    renderSchedule(); renderAttendance(); renderGrades(); renderSubjects();
  }

  async function loadPortal() {
    try {
      const [profile, schedule, attendance, summary, grades, subjects] = await Promise.all([
        apiGet('/api/student/me/profile/'), apiGet('/api/student/me/schedule/today/'),
        apiGet('/api/student/me/attendance/'), apiGet('/api/student/me/attendance/summary/'),
        apiGet('/api/student/me/grades/'), apiGet('/api/student/me/subjects/summary/')
      ]);
      portalData.profile = profile.data; portalData.schedule = schedule.data || [];
      portalData.attendance = attendance.data || []; portalData.summary = summary.data || {};
      portalData.grades = grades.data || []; portalData.subjects = subjects.data || [];
      document.querySelector('#portalStatusTitle').textContent = 'Dữ liệu đã đồng bộ';
      document.querySelector('#portalStatusCopy').textContent = 'Lịch học và lịch sử điểm danh đang lấy từ tài khoản của bạn.';
      document.querySelector('#portalStatusTag').textContent = 'CONNECTED';
      renderPortal();
    } catch (error) {
      document.querySelector('#portalStatusTitle').textContent = error.status === 401 ? 'Cần đăng nhập để xem dữ liệu' : 'Không thể đồng bộ dữ liệu';
      document.querySelector('#portalStatusCopy').textContent = error.status === 401 ? 'Hãy đăng nhập bằng tài khoản sinh viên UTH.' : 'Kiểm tra kết nối backend rồi thử đồng bộ lại.';
      document.querySelector('#portalStatusTag').textContent = error.status === 401 ? 'UNAUTHORIZED' : 'ERROR';
    }
  }

  function showToast(message) {
    toast.textContent = message;
    toast.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('is-visible'), 2800);
  }

  function setRoute(route) {
    const activeRoute = pageNames[route] ? route : 'home';
    pageLabel.textContent = pageNames[activeRoute];
    document.querySelectorAll('[data-route]').forEach((link) => {
      const active = link.dataset.route === activeRoute;
      link.classList.toggle('is-active', active);
      if (active && link.closest('.side-nav')) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
    const isHome = activeRoute === 'home';
    home.hidden = !isHome;
    const isAttendance = activeRoute === 'attendance';
    const isGrades = activeRoute === 'grades';
    const isSubjects = activeRoute === 'subjects';
    attendancePage.hidden = !isAttendance;
    gradesPage.hidden = !isGrades;
    subjectsPage.hidden = !isSubjects;
    other.hidden = isHome || isAttendance || isGrades || isSubjects;
    if (!isHome && !isAttendance && !isGrades && !isSubjects) {
      placeholderTitle.textContent = pageNames[activeRoute];
      placeholderCopy.textContent = `${pageNames[activeRoute]} sẽ dùng cùng hệ thống dữ liệu và quyền truy cập của portal.`;
    }
    sidebar.classList.remove('is-open');
    menuToggle.setAttribute('aria-expanded', 'false');
    drawerScrim.hidden = true;
    window.scrollTo({top: 0, behavior: 'smooth'});
  }

  window.addEventListener('hashchange', () => setRoute(window.location.hash.slice(1)));
  document.querySelectorAll('[data-route]').forEach((link) => link.addEventListener('click', () => setRoute(link.dataset.route)));
  menuToggle.addEventListener('click', () => {
    const open = sidebar.classList.toggle('is-open');
    menuToggle.setAttribute('aria-expanded', String(open));
    drawerScrim.hidden = !open;
    if (open) sidebar.querySelector('.nav-item')?.focus();
  });
  drawerScrim.addEventListener('click', () => { sidebar.classList.remove('is-open'); menuToggle.setAttribute('aria-expanded', 'false'); drawerScrim.hidden = true; menuToggle.focus(); });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && sidebar.classList.contains('is-open')) {
      sidebar.classList.remove('is-open'); menuToggle.setAttribute('aria-expanded', 'false'); drawerScrim.hidden = true; menuToggle.focus();
    }
  });
  document.querySelector('#refreshButton').addEventListener('click', () => loadPortal().then(() => showToast('Đã đồng bộ dữ liệu.')).catch(() => showToast('Không thể đồng bộ dữ liệu.')));
  document.querySelector('#searchButton').addEventListener('click', () => showToast('Tìm kiếm sẽ khả dụng khi portal kết nối dữ liệu.'));
  document.querySelector('#themeToggle').addEventListener('click', (event) => {
    const button = event.currentTarget;
    const dark = document.body.classList.toggle('dark-preview');
    button.setAttribute('aria-pressed', String(dark));
    button.querySelector('b').textContent = dark ? 'Dark' : 'Light';
    showToast(dark ? 'Dark mode đang ở bản preview.' : 'Đã chuyển về Light mode.');
  });
  setRoute(window.location.hash.slice(1) || 'home');
  loadPortal();
})();
