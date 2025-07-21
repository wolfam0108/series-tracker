// static/js/components/logsViewerTab.js

const LogsViewerTab = {
  template: `
    <div class="d-flex flex-column h-100">
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
                    <option value="downloader_agent">downloader_agent</option>
                    <option value="slicing_agent">slicing_agent</option>
                    <option value="flask_internal">flask_internal</option>
                    <option value="kinozal_parser">kinozal_parser</option>
                    <option value="main">main</option>
                    <option value="media_api">media_api</option>
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
                <input type="number" id="logLimitInput" v-model.lazy="logLimit" @change="saveLogLimit" class="modern-input" min="100" max="10000" step="100">
            </div>
        </div>
        
        <div class="div-table-wrapper flex-grow-1" style="overflow-y: auto; position: relative;">
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
  `,
  data() {
    return {
      isLoading: false,
      logs: [],
      logFilter: { group: '', level: '' },
      logLimit: 1000,
    };
  },
  emits: ['show-toast'],
  computed: {
    paginatedLogs() {
        return this.logs.slice(0, this.logLimit);
    },
  },
  methods: {
    // ---> ИЗМЕНЕНО: Теперь это основной метод для загрузки данных <---
    load() {
        this.loadLogLimitFromStorage();
        this.loadLogs();
    },
    loadLogLimitFromStorage() {
        const savedLimit = localStorage.getItem('logLimit');
        this.logLimit = parseInt(savedLimit, 10) || 1000;
    },
    saveLogLimit() {
        let newLimit = parseInt(this.logLimit, 10);
        if (isNaN(newLimit) || newLimit < 100) newLimit = 100;
        if (newLimit > 10000) newLimit = 10000;
        this.logLimit = newLimit;
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