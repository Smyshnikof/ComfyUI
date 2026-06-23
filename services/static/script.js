console.log('JavaScript loaded');
let selectedPresets = [];
let selectedVariants = {}; // {presetId: [variantId1, variantId2, ...]}
let installedStatus = {};

window.setPresetProgressVisible = function(visible) {
  const progress = document.getElementById('preset-progress');
  if (progress) progress.hidden = !visible;
  document.body.classList.toggle('preset-download-active', visible);
};

window.openManageModal = function() {
  const modal = document.getElementById('manage-modal');
  if (modal) modal.classList.add('open');
  if (typeof initPresetForm === 'function') initPresetForm();
  if (typeof loadCommunityPresetList === 'function') loadCommunityPresetList();
};

window.closeManageModal = function() {
  const modal = document.getElementById('manage-modal');
  if (modal) modal.classList.remove('open');
};

window.updateCommunityBadge = function(count) {
  const badge = document.getElementById('community-count-badge');
  if (!badge || count === undefined) return;
  if (count > 0) {
    badge.hidden = false;
    badge.textContent = String(count);
  } else {
    badge.hidden = true;
  }
};

document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') closeManageModal();
});
console.log('selectedPresets initialized:', selectedPresets);

// Убеждаемся, что функции доступны глобально
window.switchTab = function(tabName) {
  // Убираем активный класс со всех табов и контента
  document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
  
  // Активируем выбранный таб
  document.querySelector(`[onclick="switchTab('${tabName}')"]`).classList.add('active');
  document.getElementById(`${tabName}-tab`).classList.add('active');
  
  // Если переключаемся на HuggingFace, активируем таб "Прямая ссылка"
  if (tabName === 'huggingface') {
    switchHFMethod('url');
  }
}

window.switchHFMethod = function(method) {
  // Убираем активный класс со всех табов в HuggingFace разделе
  document.querySelectorAll('#huggingface-tab .tabs .tab').forEach(tab => tab.classList.remove('active'));
  
  // Активируем выбранный таб
  document.querySelector(`#huggingface-tab [onclick="switchHFMethod('${method}')"]`).classList.add('active');
  
  // Показываем/скрываем формы
  if (method === 'url') {
    document.getElementById('hf-url-form').style.display = 'block';
    document.getElementById('hf-repo-form').style.display = 'none';
  } else {
    document.getElementById('hf-url-form').style.display = 'none';
    document.getElementById('hf-repo-form').style.display = 'block';
  }
}

// Глобальный объект для хранения выбранных вариантов (уже объявлен выше)

window.togglePresetCard = function(presetId, event) {
  console.log('togglePresetCard called with:', presetId, event);
  // Для пресетов с вариантами - разворачиваем/сворачиваем карточку
  const card = document.querySelector(`[data-preset="${presetId}"]`);
  if (!card) {
    console.error('Card not found for preset:', presetId);
    return;
  }
  
  // Проверяем, был ли клик на варианте или видео-гайде
  if (event && event.target) {
    const clickedElement = event.target;
    
    // Если клик был на варианте или видео-гайде, не раскрываем/сворачиваем
    if (clickedElement.closest('.preset-variant-item') || 
        clickedElement.closest('.video-guide-icon')) {
      console.log('Click on variant or video guide, ignoring');
      return;
    }
    
    // Если клик был на иконке раскрытия, всегда раскрываем/сворачиваем
    if (clickedElement.closest('.preset-expand-icon')) {
      console.log('Click on expand icon, toggling');
      card.classList.toggle('expanded');
      return;
    }
  }
  
  // Обычный клик на карточке - если не раскрыта, раскрываем; если раскрыта, сворачиваем
  // Но если карточка уже выделена (selected), то сворачиваем
  if (card.classList.contains('expanded')) {
    // Если раскрыта и выделена - сворачиваем
    if (card.classList.contains('selected')) {
      card.classList.remove('expanded');
    } else {
      // Если раскрыта но не выделена - просто сворачиваем
      card.classList.remove('expanded');
    }
  } else {
    // Если не раскрыта - всегда раскрываем при клике
    card.classList.add('expanded');
  }
}

