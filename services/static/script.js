console.log('JavaScript loaded');
let selectedPresets = [];
let selectedVariants = {}; // {presetId: [variantId1, variantId2, ...]}
console.log('selectedPresets initialized:', selectedPresets);

function switchTab(tabName) {
  console.log('switchTab called with:', tabName);
  // Убираем активный класс со всех основных табов (первый .tabs) и контента
  const mainTabs = document.querySelectorAll('.tabs:first-of-type .tab');
  mainTabs.forEach(tab => tab.classList.remove('active'));
  
  document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
  
  // Активируем выбранный таб
  mainTabs.forEach(tab => {
    const tabData = tab.getAttribute('data-tab');
    if (tabData === tabName) {
      tab.classList.add('active');
    }
  });
  
  // Активируем соответствующий контент
  const targetTab = document.getElementById(`${tabName}-tab`);
  if (targetTab) {
    targetTab.classList.add('active');
    console.log('Tab activated:', tabName);
  } else {
    console.error('Tab not found:', `${tabName}-tab`);
  }
  
  // Если переключаемся на HuggingFace, активируем таб "Прямая ссылка"
  if (tabName === 'huggingface') {
    setTimeout(() => switchHFMethod('url'), 100);
  }
}

function switchHFMethod(method) {
  console.log('switchHFMethod called with:', method);
  // Убираем активный класс со всех табов в HuggingFace разделе
  const hfTabs = document.querySelectorAll('#huggingface-tab .tabs .tab');
  hfTabs.forEach(tab => tab.classList.remove('active'));
  
  // Активируем выбранный таб
  hfTabs.forEach(tab => {
    const methodData = tab.getAttribute('data-hf-method');
    if (methodData === method) {
      tab.classList.add('active');
    }
  });
  
  // Показываем/скрываем формы
  const urlForm = document.getElementById('hf-url-form');
  const repoForm = document.getElementById('hf-repo-form');
  
  if (method === 'url') {
    if (urlForm) urlForm.style.display = 'block';
    if (repoForm) repoForm.style.display = 'none';
    console.log('URL form shown');
  } else {
    if (urlForm) urlForm.style.display = 'none';
    if (repoForm) repoForm.style.display = 'block';
    console.log('Repo form shown');
  }
}

// Глобальный объект для хранения выбранных вариантов
let selectedVariants = {}; // {presetId: [variantId1, variantId2, ...]}

function togglePresetCard(presetId, event) {
  // Для пресетов с вариантами - разворачиваем/сворачиваем карточку
  const card = document.querySelector(`[data-preset="${presetId}"]`);
  if (!card) {
    console.error('Card not found for preset:', presetId);
    return;
  }
  
  // Проверяем, был ли клик на варианте или видео-гайде (но не на иконке раскрытия)
  if (event && event.target) {
    const clickedElement = event.target;
    
    // Если клик был на варианте или видео-гайде, не раскрываем/сворачиваем
    if (clickedElement.closest('.preset-variant-item') || 
        clickedElement.closest('.video-guide-icon')) {
      return;
    }
    
    // Если клик был на иконке раскрытия, всегда раскрываем/сворачиваем
    if (clickedElement.closest('.preset-expand-icon')) {
      card.classList.toggle('expanded');
      return;
    }
  }
  
  // Обычный клик на карточке - раскрываем/сворачиваем
  card.classList.toggle('expanded');
}

function togglePreset(presetId) {
  // Для обычных пресетов без вариантов (Wan)
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
  
  updateDownloadButton();
}

function toggleVariant(parentId, variantId) {
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
  
  updateDownloadButton();
}

function updateDownloadButton() {
  // Подсчитываем общее количество выбранных пресетов (обычные + варианты)
  let totalSelected = selectedPresets.length;
  Object.values(selectedVariants).forEach(variants => {
    totalSelected += variants.length;
  });
  
  const btn = document.getElementById('download-presets-btn');
  btn.disabled = totalSelected === 0;
  btn.textContent = totalSelected > 0 ? 
    `📥 Скачать выбранные пресеты (${totalSelected})` : 
    '📥 Скачать выбранные пресеты';
}

