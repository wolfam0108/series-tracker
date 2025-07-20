const LogsModal = {
  components: {
    'settings-logging-tab': SettingsLoggingTab,
  },
  template: `
    <div class="modal fade" ref="logsModal" tabindex="-1" aria-labelledby="logsModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-xl">
            <div class="modal-content modern-modal" style="max-height: 90vh; display: flex; flex-direction: column;">
                <div class="modal-header modern-header">
                    <h5 class="modal-title" id="logsModalLabel"><i class="bi bi-journal-text me-2"></i>Просмотр логов</h5>
                    
                    <ul class="nav modern-nav-tabs" id="logsTab" role="tablist">
                        <li class="nav-item" role="presentation">
                            <button class="nav-link modern-tab-link active" 
                                    id="viewer-tab" data-bs-toggle="tab" data-bs-target="#viewer-tab-pane" 
                                    type="button" role="tab" @click="activeTab = 'viewer'">
                                <i class="bi bi-card-list me-2"></i>Просмотр
                            </button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link modern-tab-link" 
                                    id="settings-tab" data-bs-toggle="tab" data-bs-target="#settings-tab-pane" 
                                    type="button" role="tab" @click="activeTab = 'settings'">
                                <i class="bi bi-toggles2 me-2"></i>Настройка логирования
                            </button>
                        </li>
                    </ul>

                    <button type="button" class="btn-close modern-close" @click="close" aria-label="Close"></button>
                </div>
                <div class="modal-body modern-body" style="display: flex; flex-direction: column; overflow: hidden; flex-grow: 1;">
                    <div class="tab-content modern-tab-content" id="logsTabContent" style="flex-grow: 1; display: flex; flex-direction: column;">
                        <div class="tab-pane fade show active" id="viewer-tab-pane" role="tabpanel" style="display: flex; flex-direction: column; flex-grow: 1;">
                            <div class="row mb-3">
                                <div class="col-md-4">
                                    <label for="logGroupFilter" class="modern-label">Фильтр по группе</label>
                                    <select v-model="logFilter.group" class="modern-select" @change="loadLogs">
                                        <option value="">Все группы</option>
                                        <option value="agent">agent</option>
                                        <option value="anilibria_parser">anilibria_parser</option>
                                        <option value="astar_parser">astar_parser</option>
                                        <option value="auth">auth</option>
                                        <option value="auth_api">auth_api</option>
                                        <option value="database">database</option>
                                        <option value="database_api">database_api</option>
                                        <option value="flask_internal">flask_internal</option>
                                        <option value="kinozal_parser">kinozal_parser</option>
                                        <option value="main">main</option>
                                        <option value="monitoring_agent">monitoring_agent</option>
                                        <option value="qbittorrent">qbittorrent</option>
                                        <option value="renamer">renamer</option>
                                        <option value="routes">routes</option>
                                        <option value="scanner">scanner</option>
                                        <option value="series_api">series_api</option>
                                    </select>
                                </div>
                                <div class="col-md-4">
                                    <label for="logLevelFilter" class="modern-label">Фильтр по уровню</label>
                                    <select v-model="logFilter.level" class="modern-select" @change="loadLogs">
                                        <option value="">Все уровни</option>
                                        <option value="INFO">INFO</option>
                                        <option value="DEBUG">DEBUG</option>
                                        <option value="WARNING">WARNING</option>
                                        <option value="ERROR">ERROR</option>
                                    </select>
                                </div>
                                <div class="col-md-4">
                                    <label for="logLimitInput" class="modern-label">Лимит записей</label>
                                    <input type="number" id="logLimitInput" v-model.lazy="editableLogLimit" class="modern-input" min="100" max="10000" step="100">
                                </div>
                            </div>
                            
                            <div class="div-table-wrapper" style="flex-grow: 1; overflow-y: auto; position: relative;">
                                <div class="position-relative">
                                    <transition name="fade">
                                        <div v-if="isLoading" class="loading-overlay"></div>
                                    </transition>
                                    <div class="div-table table-logs">
                                        <div class="div-table-header">
                                            <div class="div-table-cell">Время</div>
                                            <div class="div-table-cell">Группа</div>
                                            <div class="div-table-cell">Уровень</div>
                                            <div class="div-table-cell">Сообщение</div>
                                        </div>
                                        <div class="div-table-body">
                                            <transition-group name="list" tag="div">
                                                <div v-for="log in paginatedLogs" :key="log.id" class="div-table-row" :class="getLogRowClass(log.level)">
                                                    <div class="div-table-cell">{{ formatTimestamp(log.timestamp) }}</div>
                                                    <div class="div-table-cell">{{ log.group }}</div>
                                                    <div class="div-table-cell">{{ log.level }}</div>
                                                    <div class="div-table-cell">{{ log.message }}</div>
                                                </div>
                                            </transition-group>
                                            <div class="div-table-row" v-if="!logs.length && !isLoading">
                                                <div class="div-table-cell text-center" style="grid-column: 1 / -1;">Логи не найдены.</div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <small v-if="logs.length > logLimit" class="text-muted mt-2 pt-2 border-top">Отображаются последние {{ logLimit }} из {{ logs.length }} записей.</small>
                        </div>
                        <div class="tab-pane fade" id="settings-tab-pane" role="tabpanel">
                            <settings-logging-tab v-if="activeTab === 'settings'" @show-toast="emitToast" ref="loggingTab"></settings-logging-tab>
                        </div>
                    </div>
                </div>
                <div class="modal-footer modern-footer">
                    <button v-if="activeTab === 'viewer'" type="button" class="btn btn-primary" @click="saveLogLimit" :disabled="isLimitUnchanged">
                        <i class="bi bi-save me-2"></i>Сохранить лимит
                    </button>
                    <button type="button" class="btn btn-secondary" @click="close">
                        <i class="bi bi-x-lg me-2"></i>Закрыть
                    </button>
                </div>
            </div>
        </div>
    </div>
  `,
  data() {
    return {
      modal: null,
      isLoading: false,
      logs: [],
      logFilter: { group: '', level: '' },
      logLimit: 1000,
      editableLogLimit: 1000,
      activeTab: 'viewer',
    };
  },
  emits: ['show-toast', 'reload-series'],
  computed: {
    paginatedLogs() {
        return this.logs.slice(0, this.logLimit);
    },
    isLimitUnchanged() {
        return Number(this.editableLogLimit) === Number(this.logLimit);
    }
  },
  methods: {
    open() {
      if (!this.modal) {
        this.modal = new bootstrap.Modal(this.$refs.logsModal);
      }
      this.loadLogLimitFromStorage();
      this.editableLogLimit = this.logLimit; 
      this.activeTab = 'viewer';
      this.modal.show();
      this.loadLogs();
      this.$nextTick(() => {
        const firstTab = this.$refs.logsModal.querySelector('#viewer-tab');
        if (firstTab) {
            new bootstrap.Tab(firstTab).show();
        }
      });
    },
    close() {
      this.modal.hide();
    },
    emitToast(message, type) {
        this.$emit('show-toast', message, type);
    },
    loadLogLimitFromStorage() {
        const savedLimit = localStorage.getItem('logLimit');
        this.logLimit = parseInt(savedLimit, 10) || 1000;
    },
    saveLogLimit() {
        let newLimit = parseInt(this.editableLogLimit, 10);
        if (isNaN(newLimit) || newLimit < 100) newLimit = 100;
        if (newLimit > 10000) newLimit = 10000;
        this.logLimit = newLimit;
        this.editableLogLimit = newLimit;
        localStorage.setItem('logLimit', this.logLimit.toString());
        this.$emit('show-toast', `Лимит логов сохранен: ${this.logLimit} записей`, 'success');
    },
    async loadLogs() {
      this.isLoading = true;
      try {
        const params = new URLSearchParams(this.logFilter);
        const response = await fetch(`/api/logs?${params.toString()}`);
        if(!response.ok) throw new Error("Ошибка загрузки логов");
        const data = await response.json();
        this.logs = data.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
      } catch (error) {
        this.$emit('show-toast', error.message, 'danger');
      } finally {
        this.isLoading = false;
      }
    },
    getLogRowClass(level) {
        const map = { 'INFO': 'table-info-light', 'DEBUG': 'table-debug-light', 'WARNING': 'row-warning-animated', 'ERROR': 'row-danger' };
        return map[level] || '';
    },
    formatTimestamp(isoString) {
        if (!isoString) return 'N/A';
        const date = new Date(isoString);
        return date.toLocaleString('ru-RU', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }
  }
};