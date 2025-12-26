import { createProgressFeed } from './progress-feed.js';

const API_BASE = '/api';
const STATUS_TEXT = {
  pending: '等待调度',
  running: '执行中',
  done: '已完成',
  failed: '执行失败',
  aborted: '已中止',
};

const DEFAULT_ABORT_REASON = '用户主动中止';
const GLOBAL_PROGRESS_LIMIT = 300;

const stageGridEl = document.getElementById('stage-grid');
const deployBtn = document.getElementById('deploy-btn');
const hintEl = document.getElementById('form-hint');
const taskListEl = document.getElementById('task-list');
const globalProgressEl = document.getElementById('global-progress');
const taskFilterEl = document.getElementById('task-filter');
const toastContainer = document.getElementById('toast-container');
const stageCountEl = document.getElementById('stage-count');
const dryRunEl = document.getElementById('opt-dry-run');
const strictEl = document.getElementById('opt-strict');
const debugEl = document.getElementById('opt-debug');
const flowStepperEl = document.querySelector('.flow-stepper');
const optionInputs = [dryRunEl, strictEl, debugEl];

const viewElements = new Map();
document.querySelectorAll('[data-view]').forEach((el) => {
  const name = el.dataset.view;
  if (name) {
    viewElements.set(name, el);
  }
});

const viewLinks = Array.from(document.querySelectorAll('[data-view-link]'));

let activeView = null;

let pollTimer = null;
let stageCatalog = [];
let taskStore = [];
let stageLookup = new Map();
let currentFilter = 'all';
let currentStep = 1;

let defaultStageSelection = new Set();
const defaultRunOptions = {
  dry_run: null,
  strict_validation: null,
  debug: null,
};

const abortRequestCache = new Map();

const taskProgressFeed = createProgressFeed({
  title: '最近进展',
  includeLevels: ['info', 'warning', 'error'],
  limit: 6,
  timeFormatter: (value) => formatTime(value),
  stageResolver: (stage) => getStageMeta(stage),
});

const globalProgressFeed = createProgressFeed({
  includeLevels: ['info', 'warning'],
  limit: GLOBAL_PROGRESS_LIMIT,
  showHeader: false,
  emptyText: '暂无实时进展。',
  timeFormatter: (value) => formatTime(value),
  stageResolver: (stage) => getStageMeta(stage),
  taskResolver: (taskId) => (taskId ? `任务 ${taskId.slice(0, 8)}` : null),
});

function formatStageOrder(order) {
  if (!order || Number.isNaN(order)) return '--';
  return order.toString().padStart(2, '0');
}

const STAGE_STATUS_TEXT = {
  pending: '待执行',
  running: '执行中',
  done: '已完成',
  failed: '执行失败',
  aborted: '已中止',
};

function countSummaryItems(value) {
  if (!value) return 0;
  if (Array.isArray(value)) return value.length;
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'object') return Object.keys(value).length;
  return 0;
}

function collectIssueCounts(task) {
  if (!task || typeof task !== 'object') {
    return { warnings: 0, errors: 0 };
  }
  const summary = task.summary || {};
  const report = summary.report || {};
  const totals = summary.totals || {};
  const warningBuckets = [report.warnings, summary.warnings, totals.warnings];
  const errorBuckets = [report.errors, summary.errors, totals.errors];
  const warnings = warningBuckets.reduce((acc, bucket) => acc + countSummaryItems(bucket), 0);
  const errors = errorBuckets.reduce((acc, bucket) => acc + countSummaryItems(bucket), 0);
  return { warnings, errors };
}

function getStageInfo(stageName) {
  return stageLookup.get(stageName);
}

function getStageMeta(stageName) {
  const info = getStageInfo(stageName);
  if (!info) {
    return stageName ? { label: stageName, order: null } : null;
  }
  return {
    label: info.label,
    order: typeof info.order === 'number' ? info.order : null,
  };
}

