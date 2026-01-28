/**
 * Компонент выбора директории с оптимизированной производительностью
 */
class DirectoryPicker {
    constructor(options = {}) {
        // Конфигурация компонента
        this.config = {
            apiEndpoint: '/api/directories',
            debounceDelay: options.debounceDelay || 300,
            maxVisibleItems: options.maxVisibleItems || 50,
            enableVirtualScroll: options.enableVirtualScroll !== false,
            enableRecentPaths: options.enableRecentPaths !== false,
            maxRecentPaths: options.maxRecentPaths || 5,
            rootPath: options.rootPath || '/',
            ...options
        };

        // Состояние компонента
        this.state = {
            activeInput: null,
            currentPath: this.config.rootPath,
            selectedPath: this.config.rootPath,
            isInputFocused: false,
            isLoading: false,
            recentPaths: this.loadRecentPaths(),
            directoryCache: new Map(),
            debounceTimer: null,
            virtualScrollIndex: 0
        };

        // Элементы DOM
        this.elements = {};
        
        // Инициализация компонента
        this.init();
    }

    /**
     * Инициализация компонента
     */
    init() {
        this.createFileBrowser();
        this.attachEventListeners();
    }

    /**
     * Создание файлового браузера
     */
    createFileBrowser() {
        // Проверяем, существует ли уже файловый браузер
        if (document.getElementById('fileBrowser')) {
            this.elements.browser = document.getElementById('fileBrowser');
            this.elements.content = document.getElementById('fileBrowserContent');
            this.elements.currentPath = document.getElementById('currentPath');
            this.elements.cancelBtn = document.getElementById('cancelBtn');
            this.elements.selectBtn = document.getElementById('selectBtn');
            return;
        }

        // Создаем файловый браузер, если его нет
        const browser = document.createElement('div');
        browser.className = 'file-browser';
        browser.id = 'fileBrowser';
        browser.innerHTML = `
            <div class="file-browser-header">
                Выберите директорию
                <div class="file-browser-actions">
                    <button class="file-browser-recent-btn" title="Недавние пути">
                        ⏱
                    </button>
                </div>
            </div>
            <div class="file-browser-status" id="fileBrowserStatus"></div>
            <div class="file-browser-content" id="fileBrowserContent">
                <!-- Директории будут загружены динамически -->
            </div>
            <div class="file-browser-footer">
                <div class="current-path" id="currentPath">${this.config.rootPath}</div>
                <div>
                    <button id="cancelBtn">Отмена</button>
                    <button id="selectBtn" class="select">Выбрать</button>
                </div>
            </div>
        `;

        // Добавляем недостающие стили для новых элементов
        this.addAdditionalStyles();

        document.body.appendChild(browser);

        // Сохраняем ссылки на элементы
        this.elements.browser = browser;
        this.elements.content = document.getElementById('fileBrowserContent');
        this.elements.currentPath = document.getElementById('currentPath');
        this.elements.status = document.getElementById('fileBrowserStatus');
        this.elements.cancelBtn = document.getElementById('cancelBtn');
        this.elements.selectBtn = document.getElementById('selectBtn');
        this.elements.recentBtn = browser.querySelector('.file-browser-recent-btn');
    }

