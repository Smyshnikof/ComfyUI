let selectedPresets = [];
let selectedVariants = {};
let installedStatus = {};
let currentTaskId = null;
let pollTimer = null;

function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  document.querySelector(`[data-tab="${name}"]`).classList.add('active');
  document.getElementById(`tab-${name}`).classList.add('active');
}

function collectSelectedIds() {
  const ids = [...selectedPresets];
  Object.values(selectedVariants).forEach(v => ids.push(...v));
  return ids;
}

function togglePreset(presetId) {
  const card = document.querySelector(`[data-preset="${presetId}"]`);
  if (selectedPresets.includes(presetId)) {
    selectedPresets = selectedPresets.filter(p => p !== presetId);
    card.classList.remove('selected');
  } else {
    selectedPresets.push(presetId);
    card.classList.add('selected');
  }
}

function togglePresetCard(presetId, event) {
  const card = document.querySelector(`[data-preset="${presetId}"]`);
  if (!card) return;
  if (event && event.target) {
    if (event.target.closest('.preset-variant-item') || event.target.closest('.preset-card-footer')) return;
    if (event.target.closest('.preset-expand-icon')) {
      card.classList.toggle('expanded');
      return;
    }
  }
  card.classList.toggle('expanded');
}

function toggleVariant(parentId, variantId) {
  const checkbox = document.getElementById(`variant-${variantId}`);
  const card = document.querySelector(`[data-preset="${parentId}"]`);
  if (!selectedVariants[parentId]) selectedVariants[parentId] = [];
  if (checkbox.checked) {
    if (!selectedVariants[parentId].includes(variantId)) selectedVariants[parentId].push(variantId);
    card.classList.add('selected');
  } else {
    selectedVariants[parentId] = selectedVariants[parentId].filter(v => v !== variantId);
    if (selectedVariants[parentId].length === 0) {
      card.classList.remove('selected');
      delete selectedVariants[parentId];
    }
  }
}

function filterByCategory(category, event) {
  if (event) event.stopPropagation();
  document.querySelectorAll('.category-filter').forEach(f => f.classList.remove('active'));
  document.querySelector(`[data-category="${category}"]`).classList.add('active');
  document.querySelectorAll('.preset-card').forEach(card => {
    const match = category === 'all' || card.dataset.category === category;
    card.classList.toggle('hidden', !match);
  });
  filterPresets();
}

function filterPresets() {
  const q = (document.getElementById('search-input')?.value || '').toLowerCase().trim();
  const activeCat = document.querySelector('.category-filter.active')?.dataset.category || 'all';
  document.querySelectorAll('.preset-card').forEach(card => {
    const text = card.textContent.toLowerCase();
    const catOk = activeCat === 'all' || card.dataset.category === activeCat;
    const searchOk = !q || text.includes(q);
    card.classList.toggle('hidden', !(catOk && searchOk));
  });
}

function applyInstallBadges() {
  document.querySelectorAll('.preset-card').forEach(card => {
    const pid = card.dataset.preset;
    const slot = card.querySelector('.preset-install-slot');
    if (!slot) return;
    const st = installedStatus[pid];
    if (!st || st.state === 'none') {
      slot.innerHTML = '';
      return;
    }
    const cls = st.state === 'full' ? 'full' : 'partial';
    const label = st.state === 'full' ? 'установлено' : `${st.have}/${st.total}`;
    slot.innerHTML = `<span class="preset-install-badge ${cls}">${label}</span>`;
  });
}

async function refreshInstalled() {
  try {
    const resp = await fetch('/installed');
    installedStatus = await resp.json();
    applyInstallBadges();
  } catch (e) {
    console.warn('installed status', e);
  }
}

function showProgress(visible) {
  document.getElementById('preset-progress').classList.toggle('hidden', !visible);
}

function finishPollTask(data) {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  const msg = data?.message || 'Готово';
  const single = document.getElementById('single-result');
  if (single) single.textContent = msg;
  setTimeout(() => showProgress(false), 4000);
  refreshInstalled();
  currentTaskId = null;
}