function setStep(step) {
  if (!flowStepperEl) return;
  const targetStep = Math.min(Math.max(step, 1), 3);
  currentStep = targetStep;
  const buttons = flowStepperEl.querySelectorAll('.flow-step');
  buttons.forEach((btn) => {
    const stepNumber = Number(btn.dataset.step);
    btn.classList.toggle('flow-step--active', stepNumber === currentStep);
    btn.classList.toggle('flow-step--done', stepNumber < currentStep);
  });
}

async function fetchJSON(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `${response.status} ${response.statusText}`);
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

function renderStages(catalog, selection = defaultStageSelection) {
  stageGridEl.innerHTML = '';
  const sorted = [...catalog].sort((a, b) => a.order - b.order);
  stageLookup = new Map(sorted.map((item) => [item.name, item]));

  for (const stage of sorted) {
    const label = document.createElement('label');
    label.className = 'stage-item';
    label.dataset.stage = stage.name;

    const input = document.createElement('input');
    input.type = 'checkbox';
    input.name = 'stage';
    input.value = stage.name;
  input.checked = selection.has(stage.name);

    const wrapper = document.createElement('div');
    wrapper.className = 'stage-item__label';

    const orderBadge = document.createElement('span');
    orderBadge.className = 'stage-item__order';
    orderBadge.textContent = `阶段 ${formatStageOrder(stage.order)}`;

    const strong = document.createElement('strong');
    strong.textContent = stage.label;

    const group = document.createElement('span');
    group.textContent = stage.group || '未分组';

    const desc = document.createElement('p');
    desc.textContent = stage.description || '暂未提供说明';

    wrapper.append(orderBadge, strong, group, desc);
    label.append(input, wrapper);
    stageGridEl.append(label);
  }
}

function applyRunOptionDefaults() {
  if (dryRunEl && typeof defaultRunOptions.dry_run === 'boolean') {
    dryRunEl.checked = defaultRunOptions.dry_run;
  }
  if (strictEl && typeof defaultRunOptions.strict_validation === 'boolean') {
    strictEl.checked = defaultRunOptions.strict_validation;
  }
  if (debugEl && typeof defaultRunOptions.debug === 'boolean') {
    debugEl.checked = defaultRunOptions.debug;
  }
}

function selectedStages() {
  return Array.from(stageGridEl.querySelectorAll("input[name='stage']"))
    .filter((input) => input.checked)
    .map((input) => input.value);
}

function updateNavActive(viewName) {
  viewLinks.forEach((link) => {
    const target = link.dataset.viewLink;
    const isActive = target === viewName;
    if (link.classList.contains('topbar__link')) {
      link.classList.toggle('topbar__link--active', isActive);
    }
    if (link.classList.contains('topbar__button')) {
      link.classList.toggle('topbar__button--active', isActive);
    }
    if (isActive) {
      link.setAttribute('aria-current', 'page');
    } else {
      link.removeAttribute('aria-current');
    }
  });
}