window.togglePreset = function(presetId) {
  console.log('togglePreset called with:', presetId);
  const card = document.querySelector(`[data-preset="${presetId}"]`);
  console.log('Card found:', card);
  
  if (selectedPresets.includes(presetId)) {
    selectedPresets = selectedPresets.filter(p => p !== presetId);
    card.classList.remove('selected');
    console.log('Removed preset:', presetId);
  } else {
    selectedPresets.push(presetId);
    card.classList.add('selected');
    console.log('Added preset:', presetId);
  }
  
  const btn = document.getElementById('download-presets-btn');
  if (btn) {
    // Подсчитываем общее количество выбранных пресетов (обычные + варианты)
    let totalSelected = selectedPresets.length;
    Object.values(selectedVariants).forEach(variants => {
      totalSelected += variants.length;
    });
    
    btn.disabled = totalSelected === 0;
    btn.textContent = totalSelected > 0 ? 
      `📥 Скачать выбранные пресеты (${totalSelected})` : 
      '📥 Скачать выбранные пресеты';
  }
  
  console.log('Selected presets:', selectedPresets);
}

window.toggleVariant = function(parentId, variantId) {
  // Обработка выбора варианта внутри карточки
  const checkbox = document.getElementById(`variant-${variantId}`);
  const card = document.querySelector(`[data-preset="${parentId}"]`);
  
  if (!selectedVariants[parentId]) {
    selectedVariants[parentId] = [];
  }
  
  if (checkbox.checked) {
    if (!selectedVariants[parentId].includes(variantId)) {
      selectedVariants[parentId].push(variantId);
    }
    card.classList.add('selected');
  } else {
    selectedVariants[parentId] = selectedVariants[parentId].filter(v => v !== variantId);
    // Если нет выбранных вариантов, убираем выделение карточки
    if (selectedVariants[parentId].length === 0) {
      card.classList.remove('selected');
      delete selectedVariants[parentId];
    }
  }
  
  const btn = document.getElementById('download-presets-btn');
  if (btn) {
    // Подсчитываем общее количество выбранных пресетов (обычные + варианты)
    let totalSelected = selectedPresets.length;
    Object.values(selectedVariants).forEach(variants => {
      totalSelected += variants.length;
    });
    
    btn.disabled = totalSelected === 0;
    btn.textContent = totalSelected > 0 ? 
      `📥 Скачать выбранные пресеты (${totalSelected})` : 
      '📥 Скачать выбранные пресеты';
  }
}


window.downloadPresets = function(forceDownload) {
  // Собираем все выбранные пресеты (обычные + варианты)
  let allSelectedPresets = [...selectedPresets];
  Object.values(selectedVariants).forEach(variants => {
    allSelectedPresets.push(...variants);
  });
  
  if (allSelectedPresets.length === 0) {
    alert('Пожалуйста, выберите хотя бы один пресет для скачивания');
    return;
  }
  
  const result = document.getElementById('preset-result');
  const btn = document.getElementById('download-presets-btn');
  
  // Показываем прогресс
  setPresetProgressVisible(true);
  result.textContent = '';
  result.innerHTML = '';
  btn.disabled = true;
  btn.textContent = 'Загрузка...';
  
  // Отправляем запрос
  const formData = new FormData();
  formData.append('presets', allSelectedPresets.join(','));
  formData.append('force', forceDownload ? '1' : '0');
  
  fetch('/download_presets', {
    method: 'POST',
    body: formData
  })
  .then(response => response.json())
  .then(data => {
    if (data.warning) {
      setPresetProgressVisible(false);
      btn.disabled = false;
      window.updatePresetDownloadButtonLabel();
      window.showDiskSpaceWarning(data);
      return;
    }
    if (data.task_id) {
      result.textContent = data.message;
      pollStatus(data.task_id);
    } else {
      result.textContent = data.message;
      setPresetProgressVisible(false);
      btn.disabled = false;
      window.updatePresetDownloadButtonLabel();
    }
  })
  .catch(error => {
    result.textContent = '❌ Ошибка: ' + error.message;
    setPresetProgressVisible(false);
    btn.disabled = false;
    window.updatePresetDownloadButtonLabel();
  });
}

