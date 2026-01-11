console.log('JavaScript loaded');
let selectedPresets = [];
let selectedVariants = {}; // {presetId: [variantId1, variantId2, ...]}
console.log('selectedPresets initialized:', selectedPresets);

function switchTab(tabName) {
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

function switchHFMethod(method) {
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

// Глобальный объект для хранения выбранных вариантов
let selectedVariants = {}; // {presetId: [variantId1, variantId2, ...]}

function togglePresetCard(presetId, event) {
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

function togglePreset(presetId) {
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
  
  // Показываем прогресс
  progress.style.display = 'block';
  result.textContent = '';
  btn.disabled = true;
  btn.textContent = 'Загрузка...';
  
  // Отправляем запрос
  const formData = new FormData();
  formData.append('presets', allSelectedPresets.join(','));
  
  fetch('/download_presets', {
    method: 'POST',
    body: formData
  })
  .then(response => response.json())
  .then(data => {
    if (data.task_id) {
      result.textContent = data.message;
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
      result.textContent = data.message;
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

function filterByCategory(category, event) {
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
// Инициализация
document.addEventListener('DOMContentLoaded', function() {
  // Инициализируем фильтры
  if (typeof applyFilters === 'function') {
    applyFilters();
  }
});
