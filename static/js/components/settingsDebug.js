const SettingsDebugTab = {
  components: {
    'database-viewer-modal': DatabaseViewerModal
  },
  template: `
    <div class="settings-tab-content">
        <div class="modern-fieldset mb-4">
            <div class="fieldset-header">
                <i class="bi bi-robot me-2"></i>
                <h6 class="fieldset-title mb-0">Агент сканирования и загрузчики</h6>
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
                
                <div class="row mb-3">
                    <div class="col-md-6">
                        <div class="modern-form-check form-switch" title="Если включено, сканер будет проверять наличие файлов на диске, даже если их нет в БД. Если файл найден, он будет зарегистрирован, а не скачан заново.">
                            <input class="form-check-input" type="checkbox" role="switch" id="lessStrictSwitch" v-model="lessStrictScan" @change="saveLessStrictScanSetting">
                            <label class="modern-form-check-label" for="lessStrictSwitch">Менее строгий режим сканирования</label>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="modern-form-check form-switch" title="Если включено, агент нарезки удалит исходный файл-компиляцию после успешного завершения.">
                            <input class="form-check-input" type="checkbox" role="switch" id="slicingDeleteSwitch" v-model="slicingDeleteSource" @change="saveSlicingDeleteSourceSetting">
                            <label class="modern-form-check-label" for="slicingDeleteSwitch">Удалять исходник после нарезки</label>
                        </div>
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-md-6">
                        <label for="scanIntervalInput" class="modern-label">Интервал сканирования (мин)</label>
                        <input type="number" id="scanIntervalInput" v-model.number="scannerStatus.scan_interval" class="modern-input" min="1" @change="saveScannerSettings">
                    </div>
                    <div class="col-md-6">
                        <label for="parallelDownloadsInput" class="modern-label">Максимум параллельных загрузок (yt-dlp)</label>
                        <input type="number" id="parallelDownloadsInput" v-model.number="parallelDownloads" class="modern-input" min="1" max="10" @change="saveParallelDownloads">
                    </div>
                </div>
                <hr>
                <div class="modern-input-group">
                    <div class="alert alert-info py-2 px-3 m-0 d-flex align-items-center" role="alert" style="flex: 1 1 auto; border-radius: 6px 0 0 6px; border-top-width: 0; border-bottom-width: 0; min-width: 200px;">
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

                    <button class="btn btn-primary" @click="scanAllNow" :disabled="scannerStatus.is_scanning || scannerStatus.is_awaiting_tasks" style="border-radius: 0 6px 6px 0;"><i class="bi bi-fast-forward-fill me-2"></i>Сканировать всё</button>
                </div>
            </div>
        </div>
        
        <div class="modern-fieldset mb-4">
            <div class="fieldset-header">
                <i class="bi bi-bug me-2"></i>
                <h6 class="fieldset-title mb-0">Действия отладки</h6>
            </div>
            <div class="fieldset-content">
                <div class="d-flex flex-column gap-3">
                    <div class="d-flex align-items-center gap-3">
                        <button class="btn btn-warning flex-shrink-0" @click="resetAgentState"><i class="bi bi-arrow-counterclockwise me-2"></i>Сбросить агент торрентов</button>
                        <p class="form-text text-muted mb-0">Очищает очередь агента обработки торрентов и сбрасывает "зависшие" статусы сериалов.</p>
                    </div>
                    <div class="d-flex align-items-center gap-3">
                        <button class="btn btn-danger flex-shrink-0" @click="clearDownloadQueue"><i class="bi bi-x-circle me-2"></i>Очистить очередь загрузок</button>
                        <p class="form-text text-muted mb-0">Удаляет все ожидающие и ошибочные задачи из очереди загрузчика VK видео.</p>
                    </div>
                    <div class="d-flex align-items-center gap-3">
                        <button class="btn btn-info flex-shrink-0" @click="openDbViewer">
                            <i class="bi bi-database me-2"></i>Просмотр БД
                        </button>
                        <p class="form-text text-muted mb-0">Открывает полноэкранное окно для просмотра всех таблиц базы данных.</p>
                    </div>
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
                    <button class="btn btn-danger" @click="clearSelectedTable" :disabled="!selectedTableToClear">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </div>
        </div>

        <database-viewer-modal ref="dbViewer"></database-viewer-modal>
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
      parallelDownloads: 2,
      debugForceReplace: false,
      debugSaveHtml: false,
      lessStrictScan: false,
      slicingDeleteSource: false,
      countdownTimer: null,
      nextScanCountdown: '...',
      tableDescriptions: {
        'series': 'Удалить все отслеживаемые сериалы.',
        'torrents': 'Удалить все связанные торренты из базы данных (не из qBittorrent).',
        'media_items': 'Удалить все найденные медиа-элементы (для VK-сериалов).',
        'download_tasks': 'Очистить текущую очередь загрузок для VK-видео.',
        'slicing_tasks': 'Очистить очередь задач на нарезку видео.',
        'sliced_files': 'Удалить все записи о нарезанных файлах.',
        'advanced_renaming_patterns': 'Сбросить все продвинутые паттерны переименования.',
        'renaming_patterns': 'Сбросить все паттерны переименования эпизодов.',
        'season_patterns': 'Сбросить все паттерны переименования сезонов.',
        'settings': 'Удалить все сохраненные настройки, включая SID и флаги отладки.',
      }
    };
  },
  emits: ['show-toast', 'reload-series'],
  methods: {
    openDbViewer() {
        this.$refs.dbViewer.open();
    },
    load() {
        this.loadForceReplaceSetting();
        this.loadSaveHtmlSetting();
        this.loadLessStrictScanSetting();
        this.loadSlicingDeleteSourceSetting();
        this.loadTables();
        this.connectEventSourceForScanner();
        this.startCountdownTimer();
        this.loadParallelDownloads();
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
    async clearDownloadQueue() {
        if (!confirm('Вы уверены, что хотите очистить очередь загрузок? Это действие не остановит уже идущие процессы.')) return;
        try {
            const response = await fetch('/api/downloads/queue/clear', { method: 'POST' });
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Ошибка при очистке очереди');
            }
            this.$emit('show-toast', data.message || 'Очередь загрузок очищена.', 'success');
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        }
    },
    async loadParallelDownloads() {
        try {
            const response = await fetch('/api/settings/parallel_downloads');
            if (!response.ok) throw new Error('Could not fetch parallel downloads setting');
            const setting = await response.json();
            this.parallelDownloads = setting.value || 2;
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        }
    },
    async saveParallelDownloads() {
        try {
            await fetch('/api/settings/parallel_downloads', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ value: this.parallelDownloads })
            });
            this.$emit('show-toast', `Лимит параллельных загрузок установлен: ${this.parallelDownloads}`, 'info');
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        }
    },
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
    async loadLessStrictScanSetting() {
        try {
            const response = await fetch('/api/settings/less_strict_scan');
            if (!response.ok) throw new Error('Не удалось загрузить настройку строгого режима');
            const setting = await response.json();
            this.lessStrictScan = setting.enabled || false;
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        }
    },
    async saveLessStrictScanSetting() {
        try {
            await fetch('/api/settings/less_strict_scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: this.lessStrictScan })
            });
            this.$emit('show-toast', `Менее строгий режим сканирования ${this.lessStrictScan ? 'включен' : 'выключен'}`, 'info');
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        }
    },
    async loadSlicingDeleteSourceSetting() {
        try {
            const response = await fetch('/api/settings/slicing_delete_source');
            if (!response.ok) throw new Error('Не удалось загрузить настройку удаления');
            const setting = await response.json();
            this.slicingDeleteSource = setting.enabled || false;
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        }
    },
    async saveSlicingDeleteSourceSetting() {
        try {
            await fetch('/api/settings/slicing_delete_source', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: this.slicingDeleteSource })
            });
            this.$emit('show-toast', `Удаление исходника после нарезки ${this.slicingDeleteSource ? 'включено' : 'выключено'}`, 'info');
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