window.updatePresetDownloadButtonLabel = function() {
  const btn = document.getElementById('download-presets-btn');
  if (!btn) return;
  let totalSelected = selectedPresets.length;
  Object.values(selectedVariants).forEach(variants => {
    totalSelected += variants.length;
  });
  btn.disabled = totalSelected === 0;
  if (totalSelected === 0) {
    btn.textContent = '📥 Скачать выбранные пресеты';
    return;
  }
  const allIds = [...selectedPresets];
  Object.values(selectedVariants).forEach(variants => allIds.push(...variants));
  const allFull = allIds.length > 0 && allIds.every(id => installedStatus[id]?.state === 'full');
  btn.textContent = allFull ?
    `🔄 Перекачать (${totalSelected})` :
    `📥 Скачать выбранные пресеты (${totalSelected})`;
}

window.loadTokenSavedStatus = function() {
  fetch('/tokens/status')
    .then(response => response.json())
    .then(data => {
      const badge = document.getElementById('hf-token-saved-badge');
      if (badge) {
        badge.hidden = !data.hf;
      }
    })
    .catch(() => {});
}

window.loadInstalledStatus = function() {
  fetch('/installed')
    .then(response => response.json())
    .then(data => {
      installedStatus = data || {};
      applyInstalledBadges();
      updatePresetDownloadButtonLabel();
    })
    .catch(() => {});
}

window.applyInstalledBadges = function() {
  document.querySelectorAll('.preset-card[data-preset]').forEach(card => {
    const presetId = card.dataset.preset;
    const slot = card.querySelector('.preset-install-slot');
    if (!slot) return;
    let badge = slot.querySelector('.preset-install-badge');
    if (!badge) {
      badge = document.createElement('span');
      badge.className = 'preset-install-badge';
      slot.appendChild(badge);
    }
    const info = installedStatus[presetId];
    if (!info || info.state === 'none') {
      badge.textContent = '';
      badge.className = 'preset-install-badge';
      badge.hidden = true;
      return;
    }
    badge.hidden = false;
    badge.className = `preset-install-badge ${info.state}`;
    badge.textContent = info.state === 'full'
      ? `✅ установлен (${info.have}/${info.total})`
      : `🟡 частично (${info.have}/${info.total})`;
  });

  document.querySelectorAll('.preset-variant-item input[data-variant]').forEach(input => {
    const variantId = input.dataset.variant;
    const item = input.closest('.preset-variant-item');
    if (!item) return;
    let badge = item.querySelector('.preset-variant-badge');
    if (!badge) {
      badge = document.createElement('span');
      badge.className = 'preset-variant-badge';
      item.querySelector('label')?.appendChild(badge);
    }
    const info = installedStatus[variantId];
    if (!info || info.state === 'none') {
      badge.textContent = '';
      badge.className = 'preset-variant-badge';
      return;
    }
    badge.className = `preset-variant-badge ${info.state}`;
    badge.textContent = info.state === 'full' ? ' ✅' : ` 🟡 ${info.have}/${info.total}`;
  });
}

window.showDiskSpaceWarning = function(data) {
  const result = document.getElementById('preset-result');
  result.innerHTML = '';

  const needed = data.needed_gb > 0 ? data.needed_gb : 'неизвестно';
  const free = data.free_gb !== undefined ? data.free_gb : '?';
  const text = document.createElement('div');
  text.textContent = `⚠️ Не хватит места: нужно ~${needed} GB, свободно ${free} GB`;
  result.appendChild(text);

  if (data.message) {
    const detail = document.createElement('div');
    detail.style.cssText = 'margin-top:8px;color:var(--muted);font-size:14px;';
    detail.textContent = data.message;
    result.appendChild(detail);
  }

  const forceBtn = document.createElement('button');
  forceBtn.className = 'btn btn-preset';
  forceBtn.style.marginTop = '12px';
  forceBtn.textContent = 'Всё равно скачать';
  forceBtn.onclick = function() {
    downloadPresets(true);
  };
  result.appendChild(forceBtn);
}