function showView(viewName, { updateHash = true, scroll = true } = {}) {
  if (!viewElements.has(viewName)) {
    return;
  }

  viewElements.forEach((el, name) => {
    const shouldShow = name === viewName;
    if (shouldShow) {
      el.removeAttribute('hidden');
      el.classList.add('view--active');
    } else {
      if (!el.hasAttribute('hidden')) {
        el.setAttribute('hidden', '');
      }
      el.classList.remove('view--active');
    }
  });

  updateNavActive(viewName);
  activeView = viewName;

  if (updateHash) {
    history.replaceState(null, '', `#${viewName}`);
  }

  if (scroll) {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
}

function resolveViewFromHash() {
  const raw = window.location.hash.replace('#', '').trim().toLowerCase();
  if (viewElements.has(raw)) {
    return raw;
  }
  return 'home';
}

function initViewRouting() {
  const initialView = resolveViewFromHash();
  showView(initialView, { updateHash: false, scroll: false });

  viewLinks.forEach((link) => {
    link.addEventListener('click', (event) => {
      const targetView = link.dataset.viewLink;
      if (!targetView || !viewElements.has(targetView)) {
        return;
      }
      event.preventDefault();
      showView(targetView);

      if (targetView === 'wizard') {
        const nextStep = taskStore.length ? 3 : selectedStages().length ? 2 : 1;
        setStep(nextStep);
        setFormHint('请选择要执行的阶段组合。');
      } else if (targetView === 'tasks') {
        fetchTasks();
      }
    });
  });

  window.addEventListener('hashchange', () => {
    const targetView = resolveViewFromHash();
    showView(targetView, { updateHash: false });
    if (targetView === 'wizard') {
      const nextStep = taskStore.length ? 3 : selectedStages().length ? 2 : 1;
      setStep(nextStep);
    } else if (targetView === 'tasks') {
      fetchTasks();
    }
  });
}

function getFilteredTasks() {
  if (currentFilter === 'all') {
    return [...taskStore];
  }
  return taskStore.filter((item) => item.status === currentFilter);
}

function computeNextStep() {
  if (taskStore.length) {
    return 3;
  }
  if (currentStep === 1) {
    return 1;
  }
  return selectedStages().length ? 2 : 1;
}

function setFormHint(message, tone = 'info') {
  hintEl.textContent = message || '';
  hintEl.dataset.tone = tone;
}

function toast(message, tone = 'info') {
  const toastEl = document.createElement('div');
  toastEl.className = 'toast';
  if (tone === 'error') {
    toastEl.classList.add('toast--error');
  }
  toastEl.textContent = message;
  toastContainer.append(toastEl);
  setTimeout(() => {
    toastEl.style.opacity = '0';
    setTimeout(() => toastEl.remove(), 400);
  }, 4000);
}

async function handleDeploy() {
  const stages = selectedStages();
  if (!stages.length) {
    setFormHint('请至少选择一个阶段。', 'error');
    return;
  }

  setFormHint('正在提交任务……');
  deployBtn.disabled = true;
  deployBtn.textContent = '提交中…';

  const payload = {
    stages,
    options: {
      dry_run: dryRunEl.checked,
      strict_validation: strictEl.checked,
      debug: debugEl.checked,
    },
  };

  try {
    const task = await fetchJSON(`${API_BASE}/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    setFormHint('任务已创建，稍后请关注下方进度。');
    toast('已创建部署任务，正在执行中…');
    setStep(3);
    updateTaskList(task);
    showView('tasks');
    await fetchTasks();
  } catch (err) {
    console.error(err);
    setFormHint('提交失败：' + err.message, 'error');
    toast('提交任务失败：' + err.message, 'error');
    setStep(computeNextStep());
  } finally {
    deployBtn.disabled = false;
    deployBtn.textContent = '启动自动化部署';
  }
}

function updateTaskList(task) {
  if (!task) return;
  taskStore = [task, ...taskStore.filter((item) => item.id !== task.id)].slice(0, 16);
  renderTasks(getFilteredTasks());
}

function renderTasks(tasks) {
  taskListEl.innerHTML = '';
  if (!tasks.length) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.textContent = '当前暂无任务，可在上方选择阶段后启动部署。';
    taskListEl.append(empty);
    return;
  }

  const sorted = [...tasks].sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));

  for (const task of sorted) {
    const article = document.createElement('article');
    article.className = 'task-item';

    const header = document.createElement('div');
    header.className = 'task-header';

    const headerInfo = document.createElement('div');
    headerInfo.className = 'task-header__info';

    const title = document.createElement('h3');
    title.className = 'task-title';
    title.textContent = `任务 ${task.id.slice(0, 8)}`;

    const statusLine = document.createElement('div');
    statusLine.className = 'task-status';
    statusLine.dataset.status = task.status;
    statusLine.textContent = STATUS_TEXT[task.status] || task.status;

    headerInfo.append(title, statusLine);

    const headerActions = document.createElement('div');
    headerActions.className = 'task-header__actions';

  const abortBtn = document.createElement('button');
  abortBtn.type = 'button';
  abortBtn.className = 'task-abort-btn';
  abortBtn.dataset.taskId = task.id;

    const deleteBtn = document.createElement('button');
    deleteBtn.type = 'button';
    deleteBtn.className = 'task-delete-btn';
    deleteBtn.dataset.taskId = task.id;
    deleteBtn.textContent = '删除记录';
  headerActions.append(abortBtn, deleteBtn);

  const isRunning = task.status === 'running';
  const abortRequested = Boolean(task.abort_requested);
  abortBtn.textContent = abortRequested ? '已中止' : '中止任务';
  abortBtn.disabled = !isRunning || abortRequested;
  deleteBtn.disabled = isRunning;

    header.append(headerInfo, headerActions);

    const meta = document.createElement('div');
    meta.className = 'task-meta';
    meta.innerHTML = `
      <span>开始时间：${formatDate(task.created_at)}</span>
      <span>最近更新：${formatDate(task.updated_at)}</span>
    `;

    const completedSet = new Set(task.completed_stages || []);
    const sortedStages = [...task.stages].sort((a, b) => {
      const orderA = getStageInfo(a)?.order ?? Number.MAX_SAFE_INTEGER;
      const orderB = getStageInfo(b)?.order ?? Number.MAX_SAFE_INTEGER;
      return orderA - orderB;
    });

    const stageCount = sortedStages.length;
    const declaredTotal = typeof task.total_stages === 'number' ? task.total_stages : 0;
    const safeTotal = declaredTotal > 0 ? declaredTotal : stageCount;
    const completedCount = safeTotal
      ? Math.min(completedSet.size, safeTotal)
      : completedSet.size;
    const progressPercent = safeTotal ? Math.round((completedCount / safeTotal) * 100) : 0;

    const progressBlock = document.createElement('div');
    progressBlock.className = 'task-progress';
    const progressMeta = document.createElement('div');
    progressMeta.className = 'task-progress__meta';
    const totalLabel = safeTotal || '—';
    progressMeta.innerHTML = `<strong>${progressPercent}%</strong> 完成度 · ${completedCount}/${totalLabel} 阶段`;
    progressBlock.append(progressMeta);

    if (task.status === 'running' && task.current_stage) {
      const label = document.createElement('div');
      label.className = 'task-progress__label';
      const currentInfo = getStageInfo(task.current_stage);
      label.textContent = `当前阶段：${currentInfo?.label ?? task.current_stage}`;
      progressBlock.append(label);
    } else if (task.status === 'done') {
      const label = document.createElement('div');
      label.className = 'task-progress__label';
      label.textContent = '所有阶段已完成';
      progressBlock.append(label);
    } else if (task.status === 'failed') {
      const label = document.createElement('div');
      label.className = 'task-progress__label';
      const failedInfo = task.current_stage ? getStageInfo(task.current_stage) : null;
      label.textContent = `执行失败：${failedInfo?.label ?? task.current_stage ?? '未知阶段'}`;
      progressBlock.append(label);
      if (task.error) {
        const err = document.createElement('div');
        err.className = 'task-progress__error';
        err.textContent = task.error;
        progressBlock.append(err);
      }
    } else if (task.status === 'aborted') {
      const label = document.createElement('div');
      label.className = 'task-progress__label';
      label.textContent = '任务已中止';
      progressBlock.append(label);
      if (task.abort_reason) {
        const hint = document.createElement('div');
        hint.className = 'task-progress__hint';
        hint.textContent = `中止原因：${task.abort_reason}`;
        progressBlock.append(hint);
      }
    }

    const progressTrack = document.createElement('div');
    progressTrack.className = 'task-progress__track';
    const progressFill = document.createElement('div');
    progressFill.className = 'task-progress__fill';
    progressFill.style.width = `${Math.min(100, Math.max(progressPercent, 0))}%`;
    progressTrack.append(progressFill);
    progressBlock.append(progressTrack);

    article.append(header, meta, progressBlock);

    const stageDetails = buildStageTimeline(task, sortedStages, completedSet);
    if (stageDetails) {
      article.append(stageDetails);
    }

    if (Array.isArray(task.progress_messages) && task.progress_messages.length) {
      const node = taskProgressFeed.render(
        task.progress_messages.map((entry) => ({
          ...entry,
          stage: entry.stage,
        })),
      );
      if (node) {
        article.append(node);
      }
    }

    const summaryBlock = document.createElement('div');
    summaryBlock.className = 'task-summary';
    const { warnings, errors } = collectIssueCounts(task);
    const network = task.summary?.network;

    summaryBlock.innerHTML = `
      <div>累计警告：<code>${warnings}</code> 条，累计错误：<code>${errors}</code> 条。</div>
    `;

    if (network && Object.keys(network).length) {
      const unavailable = Object.entries(network)
        .filter(([, report]) => report && report['-1'] === false)
        .map(([host]) => host);
      if (unavailable.length) {
        const warn = document.createElement('div');
        warn.innerHTML = `网络不可达主机：<code>${unavailable.join(', ')}</code>`;
        summaryBlock.append(warn);
      }
    }

    article.append(summaryBlock);
    taskListEl.append(article);
  }
}

function resolveStageStatus(stageName, task, events, completedSet) {
  if (events.some((event) => event.event === 'error')) {
    return 'failed';
  }
  if (events.some((event) => event.event === 'aborted')) {
    return 'aborted';
  }
  if (completedSet.has(stageName)) {
    return 'done';
  }
  if (task.status === 'failed' && task.current_stage === stageName) {
    return 'failed';
  }
  if (task.status === 'aborted' && task.current_stage === stageName) {
    return 'aborted';
  }
  if (task.status === 'running' && task.current_stage === stageName) {
    return 'running';
  }
  if (events.some((event) => event.event === 'start')) {
    return 'running';
  }
  return 'pending';
}

function buildStageTimeline(task, sortedStages, completedSet) {
  const historyEntries = Array.isArray(task.stage_history)
    ? task.stage_history.filter((entry) => entry && entry.stage)
    : [];
  const sortedHistory = [...historyEntries].sort((a, b) => {
    const timeA = a?.at ? new Date(a.at).getTime() : 0;
    const timeB = b?.at ? new Date(b.at).getTime() : 0;
    return timeA - timeB;
  });

  const grouped = new Map();
  for (const entry of sortedHistory) {
    const bucket = grouped.get(entry.stage) || [];
    bucket.push(entry);
    grouped.set(entry.stage, bucket);
  }

  const stageSet = new Set(sortedStages);
  const extras = [];
  for (const stageName of grouped.keys()) {
    if (!stageSet.has(stageName)) {
      extras.push(stageName);
    }
  }

  const stagesToRender = [...sortedStages, ...extras];
  if (!stagesToRender.length) {
    return null;
  }

  const container = document.createElement('div');
  container.className = 'task-stage';

  const table = document.createElement('table');
  table.className = 'task-stage-table';

  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');
  const headers = ['顺序', '阶段', '状态', '开始时间', '结束时间', '耗时'];
  headers.forEach((text) => {
    const th = document.createElement('th');
    th.textContent = text;
    headerRow.append(th);
  });
  thead.append(headerRow);
  table.append(thead);

  const tbody = document.createElement('tbody');

  for (const stageName of stagesToRender) {
    const info = getStageInfo(stageName);
    const stageIndex = sortedStages.indexOf(stageName);
    const derivedOrder = typeof info?.order === 'number'
      ? info.order
      : stageIndex >= 0
        ? stageIndex + 1
        : null;
    const label = info?.label ?? stageName;
    const events = grouped.get(stageName) || [];
    const statusKey = resolveStageStatus(stageName, task, events, completedSet);
    const startEvent = events.find((event) => event.event === 'start');
    const endEvent = [...events].reverse().find((event) => ['complete', 'error', 'aborted'].includes(event.event));

    const row = document.createElement('tr');
    row.dataset.status = statusKey;

    const orderCell = document.createElement('td');
    orderCell.dataset.label = '顺序';
    orderCell.textContent = formatStageOrder(derivedOrder);

    const labelCell = document.createElement('td');
    labelCell.dataset.label = '阶段';
    labelCell.textContent = label;

    const statusCell = document.createElement('td');
    statusCell.dataset.label = '状态';
    const statusBadge = document.createElement('span');
    statusBadge.className = `stage-status stage-status--${statusKey}`;
    statusBadge.textContent = STAGE_STATUS_TEXT[statusKey] || '未知状态';
    statusCell.append(statusBadge);

    const startCell = document.createElement('td');
    startCell.dataset.label = '开始时间';
    startCell.textContent = startEvent ? formatTime(startEvent.at) : '--:--:--';

    const endCell = document.createElement('td');
    endCell.dataset.label = '结束时间';
    endCell.textContent = endEvent ? formatTime(endEvent.at) : '--:--:--';

    const durationCell = document.createElement('td');
    durationCell.dataset.label = '耗时';
    const durationMs = computeStageDurationMs(startEvent?.at, endEvent?.at);
    if (typeof durationMs === 'number') {
      durationCell.textContent = formatDuration(durationMs);
    } else if (statusKey === 'running' && startEvent) {
      durationCell.textContent = '进行中…';
    } else {
      durationCell.textContent = '—';
    }

    row.append(orderCell, labelCell, statusCell, startCell, endCell, durationCell);
    tbody.append(row);
  }

  table.append(tbody);
  container.append(table);
  return container;
}

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString();
}

function formatTime(value) {
  if (!value) return '--:--:--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '--:--:--';
  return date.toLocaleTimeString();
}

function computeStageDurationMs(startValue, endValue) {
  if (!startValue || !endValue) return null;
  const start = new Date(startValue);
  const end = new Date(endValue);
  const startTs = start.getTime();
  const endTs = end.getTime();
  if (Number.isNaN(startTs) || Number.isNaN(endTs)) {
    return null;
  }
  if (endTs < startTs) {
    return null;
  }
  return endTs - startTs;
}

function formatDuration(durationMs) {
  if (!Number.isFinite(durationMs) || durationMs < 0) {
    return '—';
  }
  const totalSeconds = Math.floor(durationMs / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const parts = [hours, minutes, seconds].map((value) => String(value).padStart(2, '0'));
  return parts.join(':');
}

async function fetchTasks() {
  try {
    const data = await fetchJSON(`${API_BASE}/tasks`);
    if (data && Array.isArray(data.items)) {
      taskStore = data.items;
      renderTasks(getFilteredTasks());
      renderGlobalProgress(taskStore);
      if (flowStepperEl) {
        setStep(computeNextStep());
      }
    }
  } catch (err) {
    console.warn('Failed to fetch tasks', err);
  }
}

async function deleteTaskRecord(taskId) {
  await fetchJSON(`${API_BASE}/tasks/${taskId}`, {
    method: 'DELETE',
  });
}

async function abortTaskRecord(taskId, reason = DEFAULT_ABORT_REASON) {
  return fetchJSON(`${API_BASE}/tasks/${taskId}/abort`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  });
}

function requestAbortTask(taskId, triggerBtn) {
  if (!taskId || abortRequestCache.has(taskId)) {
    return;
  }
  abortRequestCache.set(taskId, true);
  const button = triggerBtn || null;
  const originalText = button?.textContent;
  if (button) {
    button.disabled = true;
    button.textContent = '已中止';
  }
  abortTaskRecord(taskId)
    .then(() => {
      toast(`已请求中止任务 ${taskId.slice(0, 8)}`);
      return fetchTasks();
    })
    .catch((err) => {
      console.error(err);
      toast('中止任务失败：' + err.message, 'error');
      if (button) {
        button.disabled = false;
        button.textContent = originalText || '中止任务';
      }
    })
    .finally(() => {
      abortRequestCache.delete(taskId);
    });
}

function startPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
  }
  pollTimer = setInterval(fetchTasks, 2000);
}

async function bootstrap() {
  setFormHint('请选择要执行的阶段组合。');
  try {
    const defaultsPromise = fetchJSON(`${API_BASE}/defaults`).catch((err) => {
      console.warn('Failed to load UI defaults', err);
      return null;
    });
    const stagesPromise = fetchJSON(`${API_BASE}/stages`);
    const [defaults, stages] = await Promise.all([defaultsPromise, stagesPromise]);

    if (defaults && typeof defaults === 'object') {
      if (Array.isArray(defaults.stages)) {
        defaultStageSelection = new Set(defaults.stages.filter((item) => typeof item === 'string'));
      }
      const opts = defaults.run_options;
      if (opts && typeof opts === 'object') {
        if (typeof opts.dry_run === 'boolean') {
          defaultRunOptions.dry_run = opts.dry_run;
        }
        if (typeof opts.strict_validation === 'boolean') {
          defaultRunOptions.strict_validation = opts.strict_validation;
        }
        if (typeof opts.debug === 'boolean') {
          defaultRunOptions.debug = opts.debug;
        }
      }
    }

    if (!defaultStageSelection.size) {
      defaultStageSelection = new Set(['prepare']);
    }

    stageCatalog = Array.isArray(stages) ? stages : [];
    if (stageCountEl) {
      stageCountEl.textContent = stageCatalog.length || '--';
    }
    renderStages(stageCatalog, defaultStageSelection);
    applyRunOptionDefaults();
    setStep(selectedStages().length ? 2 : 1);
    stageGridEl.addEventListener('change', () => {
      setFormHint('');
      const hasSelection = selectedStages().length > 0;
      if (currentStep < 3) {
        setStep(hasSelection ? 2 : 1);
      }
    });
    optionInputs.forEach((input) => {
      if (!input) return;
      input.addEventListener('change', () => {
        if (currentStep < 3 && selectedStages().length) {
          setStep(2);
        }
      });
    });
    await fetchTasks();
    startPolling();
  } catch (err) {
    console.error(err);
    setFormHint('加载阶段信息失败：' + err.message, 'error');
    toast('加载阶段列表失败，请刷新页面重试。', 'error');
  }

  deployBtn.addEventListener('click', handleDeploy);
  if (taskFilterEl) {
    taskFilterEl.value = currentFilter;
    taskFilterEl.addEventListener('change', () => {
      currentFilter = taskFilterEl.value;
      renderTasks(getFilteredTasks());
      renderGlobalProgress(taskStore);
      fetchTasks();
    });
  }
  if (flowStepperEl) {
    flowStepperEl.addEventListener('click', (event) => {
      const button = event.target.closest('.flow-step');
      if (!button) {
        return;
      }
      const requested = Number(button.dataset.step) || 1;
      if (requested > currentStep) {
        if (requested === 2 && !selectedStages().length) {
          toast('请先完成步骤 1：选择部署阶段。', 'error');
          setStep(1);
          return;
        }
        if (requested === 3 && !taskStore.length) {
          toast('请先启动部署任务。', 'error');
          return;
        }
      }
      const targetId = button.dataset.target;
      if (targetId) {
        const target = document.getElementById(targetId);
        if (target) {
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }
      setStep(requested);
    });
  }
  taskListEl.addEventListener('click', (event) => {
    const abortBtn = event.target.closest('.task-abort-btn');
    if (abortBtn) {
      const { taskId } = abortBtn.dataset;
      if (taskId) {
        requestAbortTask(taskId, abortBtn);
      }
      return;
    }
    const button = event.target.closest('.task-delete-btn');
    if (!button) {
      return;
    }
    const { taskId } = button.dataset;
    if (!taskId) {
      return;
    }
    button.disabled = true;
    deleteTaskRecord(taskId)
      .then(() => {
        toast(`已删除任务 ${taskId.slice(0, 8)}`);
        taskStore = taskStore.filter((item) => item.id !== taskId);
        renderTasks(getFilteredTasks());
        renderGlobalProgress(taskStore);
        setStep(computeNextStep());
        fetchTasks();
      })
      .catch((err) => {
        console.error(err);
        toast('删除任务失败：' + err.message, 'error');
        button.disabled = false;
      });
  });
}

initViewRouting();
bootstrap();

function renderGlobalProgress(tasks) {
  if (!globalProgressEl) {
    return;
  }
  const entries = [];
  for (const task of tasks) {
    if (!Array.isArray(task.progress_messages)) {
      continue;
    }
    for (const message of task.progress_messages) {
      entries.push({
        ...message,
        taskId: task.id,
      });
    }
  }
  globalProgressFeed.renderInto(globalProgressEl, entries);
}