function downloadPresets() {
  // Собираем все выбранные пресеты (обычные + варианты)
  let allSelectedPresets = [...selectedPresets];
  Object.values(selectedVariants).forEach(variants => {
    allSelectedPresets.push(...variants);
  });
  
  if (allSelectedPresets.length === 0) {
    alert('Пожалуйста, выберите хотя бы один пресет для скачивания');
    return;
  }
  
  const progress = document.getElementById('preset-progress');
  const result = document.getElementById('preset-result');
  const btn = document.getElementById('download-presets-btn');
  const lightningCheckbox = document.getElementById('lightning-lora-checkbox');
  
  // Показываем прогресс
  progress.style.display = 'block';
  result.textContent = '';
  btn.disabled = true;
  btn.textContent = 'Загрузка...';
  
  // Отправляем запрос
  const formData = new FormData();
  formData.append('presets', allSelectedPresets.join(','));
  formData.append('lightning_lora', lightningCheckbox.checked ? 'true' : 'false');
  
  fetch('/download_presets', {
    method: 'POST',
    body: formData
  })
  .then(response => response.json())
  .then(data => {
    if (data.task_id) {
      const lightningStatus = lightningCheckbox.checked ? ' (включая Lightning LoRA)' : '';
      result.textContent = data.message + lightningStatus;
      // Начинаем опрос статуса
      pollStatus(data.task_id);
    } else {
      result.textContent = data.message;
      progress.style.display = 'none';
      btn.disabled = false;
      btn.textContent = '📥 Скачать выбранные пресеты';
    }
  })
  .catch(error => {
    result.textContent = '❌ Ошибка: ' + error.message;
    progress.style.display = 'none';
    btn.disabled = false;
    btn.textContent = '📥 Скачать выбранные пресеты';
  });
}

function pollStatus(taskId) {
  const progress = document.getElementById('preset-progress');
  const progressFill = document.getElementById('preset-progress-fill');
  const progressText = document.getElementById('preset-progress-text');
  const result = document.getElementById('preset-result');
  const btn = document.getElementById('download-presets-btn');
  
  fetch(`/status/${taskId}`)
  .then(response => response.json())
  .then(data => {
    if (data.status === 'completed' || data.status === 'error') {
      let message = data.message;
      const lightningCheckbox = document.getElementById('lightning-lora-checkbox');
      if (lightningCheckbox && lightningCheckbox.checked && data.status === 'completed') {
        message += '\n⚡ Lightning LoRA также скачаны (экспериментальные версии)';
      }
      result.textContent = message;
      progress.style.display = 'none';
      btn.disabled = false;
      btn.textContent = '📥 Скачать выбранные пресеты';
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
      progress.style.display = 'none';
      btn.disabled = false;
      btn.textContent = '📥 Скачать выбранные пресеты';
    }
  })
  .catch(error => {
    result.textContent = '❌ Ошибка проверки статуса: ' + error.message;
    progress.style.display = 'none';
    btn.disabled = false;
    btn.textContent = '📥 Скачать выбранные пресеты';
  });
}

// Остальные функции для HuggingFace...

// Фильтрация по категориям и поиск
let currentCategory = 'all';
let searchQuery = '';

function filterByCategory(category) {
  currentCategory = category;
  
  // Обновляем активный фильтр
  document.querySelectorAll('.category-filter').forEach(filter => {
    filter.classList.remove('active');
  });
  event.target.closest('.category-filter').classList.add('active');
  
  // Применяем фильтры
  applyFilters();
}

function filterPresets() {
  searchQuery = document.getElementById('preset-search').value.toLowerCase().trim();
  applyFilters();
}