window.pollStatus = function(taskId) {
  const progressFill = document.getElementById('preset-progress-fill');
  const progressText = document.getElementById('preset-progress-text');
  const result = document.getElementById('preset-result');
  const btn = document.getElementById('download-presets-btn');
  
  fetch(`/status/${taskId}`)
  .then(response => response.json())
  .then(data => {
    if (data.status === 'completed' || data.status === 'error') {
      result.textContent = data.message;
      setPresetProgressVisible(false);
      btn.disabled = false;
      window.updatePresetDownloadButtonLabel();
      window.loadInstalledStatus();
    } else if (data.status === 'running') {
      // Обновляем прогресс-бар
      const progressPercent = data.progress || 0;
      progressFill.style.width = progressPercent + '%';
      
      // Формируем текст прогресса
      let progressMessage = data.message || 'Загрузка...';
      if (data.total_files && data.current_file !== undefined) {
        progressMessage = `📥 Файл ${data.current_file} из ${data.total_files}`;
        if (data.current_filename) {
          const shortName = data.current_filename.length > 50 
            ? data.current_filename.substring(0, 47) + '...' 
            : data.current_filename;
          progressMessage += `: ${shortName}`;
        }
        progressMessage += ` (${Math.round(progressPercent)}%)`;
      }
      
      progressText.textContent = progressMessage;
      result.textContent = data.message || 'Загрузка...';
      
      // Повторяем через 500ms для более плавного обновления прогресса
      setTimeout(() => pollStatus(taskId), 500);
    } else {
      result.textContent = '❌ Неизвестный статус: ' + data.message;
      setPresetProgressVisible(false);
      btn.disabled = false;
      window.updatePresetDownloadButtonLabel();
    }
  })
  .catch(error => {
    result.textContent = '❌ Ошибка проверки статуса: ' + error.message;
    setPresetProgressVisible(false);
    btn.disabled = false;
    window.updatePresetDownloadButtonLabel();
  });
}

// Остальные функции для HuggingFace...

// Фильтрация по категориям и поиск
let currentCategory = 'all';
let searchQuery = '';

window.filterByCategory = function(category, event) {
  currentCategory = category;
  
  // Обновляем активный фильтр
  document.querySelectorAll('.category-filter').forEach(filter => {
    filter.classList.remove('active');
  });
  if (event && event.target) {
    event.target.closest('.category-filter')?.classList.add('active');
  } else {
    // Если event не передан, ищем по data-category
    document.querySelectorAll('.category-filter').forEach(filter => {
      if (filter.getAttribute('data-category') === category || 
          (category === 'all' && filter.textContent.includes('Все'))) {
        filter.classList.add('active');
      }
    });
  }
  
  // Применяем фильтры
  applyFilters();
}

window.filterPresets = function() {
  searchQuery = document.getElementById('preset-search').value.toLowerCase().trim();
  applyFilters();
}

window.applyFilters = function() {
  const cards = document.querySelectorAll('.preset-card');
  let visibleCount = 0;
  
  cards.forEach(card => {
    const presetCategory = card.getAttribute('data-category');
    const presetName = (card.querySelector('.preset-name')?.textContent || '').toLowerCase();
    const presetDesc = (card.querySelector('.preset-desc')?.textContent || '').toLowerCase();
    const presetInfo = (card.querySelector('.preset-info')?.textContent || '').toLowerCase();
    
    // Проверяем категорию
    const categoryMatch = currentCategory === 'all' || presetCategory === currentCategory;
    
    // Проверяем поисковый запрос
    const searchMatch = !searchQuery || 
      presetName.includes(searchQuery) || 
      presetDesc.includes(searchQuery) || 
      presetInfo.includes(searchQuery);
    
    // Показываем/скрываем карточку
    if (categoryMatch && searchMatch) {
      card.classList.remove('hidden');
      visibleCount++;
    } else {
      card.classList.add('hidden');
    }
  });
  
  // Показываем сообщение, если ничего не найдено
  const grid = document.getElementById('preset-grid');
  let noResultsMsg = document.getElementById('no-results-message');
  
  if (visibleCount === 0) {
    if (!noResultsMsg) {
      noResultsMsg = document.createElement('div');
      noResultsMsg.id = 'no-results-message';
      noResultsMsg.style.cssText = 'text-align: center; padding: 40px; color: var(--muted); font-size: 16px;';
      noResultsMsg.textContent = '😔 Пресеты не найдены';
      grid.appendChild(noResultsMsg);
    }
  } else {
    if (noResultsMsg) {
      noResultsMsg.remove();
    }
  }
}