function pollTask(taskId) {
  currentTaskId = taskId;
  if (pollTimer) clearInterval(pollTimer);
  let pollErrors = 0;
  showProgress(true);
  pollTimer = setInterval(async () => {
    try {
      const resp = await fetch(`/status/${taskId}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      pollErrors = 0;
      const data = await resp.json();
      const fill = document.getElementById('progress-fill');
      const text = document.getElementById('progress-text');
      const msg = data.message || '...';
      if (fill) fill.style.width = `${data.progress || 0}%`;
      if (text) text.textContent = msg;
      const single = document.getElementById('single-result');
      if (single) single.textContent = msg;
      if (data.status === 'completed') {
        finishPollTask(data);
      } else if (data.status === 'error' || data.status === 'not_found') {
        finishPollTask(data);
        alert(msg || (data.status === 'not_found' ? 'Задача не найдена (перезапуск сервиса?)' : 'Ошибка установки'));
      }
    } catch (e) {
      pollErrors += 1;
      console.error(e);
      if (pollErrors >= 12) {
        finishPollTask({ message: `Потеряна связь с сервером: ${e.message}` });
        alert('Не удалось получить статус установки. Проверьте /workspace/logs/custom_nodes_installer.log');
      }
    }
  }, 500);
}

async function installSelected() {
  const autoRestart = !!document.getElementById('install-restart')?.checked;
  const ids = collectSelectedIds();
  if (!ids.length) {
    alert('Выберите хотя бы один набор');
    return;
  }
  const body = new FormData();
  body.append('presets', ids.join(','));
  body.append('auto_restart', autoRestart ? '1' : '0');
  const resp = await fetch('/install_presets', { method: 'POST', body });
  const data = await resp.json();
  if (data.message && data.message.startsWith('❌')) {
    alert(data.message);
    return;
  }
  if (data.task_id) pollTask(data.task_id);
}

async function installSingleRepo(event) {
  if (event) event.preventDefault();
  const autoRestart = !!document.getElementById('single-restart')?.checked;
  const url = document.getElementById('repo-url').value.trim();
  const result = document.getElementById('single-result');
  const body = new FormData();
  body.append('url', url);
  body.append('auto_restart', autoRestart ? '1' : '0');
  result.textContent = 'Запуск...';
  const resp = await fetch('/install_repo', { method: 'POST', body });
  const data = await resp.json();
  if (data.message && data.message.startsWith('❌')) {
    result.textContent = data.message;
    return;
  }
  result.textContent = data.message || 'Установка...';
  if (data.task_id) pollTask(data.task_id);
}

async function restartComfyUI() {
  try {
    const resp = await fetch('/restart_comfyui', { method: 'POST' });
    const data = await resp.json();
    alert(data.message || (data.ok ? 'ComfyUI перезапущен' : 'Ошибка'));
  } catch (e) {
    alert('Ошибка: ' + e.message);
  }
}

async function validateNodes() {
  const ids = collectSelectedIds();
  const qs = ids.length ? `?presets=${encodeURIComponent(ids.join(','))}` : '';
  const result = document.getElementById('validate-result');
  result.textContent = 'Проверка...';
  try {
    const resp = await fetch(`/api/validate${qs}`);
    const data = await resp.json();
    const lines = [];
    lines.push(data.comfyui_running ? '✅ ComfyUI отвечает' : '❌ ComfyUI не отвечает (запустите и перезагрузите)');
    if (data.log_errors && data.log_errors.length) {
      lines.push('', 'Ошибки в логе:');
      data.log_errors.slice(0, 8).forEach(e => lines.push('  • ' + e));
    }
    (data.presets || []).forEach(p => {
      const st = p.install;
      lines.push('');
      lines.push(`${p.name}: ${st.have}/${st.total} репо`);
      if (p.nodes_ok === true) lines.push('  ✅ check_nodes OK');
      else if (p.nodes_ok === false) lines.push('  ❌ не найдены: ' + (p.missing_nodes || []).join(', '));
    });
    result.textContent = lines.join('\n');
  } catch (e) {
    result.textContent = 'Ошибка: ' + e.message;
  }
}

async function downloadPresetFile(pid, event) {
  if (event) event.stopPropagation();
  window.location.href = `/presets/export/${encodeURIComponent(pid)}`;
}

async function copyPresetCode(pid, event) {
  if (event) event.stopPropagation();
  const resp = await fetch(`/presets/code/${encodeURIComponent(pid)}`);
  const data = await resp.json();
  if (!data.ok) {
    alert(data.message || 'Не удалось получить код');
    return;
  }
  await navigator.clipboard.writeText(data.code);
  alert('Код скопирован');
}

function closeCommunityModal() {
  document.getElementById('community-modal').classList.add('hidden');
}

async function openCommunityModal() {
  const modal = document.getElementById('community-modal');
  modal.classList.remove('hidden');
  const body = document.getElementById('community-modal-body');
  body.innerHTML = '<p class="muted">Загрузка...</p>';
  try {
    const [meta, list] = await Promise.all([
      fetch('/api/form-meta').then(r => r.json()),
      fetch('/api/community-presets').then(r => r.json()),
    ]);
    const cats = meta.categories || [];
    const catOptions = cats.map(c => `<option value="${c.id}">${c.icon} ${c.name}</option>`).join('');
    let listHtml = '<p class="muted">Пока нет своих наборов</p>';
    if (list.presets && list.presets.length) {
      listHtml = '<ul class="community-list">' + list.presets.map(p =>
        `<li><span><b>${p.name}</b> <span class="muted">(${p.repo_count} repo)</span></span>` +
        `<span><button class="preset-action-btn" onclick="editCommunityPreset('${p.id}')">✏️</button> ` +
        `<button class="preset-action-btn" onclick="deleteCommunityPreset('${p.id}')">🗑️</button></span></li>`
      ).join('') + '</ul>';
    }
    body.innerHTML = `
      <div class="modal-section">
        <h3>Импорт</h3>
        <div class="hint">Файл .json, код CUNP1:… или URL на GitHub raw</div>
        <div class="import-row">
          <input type="text" class="input-dark" id="import-code" placeholder="CUNP1:ref:WAN_VIDEO" />
          <button class="btn btn-sm" type="button" onclick="importByCode()">📋 Импорт</button>
        </div>
      </div>
      <hr class="modal-divider" />
      <div class="modal-section">
        <h3>Создать набор</h3>
        <div class="np-field"><label>Название</label><input type="text" class="input-dark" id="np-name" /></div>
        <div class="np-field"><label>Категория</label><select class="input-dark" id="np-category">${catOptions}</select></div>
        <div class="np-field"><label>Описание</label><textarea class="input-dark" id="np-desc" rows="2"></textarea></div>
        <div class="np-field"><label>Репозитории</label><div id="repo-rows"></div></div>
        <button class="btn btn-sm" type="button" onclick="addRepoRow()">➕ Репозиторий</button>
        <div style="margin-top:14px"><button class="btn btn-install" type="button" onclick="saveCommunityPreset()">💾 Сохранить набор</button></div>
      </div>
      <hr class="modal-divider" />
      <div class="modal-section">
        <h3>Мои наборы</h3>
        ${listHtml}
      </div>
    `;
    addRepoRow();
    window._editingPresetId = null;
  } catch (e) {
    body.innerHTML = '<p class="muted">Ошибка: ' + e.message + '</p>';
  }
}

function addRepoRow(url) {
  const container = document.getElementById('repo-rows');
  if (!container) return;
  const row = document.createElement('div');
  row.className = 'repo-row';
  const safeUrl = (url || '').replace(/"/g, '&quot;');
  row.innerHTML = `<input type="text" class="input-dark repo-url" placeholder="https://github.com/..." value="${safeUrl}" />
    <button type="button" class="btn-icon" title="Удалить" onclick="this.parentElement.remove()">✕</button>`;
  container.appendChild(row);
}

async function importByCode() {
  const code = document.getElementById('import-code').value.trim();
  const body = new FormData();
  body.append('code', code);
  const resp = await fetch('/presets/import_code', { method: 'POST', body });
  const data = await resp.json();
  alert(data.message || (data.ok ? 'OK' : 'Ошибка'));
  if (data.ok) {
    await reloadPresetsFragment();
    openCommunityModal();
  }
}

async function saveCommunityPreset() {
  const repos = [];
  document.querySelectorAll('#repo-rows .repo-url').forEach(inp => {
    const u = inp.value.trim();
    if (u) repos.push({ url: u, branch: null, recursive: true, folder: null });
  });
  if (!repos.length) {
    alert('Добавьте хотя бы один репозиторий');
    return;
  }
  const body = new FormData();
  body.append('name', document.getElementById('np-name').value);
  body.append('category', document.getElementById('np-category').value);
  body.append('description', document.getElementById('np-desc').value);
  body.append('repos_json', JSON.stringify(repos));
  const endpoint = window._editingPresetId ? '/presets/update' : '/presets/create';
  if (window._editingPresetId) body.append('preset_id', window._editingPresetId);
  const resp = await fetch(endpoint, { method: 'POST', body });
  const data = await resp.json();
  alert(data.message || (data.ok ? 'Сохранено' : 'Ошибка'));
  if (data.ok) {
    await reloadPresetsFragment();
    closeCommunityModal();
  }
}

async function editCommunityPreset(pid) {
  const resp = await fetch(`/api/community-presets/${encodeURIComponent(pid)}`);
  const data = await resp.json();
  if (!data.ok) return;
  const p = data.preset;
  document.getElementById('np-name').value = p.name || '';
  document.getElementById('np-category').value = p.category || '';
  document.getElementById('np-desc').value = p.description || '';
  const container = document.getElementById('repo-rows');
  container.innerHTML = '';
  (p.repos || []).forEach(r => addRepoRow(r.url));
  window._editingPresetId = pid;
}

async function deleteCommunityPreset(pid) {
  if (!confirm('Удалить набор?')) return;
  await fetch(`/presets/community/${encodeURIComponent(pid)}`, { method: 'DELETE' });
  await reloadPresetsFragment();
  openCommunityModal();
}

async function reloadPresetsFragment() {
  const resp = await fetch('/api/presets/fragment');
  const data = await resp.json();
  document.getElementById('preset-grid').innerHTML = data.presets_html;
  document.getElementById('category-filters').innerHTML = data.category_filters_html;
  const badge = document.getElementById('community-badge');
  if (badge) {
    badge.textContent = String(data.community_count || 0);
    badge.classList.toggle('hidden', !data.community_count);
  }
  selectedPresets = [];
  selectedVariants = {};
  await refreshInstalled();
}

document.addEventListener('DOMContentLoaded', async () => {
  try {
    const h = await fetch('/health').then(r => r.json());
    if (!h.git) document.getElementById('git-warning').hidden = false;
    const emptyBanner = document.getElementById('presets-empty-warning');
    if (emptyBanner && (h.presets === 0 || h.presets === '0')) {
      emptyBanner.hidden = false;
    }
  } catch (e) {}
  refreshInstalled();
  loadManagerConfig();
});

async function loadManagerConfig() {
  const levelEl = document.getElementById('manager-security-level');
  const card = document.getElementById('manager-config-card');
  if (!levelEl) return;
  try {
    const data = await fetch('/api/manager-config').then(r => r.json());
    const level = data.security_level || (data.found ? '—' : 'не задан');
    levelEl.textContent = level;
    if (card) {
      if (data.path) card.title = data.path;
      card.classList.remove('level-weak', 'level-normal', 'level-strong', 'level-normal-');
      if (level && level !== '—' && level !== 'не задан') {
        card.classList.add('level-' + level.replace(/-/g, ''));
      }
    }
    document.querySelectorAll('.seg-control .seg').forEach(btn => {
      const active = btn.dataset.level === level;
      btn.classList.toggle('active', active);
      btn.disabled = active;
    });
  } catch (e) {
    levelEl.textContent = '—';
  }
}

async function setManagerSecurity(level) {
  const body = new FormData();
  body.append('level', level);
  try {
    const resp = await fetch('/api/manager-config/security-level', { method: 'POST', body });
    const data = await resp.json();
    if (!data.ok) {
      alert(data.message || 'Ошибка');
      return;
    }
    alert(data.message + '\n\nПерезагрузите ComfyUI, чтобы Manager подхватил настройку.');
    loadManagerConfig();
  } catch (e) {
    alert('Ошибка: ' + e.message);
  }
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeCommunityModal();
});