function applyFilters() {
  const cards = document.querySelectorAll('.preset-card');
  let visibleCount = 0;
  
  cards.forEach(card => {
    const presetCategory = card.getAttribute('data-category');
    const presetName = card.querySelector('.preset-name').textContent.toLowerCase();
    const presetDesc = card.querySelector('.preset-desc').textContent.toLowerCase();
    const presetInfo = card.querySelector('.preset-info').textContent.toLowerCase();
    
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

// Инициализация
function initAllHandlers() {
  console.log('Initializing all handlers...');
  
  // Привязываем обработчики для переключения табов
  const mainTabs = document.querySelectorAll('.tabs:first-of-type .tab');
  console.log('Found main tabs:', mainTabs.length);
  mainTabs.forEach(tab => {
    tab.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      const tabName = this.getAttribute('data-tab');
      console.log('Main tab clicked:', tabName);
      if (tabName && typeof switchTab === 'function') {
        switchTab(tabName);
      } else {
        console.error('switchTab is not a function or tabName is missing');
      }
    });
    // Добавляем курсор для визуальной обратной связи
    tab.style.cursor = 'pointer';
  });
  
  // Привязываем обработчики для переключения методов HuggingFace
  const hfTabs = document.querySelectorAll('#huggingface-tab .tabs .tab');
  console.log('Found HF tabs:', hfTabs.length);
  hfTabs.forEach(tab => {
    tab.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      const method = this.getAttribute('data-hf-method');
      console.log('HF tab clicked:', method);
      if (method && typeof switchHFMethod === 'function') {
        switchHFMethod(method);
      } else {
        console.error('switchHFMethod is not a function or method is missing');
      }
    });
    // Добавляем курсор для визуальной обратной связи
    tab.style.cursor = 'pointer';
  });
  
  // Привязываем обработчики для карточек пресетов
  const presetCards = document.querySelectorAll('.preset-card');
  console.log('Found preset cards:', presetCards.length);
  presetCards.forEach(card => {
    const presetId = card.getAttribute('data-preset');
    const hasVariants = card.getAttribute('data-has-variants') === 'true';
    
    // Обработчик клика на карточке
    card.addEventListener('click', function(e) {
      // Пропускаем клики на вариантах, видео-гайде и иконке раскрытия
      if (e.target.closest('.preset-variant-item') || 
          e.target.closest('.video-guide-icon') ||
          e.target.closest('.preset-expand-icon')) {
        return;
      }
      
      if (hasVariants) {
        // Для пресетов с вариантами - раскрываем/сворачиваем
        if (typeof togglePresetCard === 'function') {
          togglePresetCard(presetId, e);
        }
      } else {
        // Для обычных пресетов - выбираем/снимаем выбор
        if (typeof togglePreset === 'function') {
          togglePreset(presetId);
        }
      }
    });
    
    // Обработчик клика на иконке раскрытия
    const expandIcon = card.querySelector('.preset-expand-icon');
    if (expandIcon && hasVariants) {
      expandIcon.addEventListener('click', function(e) {
        e.stopPropagation();
        if (typeof togglePresetCard === 'function') {
          togglePresetCard(presetId, e);
        }
      });
      expandIcon.style.cursor = 'pointer';
    }
    
    card.style.cursor = 'pointer';
  });
  
  // Привязываем обработчики для чекбоксов вариантов
  const variantCheckboxes = document.querySelectorAll('input[type="checkbox"][data-variant]');
  console.log('Found variant checkboxes:', variantCheckboxes.length);
  variantCheckboxes.forEach(checkbox => {
    checkbox.addEventListener('change', function(e) {
      e.stopPropagation();
      const variantId = this.getAttribute('data-variant');
      const parentId = this.getAttribute('data-parent');
      if (variantId && parentId && typeof toggleVariant === 'function') {
        toggleVariant(parentId, variantId);
      }
    });
  });
  
  // Инициализируем состояние Lightning LoRA при загрузке страницы
  if (typeof updateLightningLoraInfo === 'function') {
    updateLightningLoraInfo();
  }
  
  // Инициализируем фильтры
  if (typeof applyFilters === 'function') {
    applyFilters();
  }
  
  console.log('All handlers initialized');
}

// Запускаем инициализацию
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initAllHandlers);
} else {
  // DOM уже загружен, запускаем сразу
  initAllHandlers();
}