window.resumeActiveDownloads = function() {
  fetch('/api/tasks')
    .then(r => r.json())
    .then(data => {
      const tasks = (data.tasks || []).filter(t => t.status === 'running');
      if (!tasks.length) return;

      const isPresetTask = t => t.kind === 'preset' || (!t.kind && t.total_files !== undefined);
      const isHfTask = t => t.kind === 'hf' || t.kind === 'url' || (!t.kind && t.total_files === undefined);
      const presetTask = tasks.find(isPresetTask);
      const hfTask = tasks.find(isHfTask);

      if (presetTask) {
        const fill = document.getElementById('preset-progress-fill');
        const text = document.getElementById('preset-progress-text');
        const b = document.getElementById('download-presets-btn');
        const result = document.getElementById('preset-result');
        const pct = presetTask.progress || 0;
        setPresetProgressVisible(true);
        if (fill) fill.style.width = pct + '%';
        if (text) {
          let msg = presetTask.message || 'Загрузка...';
          if (presetTask.total_files && presetTask.current_file !== undefined) {
            msg = `📥 Файл ${presetTask.current_file} из ${presetTask.total_files}`;
            if (presetTask.current_filename) {
              const short = presetTask.current_filename.length > 50
                ? presetTask.current_filename.substring(0, 47) + '...'
                : presetTask.current_filename;
              msg += `: ${short}`;
            }
            msg += ` (${Math.round(pct)}%)`;
          }
          text.textContent = msg;
        }
        if (b) { b.disabled = true; b.textContent = 'Загрузка...'; }
        if (result && presetTask.message) result.textContent = presetTask.message;
        pollStatus(presetTask.task_id);
      }

      if (hfTask) {
        const p = document.getElementById('hf-progress');
        const fill = document.getElementById('hf-progress-fill');
        const text = document.getElementById('hf-progress-text');
        const hfForm = document.getElementById('hf-repo-form');
        const urlForm = document.getElementById('hf-url-form');
        const pct = hfTask.progress || 0;
        if (p) p.style.display = 'block';
        if (fill) fill.style.width = pct + '%';
        if (text) text.textContent = hfTask.message || 'Загрузка...';
        [hfForm, urlForm].forEach(form => {
          const btn = form && form.querySelector('button[type="submit"]');
          if (btn) { btn.disabled = true; btn.textContent = 'Загрузка...'; }
        });
        const result = document.getElementById('hf-result');
        if (result && hfTask.message) result.textContent = hfTask.message;
        if (typeof window.pollHFStatus === 'function') {
          window.pollHFStatus(hfTask.task_id);
        }
      }
    })
    .catch(() => {});
};

// Инициализация
document.addEventListener('DOMContentLoaded', function() {
  if (typeof applyFilters === 'function') {
    applyFilters();
  }
  if (typeof loadInstalledStatus === 'function') {
    loadInstalledStatus();
  }
  if (typeof loadTokenSavedStatus === 'function') {
    loadTokenSavedStatus();
  }
  if (typeof initPresetForm === 'function') {
    initPresetForm();
  }
  if (typeof resumeActiveDownloads === 'function') {
    resumeActiveDownloads();
  }
});

window.refreshInstalled = window.loadInstalledStatus;

let formMeta = { categories: [], folders: [] };
let editingPresetId = null;

