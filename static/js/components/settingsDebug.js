const SettingsDebugTab = {
  template: `
    <div class="settings-tab-content">
        <div class="modern-fieldset mb-4">
            <div class="fieldset-header">
                <i class="bi bi-robot me-2"></i>
                <h6 class="fieldset-title mb-0">Агент сканирования</h6>
            </div>
            <div class="fieldset-content">
                <div class="row mb-3">
                    <div class="col-md-6">
                        <div class="modern-form-check form-switch" title="Если включено, агент будет периодически запускать сканирование для всех отмеченных сериалов.">
                            <input class="form-check-input" type="checkbox" role="switch" id="scannerAgentSwitch" v-model="scannerStatus.scanner_enabled" @change="saveScannerSettings">
                            <label class="modern-form-check-label" for="scannerAgentSwitch">Автосканирование</label>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="modern-form-check form-switch" title="Если включено, сканер будет считать все существующие торренты устаревшими и пытаться их заменить. Учитывается при любом сканировании.">
                            <input class="form-check-input" type="checkbox" role="switch" id="forceReplaceSwitch" v-model="debugForceReplace" @change="saveForceReplaceSetting">
                            <label class="modern-form-check-label" for="forceReplaceSwitch">Всегда заменять торренты</label>
                        </div>
                    </div>
                </div>
                <hr>
                <div class="modern-input-group">
                    <span class="input-group-text">Интервал (мин)</span>
                    <input type="number" id="scanIntervalInput" v-model.number="scannerStatus.scan_interval" class="modern-input" min="1" @change="saveScannerSettings" style="flex: 0 1 120px;">
                    
                    <div class="alert alert-info py-2 px-3 m-0 d-flex align-items-center" role="alert" style="flex: 1 1 auto; border-radius: 0; border-top-width: 0; border-bottom-width: 0; min-width: 200px;">
                        <div v-if="scannerStatus.is_scanning" class="w-100">
                            <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                            <strong>Сканирование...</strong>
                        </div>
                        <div v-else-if="scannerStatus.is_awaiting_tasks" class="w-100">
                            <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                            <strong>Завершение задач...</strong>
                        </div>
                        <div v-else-if="scannerStatus.scanner_enabled" class="w-100">
                            <i class="bi bi-clock me-2"></i>
                            Следующий запуск ~ <strong>{{ nextScanCountdown }}</strong>
                        </div>
                        <div v-else class="w-100">
                            <i class="bi bi-pause-circle me-2"></i>
                            Авто-сканирование выключено.
                        </div>
                    </div>

                    <button class="modern-btn btn-primary" @click="scanAllNow" :disabled="scannerStatus.is_scanning || scannerStatus.is_awaiting_tasks" style="border-radius: 0 6px 6px 0;"><i class="bi bi-fast-forward-fill me-2"></i>Сканировать всё</button>
                </div>
            </div>
        </div>
        
        <div class="modern-fieldset mb-4">
            <div class="fieldset-header">
                <i class="bi bi-toggles2 me-2"></i>
                <h6 class="fieldset-title mb-0">Отладка модулей (DEBUG)</h6>
            </div>
            <div class="fieldset-content">
                <div class="row mb-3">
                    <div class="col-md-6">
                        <div class="modern-form-check form-switch" title="Сохранять полученный от парсеров HTML-код в папку parser_dumps для анализа.">
                            <input class="form-check-input" type="checkbox" role="switch" id="saveHtmlSwitch" v-model="debugSaveHtml" @change="saveSaveHtmlSetting">
                            <label class="modern-form-check-label" for="saveHtmlSwitch">Сохранять HTML от парсеров</label>
                        </div>
                    </div>
                </div>
                <div v-if="Object.keys(debugFlags).length === 0" class="text-center text-muted p-3">
                    Загрузка флагов отладки...
                </div>
                <div class="row">
                    <div v-for="(enabled, module) in debugFlags" :key="module" class="col-md-4">
                        <div class="modern-form-check form-switch mb-2">
                            <input class="form-check-input" type="checkbox" role="switch" :id="'debugSwitch_' + module" v-model="debugFlags[module]" @change="saveDebugFlag(module)">
                            <label class="modern-form-check-label" :for="'debugSwitch_' + module">{{ module.charAt(0).toUpperCase() + module.slice(1).replace('_', ' ') }}</label>
                        </div>
                    </div>
                </div>
                 <small class="form-text text-muted d-block mt-2">
                    Включает подробное логирование для конкретного модуля. Изменения применяются мгновенно.
                </small>
            </div>
        </div>

        <div class="modern-fieldset mb-4">
            <div class="fieldset-header">
                <i class="bi bi-bug me-2"></i>
                <h6 class="fieldset-title mb-0">Действия отладки</h6>
            </div>
            <div class="fieldset-content">
                <div class="d-flex align-items-center gap-3">
                    <button class="modern-btn btn-warning flex-shrink-0" @click="resetAgentState"><i class="bi bi-arrow-counterclockwise me-2"></i>Сбросить статусы и очередь Агента</button>
                    <p class="form-text text-muted mb-0">Эта кнопка очистит очередь агента задач и сбросит статус всех сериалов, которые "зависли" в состоянии сканирования или проверки, на 'waiting'.</p>
                </div>
            </div>
        </div>

        <div class="modern-fieldset mb-4">
            <div class="fieldset-header">
                <h6 class="fieldset-title mb-0">Очистка таблиц БД</h6>
            </div>
            <div class="fieldset-content">
                <p class="text-muted small">Используйте с осторожностью. Это действие необратимо и удалит все данные из выбранной таблицы.</p>
                <div class="modern-input-group">
                    <select class="modern-select" v-model="selectedTableToClear" style="flex: 0.4;">
                        <option disabled value="">Выберите таблицу...</option>
                        <option v-for="table in tables" :key="table" :value="table">{{ table }}</option>
                    </select>
                    <span class="input-group-text" style="flex: 0.6; text-align: left; justify-content: left; white-space: normal;">{{ getTableDescription(selectedTableToClear) }}</span>
                    <button class="modern-btn btn-danger" @click="clearSelectedTable" :disabled="!selectedTableToClear">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </div>
        </div>
    </div>
  `,
  data() {
    return {
      eventSource: null,
      tables: [],
      selectedTableToClear: '',
      scannerStatus: {
          scanner_enabled: false,
          scan_interval: 60,
          is_scanning: false,
          is_awaiting_tasks: false,
          next_scan_time: null,
      },
      debugFlags: {
            'scanner': false,
            'agent': false,
            'monitoring_agent': false,
            'renamer': false,
            'qbittorrent': false,
            'auth': false,
            'kinozal_parser': false,
            'anilibria_parser': false,
            'astar_parser': false,
      },
      debugForceReplace: false,
      debugSaveHtml: false, // --- ИЗМЕНЕНИЕ: Новое свойство ---
      countdownTimer: null,
      nextScanCountdown: '...',
      tableDescriptions: {
        'series': 'Удалить все отслеживаемые сериалы.',
        'torrents': 'Удалить все связанные торренты из базы данных (не из qBittorrent).',
        'advanced_renaming_patterns': 'Сбросить все продвинутые паттерны переименования.',
        'renaming_patterns': 'Сбросить все паттерны переименования эпизодов.',
        'season_patterns': 'Сбросить все паттерны переименования сезонов.',
        'quality_patterns': 'Сбросить все стандарты качества.',
        'quality_search_patterns': 'Удалить все поисковые паттерны для качества.',
        'resolution_patterns': 'Сбросить все стандарты разрешения.',
        'resolution_search_patterns': 'Удалить все поисковые паттерны для разрешения.',
        'settings': 'Удалить все сохраненные настройки, включая SID для qBittorrent и флаги отладки.',
        'logs': 'Очистить все логи приложения.',
        'scan_tasks': 'Очистить "зависшие" задачи сканирования, если они есть.',
        'agent_tasks': 'Очистить "зависшие" задачи агента, если они есть.'
      }
    };
  },
  emits: ['show-toast', 'reload-series'],
  methods: {
    load() {
        this.loadDebugFlags();
        this.loadForceReplaceSetting();
        this.loadSaveHtmlSetting(); // --- ИЗМЕНЕНИЕ: Загрузка нового флага ---
        this.loadTables();
        this.connectEventSourceForScanner();
        this.startCountdownTimer();
    },
    unload() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        if (this.countdownTimer) {
            clearInterval(this.countdownTimer);
            this.countdownTimer = null;
        }
    },
    // --- ИЗМЕНЕНИЕ: Новые методы для управления флагом сохранения HTML ---
    async loadSaveHtmlSetting() {
        try {
            const response = await fetch('/api/settings/debug_flags');
            if (!response.ok) throw new Error('Could not fetch debug flags');
            const flags = await response.json();
            this.debugSaveHtml = flags.save_parser_html || false;
        } catch (error) {
            this.$emit('show-toast', `Ошибка загрузки флага сохранения HTML: ${error.message}`, 'danger');
        }
    },
    async saveSaveHtmlSetting() {
        try {
            await fetch('/api/settings/debug_flags', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ module: 'save_parser_html', enabled: this.debugSaveHtml })
            });
            this.$emit('show-toast', `Сохранение HTML от парсеров ${this.debugSaveHtml ? 'включено' : 'выключено'}`, 'info');
        } catch (error) {
            this.$emit('show-toast', `Ошибка сохранения флага: ${error.message}`, 'danger');
        }
    },
    // --- КОНЕЦ ИЗМЕНЕНИЯ ---
    async loadDebugFlags() {
        try {
            const response = await fetch('/api/settings/debug_flags');
            if (!response.ok) throw new Error('Could not fetch debug flags');
            const flagsFromServer = await response.json();
            for (const moduleName in this.debugFlags) {
                if (moduleName in flagsFromServer) {
                    this.debugFlags[moduleName] = flagsFromServer[moduleName];
                }
            }
        } catch (error) {
            this.$emit('show-toast', `Ошибка загрузки флагов отладки: ${error.message}`, 'danger');
        }
    },
    async saveDebugFlag(moduleName) {
        const enabled = this.debugFlags[moduleName];
        try {
            const response = await fetch('/api/settings/debug_flags', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ module: moduleName, enabled: enabled })
            });
            if (!response.ok) throw new Error('Failed to save flag');
            this.$emit('show-toast', `Отладка для '${moduleName}' ${enabled ? 'включена' : 'выключена'}`, 'info');
        } catch (error) {
            this.$emit('show-toast', `Ошибка сохранения флага: ${error.message}`, 'danger');
            this.debugFlags[moduleName] = !enabled;
        }
    },
    async loadForceReplaceSetting() {
        try {
            const response = await fetch('/api/settings/force_replace');
            if (!response.ok) throw new Error('Could not fetch force replace setting');
            const setting = await response.json();
            this.debugForceReplace = setting.enabled || false;
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        }
    },
    async saveForceReplaceSetting() {
        try {
            await fetch('/api/settings/force_replace', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: this.debugForceReplace })
            });
            this.$emit('show-toast', `Режим принудительной замены ${this.debugForceReplace ? 'включен' : 'выключен'}`, 'info');
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        }
    },
    connectEventSourceForScanner() {
        if (this.eventSource) return;
        
        this.eventSource = new EventSource('/api/stream');
        this.eventSource.onopen = () => console.log("SSE для отладки (сканер) подключен.");
        this.eventSource.onerror = () => console.error("Ошибка SSE для отладки (сканер).");

        this.eventSource.addEventListener('scanner_status_update', (event) => {
            this.scannerStatus = JSON.parse(event.data);
        });
    },
    async resetAgentState() {
        if (!confirm('Вы уверены, что хотите сбросить все активные задачи сканирования и проверки?')) return;
        try {
            const response = await fetch('/api/agent/reset', { method: 'POST' });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Ошибка при сбросе состояния');
            }
            this.$emit('show-toast', data.message || 'Состояние успешно сброшено.', 'success');
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        }
    },
    async loadTables() {
        try {
            const response = await fetch('/api/database/tables');
            if (!response.ok) throw new Error('Ошибка загрузки списка таблиц');
            this.tables = await response.json();
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        }
    },
    async clearSelectedTable() {
        if (this.selectedTableToClear) {
            if (!confirm(`ВНИМАНИЕ! Вы уверены, что хотите удалить ВСЕ записи из таблицы '${this.selectedTableToClear}'? Это действие необратимо.`)) return;
            try {
                const response = await fetch('/api/database/clear_table', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ table_name: this.selectedTableToClear })
                });
                const data = await response.json();
                if (!response.ok || !data.success) {
                    throw new Error(data.error || `Ошибка при очистке таблицы ${this.selectedTableToClear}`);
                }
                this.$emit('show-toast', data.message, 'success');
            } catch (error) {
                this.$emit('show-toast', error.message, 'danger');
            }
        }
    },
    getTableDescription(tableName) {
        if (!tableName) return 'Выберите таблицу для просмотра описания.';
        return this.tableDescriptions[tableName] || `Очистить таблицу '${tableName}'`;
    },
    async saveScannerSettings() {
        try {
            const payload = {
                enabled: this.scannerStatus.scanner_enabled,
                interval: this.scannerStatus.scan_interval
            };
            const response = await fetch('/api/scanner/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!response.ok) throw new Error('Ошибка сохранения настроек сканера');
            this.$emit('show-toast', 'Настройки сканера сохранены.', 'success');
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        }
    },
    async scanAllNow() {
        if (!confirm('Запустить сканирование для всех сериалов, отмеченных для авто-сканирования?')) return;
        try {
            const scanResponse = await fetch('/api/scanner/scan_all', { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ debug_force_replace: this.debugForceReplace })
            });
            const data = await scanResponse.json();
            if (!scanResponse.ok) throw new Error(data.error || 'Ошибка запуска сканирования');
            this.$emit('show-toast', data.message, 'info');
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        }
    },
    startCountdownTimer() {
        if (this.countdownTimer) clearInterval(this.countdownTimer);
        this.countdownTimer = setInterval(() => {
            if (!this.scannerStatus.next_scan_time || this.scannerStatus.is_scanning || !this.scannerStatus.scanner_enabled || this.scannerStatus.is_awaiting_tasks) {
                this.nextScanCountdown = '...';
                return;
            }
            const now = new Date();
            const nextScan = new Date(this.scannerStatus.next_scan_time);
            const diff = Math.max(0, nextScan - now);
            const totalMinutes = Math.floor(diff / 1000 / 60);

            let newCountdownStr = '';
            if (totalMinutes > 1440) {
                const days = Math.floor(totalMinutes / 1440);
                const hours = Math.floor((totalMinutes % 1440) / 60);
                newCountdownStr = `${days} дн. ${hours} ч.`;
            } else if (totalMinutes > 60) {
                const hours = Math.floor(totalMinutes / 60);
                const minutes = totalMinutes % 60;
                newCountdownStr = `${hours} ч. ${minutes} мин.`;
            } else if (totalMinutes > 0){
                newCountdownStr = `${totalMinutes} мин.`;
            } else {
                newCountdownStr = `< 1 мин.`;
            }
            
            if (this.nextScanCountdown !== newCountdownStr) {
                this.nextScanCountdown = newCountdownStr;
            }
        }, 5000);
    }
  },
  beforeUnmount() {
      this.unload();
  }
};