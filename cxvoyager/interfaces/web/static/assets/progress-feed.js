const DEFAULT_LEVELS = ['info', 'warning'];

function toDate(value) {
  if (!value) {
    return null;
  }
  const parsed = value instanceof Date ? value : new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function defaultTimeFormatter(value) {
  const date = toDate(value);
  if (!date) {
    return '--:--:--';
  }
  return date.toLocaleTimeString();
}

function defaultStageResolver(stage) {
  if (!stage) {
    return null;
  }
  return { label: stage, order: null };
}

function defaultTaskResolver(taskId) {
  if (!taskId) {
    return null;
  }
  return `任务 ${taskId.slice(0, 8)}`;
}

function createStageBadge(stageMeta) {
  if (!stageMeta?.label) {
    return null;
  }
  const wrapper = document.createElement('span');
  wrapper.className = 'task-log__stage';
  if (typeof stageMeta.order === 'number' && !Number.isNaN(stageMeta.order)) {
    const badge = document.createElement('span');
    badge.className = 'task-log__stage-order';
    badge.textContent = `阶段 ${stageMeta.order.toString().padStart(2, '0')}`;
    wrapper.append(badge);
  }
  const label = document.createElement('span');
  label.className = 'task-log__stage-label';
  label.textContent = stageMeta.label;
  wrapper.append(label);
  return wrapper;
}

function createTaskToken(text) {
  if (!text) {
    return null;
  }
  const chip = document.createElement('span');
  chip.className = 'task-log__task';
  chip.textContent = text;
  return chip;
}

export class ProgressFeed {
  constructor(options = {}) {
    this.limit = options.limit ?? 10;
    this.includeLevels = Array.isArray(options.includeLevels) && options.includeLevels.length
      ? options.includeLevels.map((level) => level.toLowerCase())
      : DEFAULT_LEVELS;
    this.stageResolver = options.stageResolver ?? defaultStageResolver;
    this.taskResolver = options.taskResolver ?? null;
    this.timeFormatter = options.timeFormatter ?? defaultTimeFormatter;
    this.title = options.title ?? null;
    this.wrapClass = options.wrapClass ?? 'task-log';
    this.listClass = options.listClass ?? 'task-log__list';
    this.itemBaseClass = options.itemClass ?? 'task-log__item';
    this.emptyText = options.emptyText ?? '暂无最新进展。';
    this.showHeader = options.showHeader ?? Boolean(this.title);
  }

  normalize(messages) {
    if (!Array.isArray(messages)) {
      return [];
    }
    const allowedLevels = new Set(
      this.includeLevels.map((level) => (level || 'info').toLowerCase()),
    );
    const normalized = [];
    for (const entry of messages) {
      if (!entry) {
        continue;
      }
      const level = (entry.level || 'info').toLowerCase();
      if (!allowedLevels.has(level)) {
        continue;
      }
      const at = toDate(entry.at) ?? new Date();
      normalized.push({
        at,
        message: entry.message || '',
        level,
        stage: entry.stage,
        taskId: entry.taskId,
      });
    }
    normalized.sort((a, b) => b.at.getTime() - a.at.getTime());
    return normalized.slice(0, this.limit);
  }

  render(messages) {
    const items = this.normalize(messages);
    const container = document.createElement('div');
    container.className = this.wrapClass;

    if (this.showHeader && this.title) {
      const header = document.createElement('div');
      header.className = 'task-log__header';
      header.textContent = this.title;
      container.append(header);
    }

    if (!items.length) {
      const empty = document.createElement('p');
      empty.className = 'task-log__empty';
      empty.textContent = this.emptyText;
      container.append(empty);
      return container;
    }

    const list = document.createElement('ul');
    list.className = this.listClass;

    for (const entry of items) {
      const item = document.createElement('li');
      item.className = `${this.itemBaseClass} ${this.itemBaseClass}--${entry.level}`;

      const timeEl = document.createElement('time');
      timeEl.dateTime = entry.at.toISOString();
      timeEl.textContent = this.timeFormatter(entry.at);
      item.append(timeEl);

      const stageMeta = this.stageResolver(entry.stage);
      const stageBadge = createStageBadge(stageMeta);
      if (stageBadge) {
        item.append(stageBadge);
      }

      const messageEl = document.createElement('span');
      messageEl.className = 'task-log__message';
      messageEl.textContent = entry.message;
      item.append(messageEl);

      if (this.taskResolver) {
        const token = createTaskToken(this.taskResolver(entry.taskId));
        if (token) {
          item.append(token);
        }
      }

      list.append(item);
    }

    container.append(list);
    return container;
  }

  renderInto(target, messages) {
    if (!(target instanceof Element)) {
      return;
    }
    target.innerHTML = '';
    const node = this.render(messages);
    target.append(node);
  }
}

export function createProgressFeed(options) {
  return new ProgressFeed(options);
}