window.loadCommunityPresetList = async function() {
  const wrap = document.getElementById('community-preset-list');
  if (!wrap) return;
  try {
    const resp = await fetch('/api/community-presets');
    const data = await resp.json();
    const items = data.presets || [];
    if (!items.length) {
      wrap.innerHTML = '<div class="community-preset-empty">Пока нет своих пресетов — создай или импортируй ниже.</div>';
      return;
    }
    wrap.innerHTML = items.map(p => {
      const sub = [
        p.category || '',
        p.file_count ? `${p.file_count} файл(ов)` : '',
        p.has_variants ? 'варианты' : '',
      ].filter(Boolean).join(' · ');
      const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
      return `<div class="community-preset-item" data-id="${esc(p.id)}">
        <div class="community-preset-meta">
          <div class="community-preset-name">${esc(p.name)}</div>
          <div class="community-preset-sub">${esc(sub)}</div>
        </div>
        <div class="community-preset-actions">
          <button type="button" class="btn" onclick="editCommunityPreset('${esc(p.id)}')" title="Редактировать">✏️</button>
          <button type="button" class="btn" onclick="deleteCommunityPreset('${esc(p.id)}')" title="Удалить">🗑</button>
        </div>
      </div>`;
    }).join('');
  } catch (e) {
    wrap.innerHTML = '<div class="community-preset-empty">Не удалось загрузить список</div>';
    console.warn('loadCommunityPresetList failed', e);
  }
};

window.resetPresetForm = function() {
  editingPresetId = null;
  const nameEl = document.getElementById('np-name');
  const descEl = document.getElementById('np-desc');
  if (nameEl) nameEl.value = '';
  if (descEl) descEl.value = '';
  const cat = document.getElementById('np-category');
  if (cat && cat.options.length) cat.selectedIndex = 0;
  onCategoryChange();
  const filesWrap = document.getElementById('np-files');
  if (filesWrap) {
    filesWrap.innerHTML = '';
    addFileRow();
  }
  const banner = document.getElementById('np-edit-banner');
  if (banner) banner.classList.remove('visible');
  const saveBtn = document.getElementById('np-save-btn');
  if (saveBtn) saveBtn.textContent = 'Сохранить пресет';
  const res = document.getElementById('np-result');
  if (res) res.textContent = '';
};

window.editCommunityPreset = async function(pid) {
  const res = document.getElementById('np-result');
  try {
    const resp = await fetch('/api/community-presets/' + encodeURIComponent(pid));
    const data = await resp.json();
    if (!data.ok || !data.preset) {
      if (res) res.textContent = data.message || '❌ Пресет не найден';
      return;
    }
    const preset = data.preset;
    if (preset.variant_groups && preset.variant_groups.length) {
      if (res) res.textContent = '❌ Пресеты с вариантами пока нельзя редактировать в форме';
      return;
    }
    editingPresetId = pid;
    document.getElementById('np-name').value = preset.name || '';
    document.getElementById('np-desc').value = preset.description || '';
    const cat = document.getElementById('np-category');
    if (cat) {
      const cid = preset.category || '';
      const hasOpt = [...cat.options].some(o => o.value === cid);
      if (hasOpt) cat.value = cid;
      else if (cid) {
        const opt = document.createElement('option');
        opt.value = cid;
        opt.textContent = cid;
        cat.insertBefore(opt, cat.querySelector('option[value="__new__"]'));
        cat.value = cid;
      }
    }
    onCategoryChange();
    const filesWrap = document.getElementById('np-files');
    if (filesWrap) {
      filesWrap.innerHTML = '';
      const files = preset.files || [];
      if (files.length) files.forEach(f => addFileRow(f));
      else addFileRow();
    }
    const banner = document.getElementById('np-edit-banner');
    const label = document.getElementById('np-edit-label');
    if (banner) banner.classList.add('visible');
    if (label) label.textContent = preset.name || pid;
    const saveBtn = document.getElementById('np-save-btn');
    if (saveBtn) saveBtn.textContent = 'Сохранить изменения';
    if (res) res.textContent = '';
    document.getElementById('add-preset-block')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } catch (e) {
    if (res) res.textContent = '❌ ' + e.message;
  }
};

window.deleteCommunityPreset = function(pid) {
  const item = document.querySelector(`.community-preset-item[data-id="${pid}"] .community-preset-name`);
  const label = item ? item.textContent : pid;
  if (!confirm(`Удалить пресет «${label}»? Файл на диске не трогаем — только запись пресета.`)) return;
  const res = document.getElementById('np-result');
  fetch('/presets/community/' + encodeURIComponent(pid), { method: 'DELETE' })
    .then(r => r.json())
    .then(d => {
      if (res) res.textContent = d.message || (d.ok ? 'OK' : 'Ошибка');
      if (d.ok) {
        if (editingPresetId === pid) resetPresetForm();
        refreshPresetGrid();
        loadCommunityPresetList();
      }
    })
    .catch(e => {
      if (res) res.textContent = '❌ ' + e.message;
    });
};