    /**
     * Добавление дополнительных стилей
     */
    addAdditionalStyles() {
        if (document.getElementById('directory-picker-styles')) return;

        const style = document.createElement('style');
        style.id = 'directory-picker-styles';
        style.textContent = `
            .file-browser-actions {
                position: absolute;
                right: 10px;
                top: 50%;
                transform: translateY(-50%);
            }
            
            .file-browser-recent-btn {
                background: none;
                border: none;
                cursor: pointer;
                font-size: 14px;
                opacity: 0.7;
                transition: opacity 0.2s;
            }
            
            .file-browser-recent-btn:hover {
                opacity: 1;
            }
            
            .file-browser-status {
                padding: 8px 12px;
                font-size: 0.875rem;
                color: #666;
                background-color: #f8f9fa;
                border-bottom: 1px solid #eee;
                display: none;
            }
            
            .file-browser-status.loading {
                display: block;
                color: #007bff;
            }
            
            .file-browser-status.error {
                display: block;
                color: #dc3545;
            }
            
            .file-browser-recent-paths {
                position: absolute;
                top: 100%;
                right: 0;
                background: white;
                border: 1px solid #ccc;
                border-radius: 4px;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                z-index: 1001;
                min-width: 200px;
                display: none;
            }
            
            .file-browser-recent-paths.open {
                display: block;
            }
            
            .file-browser-recent-path {
                padding: 8px 12px;
                cursor: pointer;
                border-bottom: 1px solid #eee;
                font-size: 0.875rem;
            }
            
            .file-browser-recent-path:hover {
                background-color: #f8f9fa;
            }
            
            .file-browser-recent-path:last-child {
                border-bottom: none;
            }
            
            .file-browser-virtual-scroll {
                height: 200px;
                overflow-y: auto;
                position: relative;
            }
            
            .file-browser-virtual-content {
                position: relative;
            }
            
            .file-browser-item {
                position: absolute;
                width: 100%;
                box-sizing: border-box;
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * Привязка обработчиков событий
     */
    attachEventListeners() {
        // Обработчики для кнопок
        this.elements.cancelBtn.addEventListener('click', () => this.closeFileBrowser());
        this.elements.selectBtn.addEventListener('click', () => this.confirmSelection());
        
        // Обработчик для кнопки недавних путей
        if (this.elements.recentBtn) {
            this.elements.recentBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleRecentPaths();
            });
        }

        // Обработчик клика вне браузера
        document.addEventListener('click', (e) => this.handleClickOutside(e));

        // Обработчик для полей ввода
        this.attachInputListeners();
    }

    /**
     * Привязка обработчиков для полей ввода
     */
    attachInputListeners() {
        const inputs = document.querySelectorAll('input[data-directory-picker]');
        
        inputs.forEach(input => {
            input.addEventListener('click', (e) => this.openFileBrowser(e));
            
            // Дебаунсинг при вводе текста
            input.addEventListener('input', (e) => this.handleInputWithDebounce(e));
            
            input.addEventListener('focus', () => {
                this.state.isInputFocused = true;
            });
            
            input.addEventListener('blur', () => {
                this.state.isInputFocused = false;
            });
        });
    }

    /**
     * Обработка ввода с дебаунсингом
     */
    handleInputWithDebounce(event) {
        const browser = this.elements.browser;
        if (!browser.classList.contains('open')) return;

        // Очищаем предыдущий таймер
        if (this.state.debounceTimer) {
            clearTimeout(this.state.debounceTimer);
        }

        // Устанавливаем новый таймер
        this.state.debounceTimer = setTimeout(() => {
            this.handleInputChange(event);
        }, this.config.debounceDelay);
    }

    /**
     * Обработка изменения ввода
     */
    handleInputChange(event) {
        let inputValue = event.target.value;
        
        if (inputValue && inputValue.startsWith('/')) {
            if (!inputValue.endsWith('/')) {
                inputValue = inputValue + '/';
            }
            
            this.state.selectedPath = inputValue;
            
            if (inputValue.endsWith('/') || inputValue.indexOf('/') === inputValue.lastIndexOf('/')) {
                this.loadDirectories(inputValue);
            }
        }
    }

    /**
     * Открытие файлового браузера
     */
    openFileBrowser(event) {
        this.state.activeInput = event.target;
        const browser = this.elements.browser;
        const triggerRect = event.target.getBoundingClientRect();
        
        // Получаем текущее значение из поля ввода
        let inputValue = event.target.value || this.config.rootPath;
        
        // Нормализуем путь
        if (!inputValue.startsWith('/')) {
            inputValue = this.config.rootPath;
        }
        if (!inputValue.endsWith('/')) {
            inputValue = inputValue + '/';
        }
        
        // Устанавливаем текущий путь
        this.state.currentPath = inputValue;
        this.state.selectedPath = this.state.currentPath;
        
        // Позиционируем браузер под полем ввода
        browser.style.top = `${triggerRect.bottom + window.scrollY}px`;
        browser.style.left = `${triggerRect.left + window.scrollX}px`;
        browser.style.width = `${triggerRect.width}px`;
        
        // Показываем браузер
        browser.classList.add('open');
        
        // Загружаем директории
        this.loadDirectories(this.state.currentPath);
    }

    /**
     * Загрузка директорий с кэшированием
     */
    async loadDirectories(path) {
        // Проверяем кэш
        if (this.state.directoryCache.has(path)) {
            this.renderDirectories(this.state.directoryCache.get(path), path);
            return;
        }

        // Показываем индикатор загрузки
        this.showLoading(true);

        try {
            // Нормализуем путь для запроса
            let requestPath = path.endsWith('/') ? path.slice(0, -1) : path;
            
            // Обрабатываем случай автодополнения
            if (!path.endsWith('/')) {
                const result = await this.handlePartialPath(path);
                if (result) {
                    this.showLoading(false);
                    return;
                }
            }
            
            // Запрос к API
            const response = await fetch(`${this.config.apiEndpoint}?path=${encodeURIComponent(requestPath)}`);
            
            if (!response.ok) {
                // Пробуем обработать случай с частичным путем
                const result = await this.handlePartialPath(path);
                if (result) {
                    this.showLoading(false);
                    return;
                }
                throw new Error('Ошибка при загрузке директорий');
            }
            
            const data = await response.json();
            
            // Проверяем наличие ошибки
            if (data.error) {
                this.showError(data.error);
                return;
            }
            
            // Сохраняем в кэш
            this.state.directoryCache.set(path, data);
            
            // Отображаем директории
            this.renderDirectories(data, path);
            
        } catch (error) {
            this.showError(`Ошибка: ${error.message}`);
        } finally {
            this.showLoading(false);
        }
    }

    /**
     * Обработка частичного пути для автодополнения
     */
    async handlePartialPath(path) {
        const lastSlash = path.lastIndexOf('/');
        if (lastSlash > 0) {
            const parentPath = path.substring(0, lastSlash);
            const partialName = path.substring(lastSlash + 1);
            
            try {
                const response = await fetch(`${this.config.apiEndpoint}?path=${encodeURIComponent(parentPath)}`);
                
                if (response.ok) {
                    const data = await response.json();
                    if (!data.error && data.items) {
                        // Фильтруем директории по частичному совпадению
                        const filteredDirs = data.items.filter(dir =>
                            dir.name.toLowerCase().startsWith(partialName.toLowerCase())
                        );
                        
                        if (filteredDirs.length > 0) {
                            this.renderFilteredDirectories(filteredDirs, parentPath, partialName);
                            return true;
                        }
                    }
                }
            } catch (error) {
                console.error('Ошибка при обработке частичного пути:', error);
            }
        }
        return false;
    }

    /**
     * Отображение отфильтрованных директорий
     */
    renderFilteredDirectories(directories, parentPath, partialName) {
        const content = this.elements.content;
        content.innerHTML = '';
        
        // Добавляем кнопку "Назад"
        if (parentPath !== this.config.rootPath) {
            this.addBackButton(parentPath);
        }
        
        // Добавляем отфильтрованные директории
        directories.forEach(dir => {
            this.addDirectoryItem(dir.name, dir.path);
        });
        
        // Обновляем текущий путь
        this.elements.currentPath.textContent = parentPath;
    }

    /**
     * Оптимизированное отображение директорий
     */
    renderDirectories(data, path) {
        const content = this.elements.content;
        
        // Очищаем контент
        content.innerHTML = '';
        
        // Добавляем кнопку "Назад" если не в корневом каталоге
        if (path !== this.config.rootPath) {
            this.addBackButton(path);
        }
        
        // Определяем способ отображения в зависимости от количества элементов
        if (this.config.enableVirtualScroll && data.items.length > this.config.maxVisibleItems) {
            this.renderWithVirtualScroll(data.items);
        } else {
            // Простое отображение для небольших списков
            data.items.forEach(dir => {
                this.addDirectoryItem(dir.name, dir.path);
            });
        }
        
        // Обновляем текущий путь
        this.elements.currentPath.textContent = path;
    }

    /**
     * Добавление кнопки "Назад"
     */
    addBackButton(currentPath) {
        const backItem = document.createElement('div');
        backItem.className = 'file-browser-item';
        backItem.textContent = '..';
        backItem.addEventListener('click', (e) => {
            e.stopPropagation();
            this.navigateBack();
        });
        this.elements.content.appendChild(backItem);
    }

    /**
     * Добавление элемента директории
     */
    addDirectoryItem(name, path) {
        const item = document.createElement('div');
        item.className = 'file-browser-item';
        item.textContent = name;
        item.addEventListener('click', (e) => {
            e.stopPropagation();
            this.navigateToDirectory(path);
        });
        this.elements.content.appendChild(item);
    }

    /**
     * Виртуальный скроллинг для больших списков
     */
    renderWithVirtualScroll(items) {
        const content = this.elements.content;
        content.className = 'file-browser-virtual-scroll';
        
        const virtualContent = document.createElement('div');
        virtualContent.className = 'file-browser-virtual-content';
        virtualContent.style.height = `${items.length * 30}px`;
        
        content.appendChild(virtualContent);
        
        // Отображаем только видимые элементы
        this.updateVirtualScroll(items, virtualContent);
        
        // Обработчик скроллинга
        content.addEventListener('scroll', () => {
            this.updateVirtualScroll(items, virtualContent);
        });
    }

    /**
     * Обновление виртуального скроллинга
     */
    updateVirtualScroll(items, container) {
        const content = this.elements.content;
        const scrollTop = content.scrollTop;
        const itemHeight = 30;
        const visibleCount = Math.ceil(content.clientHeight / itemHeight);
        const startIndex = Math.floor(scrollTop / itemHeight);
        const endIndex = Math.min(startIndex + visibleCount, items.length);
        
        // Очищаем контейнер
        container.innerHTML = '';
        
        // Добавляем только видимые элементы
        for (let i = startIndex; i < endIndex; i++) {
            const item = items[i];
            const element = document.createElement('div');
            element.className = 'file-browser-item';
            element.textContent = item.name;
            element.style.top = `${i * itemHeight}px`;
            element.style.height = `${itemHeight}px`;
            element.addEventListener('click', (e) => {
                e.stopPropagation();
                this.navigateToDirectory(item.path);
            });
            container.appendChild(element);
        }
    }

    /**
     * Навигация в директорию
     */
    async navigateToDirectory(path) {
        const pathWithSlash = path.endsWith('/') ? path : path + '/';
        this.state.currentPath = pathWithSlash;
        this.state.selectedPath = pathWithSlash;
        
        // Обновляем поле ввода
        if (this.state.activeInput) {
            this.state.activeInput.value = pathWithSlash;
        }
        
        // Проверяем, является ли директория конечной
        try {
            const response = await fetch(`${this.config.apiEndpoint}?path=${encodeURIComponent(path)}`);
            if (response.ok) {
                const data = await response.json();
                if (!data.error && data.items && data.items.length === 0) {
                    // Если директория пустая, выбираем её
                    this.saveToRecentPaths(pathWithSlash);
                    this.closeFileBrowser();
                    return;
                }
            }
        } catch (error) {
            console.error('Ошибка проверки директории:', error);
        }
        
        await this.loadDirectories(pathWithSlash);
    }

    /**
     * Навигация назад
     */
    async navigateBack() {
        const pathWithoutSlash = this.state.currentPath.endsWith('/') ? 
            this.state.currentPath.slice(0, -1) : this.state.currentPath;
        const parentPath = pathWithoutSlash.substring(0, pathWithoutSlash.lastIndexOf('/'));
        
        if (parentPath) {
            const parentPathWithSlash = parentPath.endsWith('/') ? parentPath : parentPath + '/';
            this.state.currentPath = parentPathWithSlash;
            this.state.selectedPath = parentPathWithSlash;
            
            // Обновляем поле ввода
            if (this.state.activeInput) {
                this.state.activeInput.value = parentPathWithSlash;
            }
            
            await this.loadDirectories(parentPathWithSlash);
        }
    }

    /**
     * Показать индикатор загрузки
     */
    showLoading(show) {
        this.state.isLoading = show;
        const status = this.elements.status;
        
        if (show) {
            status.textContent = 'Загрузка...';
            status.className = 'file-browser-status loading';
        } else {
            status.className = 'file-browser-status';
        }
    }

    /**
     * Показать ошибку
     */
    showError(message) {
        const status = this.elements.status;
        status.textContent = message;
        status.className = 'file-browser-status error';
        
        // Автоматически скрываем ошибку через 3 секунды
        setTimeout(() => {
            status.className = 'file-browser-status';
        }, 3000);
    }

    /**
     * Закрытие файлового браузера
     */
    closeFileBrowser() {
        this.elements.browser.classList.remove('open');
        this.hideRecentPaths();
    }

    /**
     * Подтверждение выбора
     */
    confirmSelection() {
        if (this.state.activeInput) {
            this.state.activeInput.value = this.state.selectedPath;
            this.saveToRecentPaths(this.state.selectedPath);
        }
        this.closeFileBrowser();
    }

    /**
     * Обработка клика вне браузера
     */
    handleClickOutside(event) {
        const browser = this.elements.browser;
        const recentPaths = document.querySelector('.file-browser-recent-paths');
        
        if (browser.classList.contains('open') &&
            !browser.contains(event.target) &&
            (!this.state.activeInput || !this.state.activeInput.contains(event.target)) &&
            (!recentPaths || !recentPaths.contains(event.target))) {
            this.closeFileBrowser();
        }
    }

    /**
     * Работа с недавними путями
     */
    loadRecentPaths() {
        if (!this.config.enableRecentPaths) return [];
        
        try {
            const stored = localStorage.getItem('directoryPickerRecentPaths');
            return stored ? JSON.parse(stored) : [];
        } catch (error) {
            console.error('Ошибка загрузки недавних путей:', error);
            return [];
        }
    }

    saveToRecentPaths(path) {
        if (!this.config.enableRecentPaths) return;
        
        try {
            const recentPaths = this.state.recentPaths.filter(p => p !== path);
            recentPaths.unshift(path);
            
            // Ограничиваем количество сохраняемых путей
            const limitedPaths = recentPaths.slice(0, this.config.maxRecentPaths);
            
            this.state.recentPaths = limitedPaths;
            localStorage.setItem('directoryPickerRecentPaths', JSON.stringify(limitedPaths));
        } catch (error) {
            console.error('Ошибка сохранения недавних путей:', error);
        }
    }

    toggleRecentPaths() {
        const existing = document.querySelector('.file-browser-recent-paths');
        
        if (existing) {
            this.hideRecentPaths();
        } else {
            this.showRecentPaths();
        }
    }

    showRecentPaths() {
        if (this.state.recentPaths.length === 0) return;
        
        const container = document.createElement('div');
        container.className = 'file-browser-recent-paths';
        
        this.state.recentPaths.forEach(path => {
            const item = document.createElement('div');
            item.className = 'file-browser-recent-path';
            item.textContent = path;
            item.addEventListener('click', () => {
                this.navigateToDirectory(path);
                this.hideRecentPaths();
            });
            container.appendChild(item);
        });
        
        this.elements.browser.appendChild(container);
        
        // Позиционируем контейнер
        const rect = this.elements.recentBtn.getBoundingClientRect();
        container.style.top = `${rect.bottom}px`;
        container.style.right = '0';
        
        setTimeout(() => {
            container.classList.add('open');
        }, 10);
    }

    hideRecentPaths() {
        const container = document.querySelector('.file-browser-recent-paths');
        if (container) {
            container.remove();
        }
    }

    /**
     * Публичные методы для интеграции
     */
    destroy() {
        // Удаляем обработчики событий
        document.removeEventListener('click', this.handleClickOutside);
        
        // Очищаем таймеры
        if (this.state.debounceTimer) {
            clearTimeout(this.state.debounceTimer);
        }
        
        // Удаляем DOM элементы
        if (this.elements.browser) {
            this.elements.browser.remove();
        }
    }

    // Метод для обновления конфигурации
    updateConfig(newConfig) {
        this.config = { ...this.config, ...newConfig };
    }

    // Метод для программного открытия
    open(inputElement) {
        if (inputElement) {
            this.openFileBrowser({ target: inputElement });
        }
    }

    // Метод для программного закрытия
    close() {
        this.closeFileBrowser();
    }
}

// Глобальная функция для инициализации компонента
window.DirectoryPicker = DirectoryPicker;

// Автоматическая инициализация для элементов с атрибутом data-directory-picker
document.addEventListener('DOMContentLoaded', () => {
    const inputs = document.querySelectorAll('input[data-directory-picker]');
    if (inputs.length > 0) {
        window.directoryPicker = new DirectoryPicker();
    }
});