const LogsViewerTab = {
template: `
    <div class="d-flex flex-column h-100">
                <div class="row mb-3">
            <div class="col-md-4">
                <constructor-group>
                    <div class="constructor-item item-label-icon" title="Фильтр по группе"><i class="bi bi-folder2-open"></i></div>
                    <constructor-item-select :options="groupOptions" v-model="logFilter.group" @update:modelValue="loadLogs"></constructor-item-select>
                </constructor-group>
            </div>
            <div class="col-md-4">
                <constructor-group>
                    <div class="constructor-item item-label-icon" title="Фильтр по уровню"><i class="bi bi-bar-chart-steps"></i></div>
                    <constructor-item-select :options="levelOptions" v-model="logFilter.level" @update:modelValue="loadLogs"></constructor-item-select>
                </constructor-group>
            </div>
            <div class="col-md-4">
                <constructor-group>
                    <div class="constructor-item item-label-icon" title="Лимит записей"><i class="bi bi-list-ol"></i></div>
                    <input type="text" inputmode="numeric" class="constructor-item item-input" :value="logLimit" @input="handleNumericInput($event, 'logLimit')" @change="saveLogLimit">
                </constructor-group>
            </div>
        </div>
        
        <div class="div-table-wrapper flex-grow-1" style="overflow-y: auto; position: relative;">
            <div class="position-relative">
                <div v-if="isLoading" class="div-table table-logs animate-pulse">
                    <div class="div-table-header">
                        <div class="div-table-cell" v-for="i in 4" :key="i">&nbsp;</div>
                    </div>
                    <div class="div-table-body">
                        <div v-for="i in 10" :key="i" class="div-table-row">
                            <div class="div-table-cell"><div class="skeleton-line"></div></div>
                            <div class="div-table-cell"><div class="skeleton-line short"></div></div>
                            <div class="div-table-cell"><div class="skeleton-line short"></div></div>
                            <div class="div-table-cell"><div class="skeleton-line long"></div></div>
                        </div>
                    </div>
                </div>

                <div v-else class="div-table table-logs">
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
      logGroups: [],
    };
  },
  emits: ['show-toast'],
  computed: {
    // --- НАЧАЛО ИЗМЕНЕНИЙ: Замените старый computed на этот блок ---
    paginatedLogs() {
        return this.logs.slice(0, this.logLimit);
    },
    groupOptions() {
        const options = this.logGroups.map(g => ({ text: g, value: g }));
        return [{ text: 'Все группы', value: '' }, ...options];
    },
    levelOptions() {
        return [
            { text: 'Все уровни', value: '' },
            { text: 'INFO', value: 'INFO' },
            { text: 'DEBUG', value: 'DEBUG' },
            { text: 'WARNING', value: 'WARNING' },
            { text: 'ERROR', value: 'ERROR' }
        ];
    }
    // --- КОНЕЦ ИЗМЕНЕНИЙ ---
  },
  methods: {
    handleNumericInput(event, modelKey) {
        const sanitizedValue = event.target.value.replace(/[^0-9]/g, '');
        this[modelKey] = sanitizedValue ? parseInt(sanitizedValue, 10) : null;
        this.$nextTick(() => {
            if (event.target.value !== sanitizedValue) {
                event.target.value = sanitizedValue;
            }
        });
    },
    async load() {
        this.isLoading = true;
        this.loadLogLimitFromStorage();
        try {
            // ---> ИЗМЕНЕНО: Загружаем сначала группы, потом логи <---
            await this.loadLogGroups();
            await this.loadLogs();
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        } finally {
            this.isLoading = false;
        }
    },
    async loadLogGroups() {
        try {
            const response = await fetch('/api/logs/groups');
            if (!response.ok) throw new Error("Ошибка загрузки групп логов");
            this.logGroups = await response.json();
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
            this.logGroups = []; // В случае ошибки оставляем список пустым
        }
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
        this.logs = []; // В случае ошибки очищаем логи
      } finally {
        this.isLoading = false;
      }
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