window.initPresetForm = async function() {
  try {
    const resp = await fetch('/api/form-meta');
    formMeta = await resp.json();
    const cat = document.getElementById('np-category');
    if (cat && formMeta.categories) {
      cat.innerHTML = formMeta.categories.map(c =>
        `<option value="${c.id}">${c.icon} ${c.name}</option>`
      ).join('') + '<option value="__new__">➕ Своя категория</option>';
    }
    const filesWrap = document.getElementById('np-files');
    if (filesWrap && !filesWrap.querySelector('.np-file-row')) {
      addFileRow();
    }
  } catch (e) {
    console.warn('initPresetForm failed', e);
  }
};

window.onCategoryChange = function() {
  const isNew = document.getElementById('np-category')?.value === '__new__';
  const block = document.getElementById('np-new-cat');
  if (block) block.style.display = isNew ? 'block' : 'none';
};

window.addFileRow = function(data) {
  const wrap = document.getElementById('np-files');
  if (!wrap) return;
  const row = document.createElement('div');
  row.className = 'np-file-row';
  const folders = (formMeta.folders || []).map(f =>
    `<option value="${f}">${f}</option>`
  ).join('');
  row.innerHTML = `
    <input class="np-url" type="text" placeholder="https://huggingface.co/.../model.safetensors" />
    <select class="np-folder">${folders}</select>
    <input class="np-filename" type="text" placeholder="имя (необяз.)" />
    <button type="button" class="btn" onclick="this.parentNode.remove()">✕</button>`;
  wrap.appendChild(row);
  if (data) {
    const urlIn = row.querySelector('.np-url');
    const folderSel = row.querySelector('.np-folder');
    const nameIn = row.querySelector('.np-filename');
    if (urlIn && data.url) urlIn.value = data.url;
    if (folderSel && data.folder) {
      if (![...folderSel.options].some(o => o.value === data.folder)) {
        const opt = document.createElement('option');
        opt.value = data.folder;
        opt.textContent = data.folder;
        folderSel.appendChild(opt);
      }
      folderSel.value = data.folder;
    }
    if (nameIn && data.filename) nameIn.value = data.filename;
  }
};

window.savePreset = function() {
  if (typeof createPreset === 'function') createPreset();
};

window.createPreset = function() {
  const name = (document.getElementById('np-name')?.value || '').trim();
  const sel = document.getElementById('np-category')?.value || '';
  const category = sel === '__new__'
    ? (document.getElementById('np-new-cat-name')?.value || '').trim()
    : sel;
  const category_icon = sel === '__new__'
    ? (document.getElementById('np-new-cat-icon')?.value || '').trim() : '';
  const description = (document.getElementById('np-desc')?.value || '').trim();
  const res = document.getElementById('np-result');
  const files = [...document.querySelectorAll('.np-file-row')].map(r => ({
    url: (r.querySelector('.np-url')?.value || '').trim(),
    folder: r.querySelector('.np-folder')?.value || '',
    filename: (r.querySelector('.np-filename')?.value || '').trim() || null,
  })).filter(f => f.url);

  if (!name || !files.length) {
    if (res) res.textContent = '❌ Нужно название и хотя бы один файл';
    return;
  }
  if (!category) {
    if (res) res.textContent = '❌ Укажи категорию';
    return;
  }

  const fd = new FormData();
  fd.append('name', name);
  fd.append('category', category);
  fd.append('category_icon', category_icon);
  fd.append('description', description);
  fd.append('files_json', JSON.stringify(files));
  if (editingPresetId) fd.append('preset_id', editingPresetId);

  const url = editingPresetId ? '/presets/update' : '/presets/create';
  fetch(url, { method: 'POST', body: fd })
    .then(r => r.json())
    .then(d => {
      if (res) res.textContent = d.message || (d.ok ? 'OK' : 'Ошибка');
      if (d.ok) {
        resetPresetForm();
        refreshPresetGrid();
        loadCommunityPresetList();
      }
    })
    .catch(e => {
      if (res) res.textContent = '❌ ' + e.message;
    });
};

window.refreshPresetGrid = function() {
  return fetch('/api/presets/fragment')
    .then(r => r.json())
    .then(d => {
      const grid = document.getElementById('preset-grid');
      const filters = document.getElementById('category-filters');
      if (grid) grid.innerHTML = d.presets_html;
      if (filters) filters.innerHTML = d.category_filters_html;
      if (typeof updateCommunityBadge === 'function') updateCommunityBadge(d.community_count);
      selectedPresets = [];
      selectedVariants = {};
      if (typeof applyFilters === 'function') applyFilters();
      if (typeof loadInstalledStatus === 'function') loadInstalledStatus();
      const dlBtn = document.getElementById('download-presets-btn');
      if (dlBtn) {
        dlBtn.disabled = true;
        dlBtn.textContent = '📥 Скачать выбранные пресеты';
      }
    });
};

window.reloadPresets = function() {
  const btn = document.getElementById('reload-presets-btn');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Обновление...';
  }
  fetch('/reload_presets', { method: 'POST' })
    .then(r => r.json())
    .then(data => {
      if (!data.ok) throw new Error('reload failed');
      return refreshPresetGrid().then(() => {
        if (typeof loadCommunityPresetList === 'function') loadCommunityPresetList();
      });
    })
    .catch(err => alert('Не удалось обновить пресеты: ' + err.message))
    .finally(() => {
      if (btn) {
        btn.disabled = false;
        btn.textContent = '🔄 Обновить';
      }
    });
};

window.downloadPresetFile = function(pid, event) {
  if (event) event.stopPropagation();
  window.location = `/presets/export/${pid}`;
};

window.copyPresetCode = function(pid, event) {
  if (event) event.stopPropagation();
  fetch(`/presets/code/${pid}`)
    .then(r => r.json())
    .then(d => {
      if (!d.ok) {
        alert(d.message || 'Не удалось получить код');
        return;
      }
      let hint;
      if (d.kind === 'ref') {
        hint = `Код пресета: ${d.code}\n\nВстроенный пресет — на поде с тем же загрузчиком он уже в списке.\nКод можно использовать, чтобы указать, какой пресет качать.`;
      } else {
        hint = `Код пресета скопирован (${d.code.length} симв.)!\n\nВставь строку на другом поде: ⚙️ Свои пресеты → поле импорта → Импорт.\n\nЕсли не влезает — «Скачать .json».`;
      }
      navigator.clipboard.writeText(d.code)
        .then(() => alert(hint))
        .catch(() => prompt('Скопируй код пресета:', d.code));
    })
    .catch(e => alert('❌ ' + e.message));
};

window.importPresetFile = function(input) {
  const f = input.files && input.files[0];
  if (!f) return;
  const fd = new FormData();
  fd.append('file', f);
  fetch('/presets/import_file', { method: 'POST', body: fd })
    .then(r => r.json())
    .then(d => {
      alert(d.message);
      if (d.ok) refreshPresetGrid().then(() => {
        loadCommunityPresetList();
        closeManageModal();
      });
    })
    .catch(e => alert('❌ ' + e.message))
    .finally(() => { input.value = ''; });
};

window.importPresetSmart = function() {
  const input = document.getElementById('import-preset-input');
  const btn = document.getElementById('import-preset-btn');
  const val = (input && input.value || '').trim();
  if (!val) {
    alert('Вставь код пресета или ссылку https://...');
    return;
  }
  const isUrl = /^https?:\/\//i.test(val);
  const fd = new FormData();
  fd.append(isUrl ? 'url' : 'code', val);
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Импорт...';
  }
  fetch(isUrl ? '/presets/import' : '/presets/import_code', { method: 'POST', body: fd })
    .then(r => r.json())
    .then(d => {
      if (!d.ok) throw new Error(d.message || 'import failed');
      if (input) input.value = '';
      return refreshPresetGrid().then(() => {
        loadCommunityPresetList();
        closeManageModal();
      });
    })
    .catch(err => alert('Импорт: ' + err.message))
    .finally(() => {
      if (btn) {
        btn.disabled = false;
        btn.textContent = 'Импорт';
      }
    });
};

window.importPresetByUrl = window.importPresetSmart;
