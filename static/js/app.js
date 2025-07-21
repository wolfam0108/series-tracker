const { createApp } = Vue;

const app = createApp({
  components: {
    'add-series-modal': AddSeriesModal,
    'status-modal': StatusModal,
    'logs-modal': LogsModal,
    'settings-modal': SettingsModal,
    'confirmation-modal': ConfirmationModal
  },
  data() {
    return {
      series: [],
      agentQueue: [],
      downloadQueue: [],
      slicingQueue: [],
      toastMessage: '',
      activeSeriesId: null,
      isLoading: true,
      eventSource: null,
      
      agentIndicators: {
          monitoring: { color: 'bg-secondary', pulse: false, timeoutId: null },
          downloader: { color: 'bg-secondary', pulse: false, timeoutId: null },
          slicing: { color: 'bg-secondary', pulse: false, timeoutId: null },
      },
      scannerStatus: {},

      stateConfig: {
        'waiting':    { title: 'Ожидание',       icon: 'bi-clock' },
        'viewing':    { title: 'Просмотр',       icon: 'bi-eye' },
        'scanning':   { title: 'Сканирование',   icon: 'bi-ui-checks-grid' },
        'metadata':   { title: 'Метадата',       icon: 'bi-file-earmark-text' },
        'renaming':   { title: 'Переименование', icon: 'bi-pencil-square' },
        'checking':   { title: 'Проверка',       icon: 'bi-arrow-repeat' },
        'activation': { title: 'Активация',      icon: 'bi-lightning-charge' },
        'downloading':{ title: 'Загрузка',       icon: 'bi-download' },
        'ready':      { title: 'Готов',          icon: 'bi-hdd-stack-fill' },
        'error':      { title: 'Ошибка',         icon: 'bi-exclamation-triangle' },
        'overflow':   { title: '',               icon: 'bi-three-dots' }
      },
      layerHierarchy: ['waiting', 'ready', 'downloading', 'activation', 'checking', 'renaming', 'metadata', 'scanning', 'viewing', 'error']
    };
  },
  mounted() {
    this.loadInitialSeries();
    this.loadAgentQueue();
    this.connectEventSource();
  },
  beforeUnmount() {
    if (this.eventSource) {
      this.eventSource.close();
    }
  },
  computed: {
    seriesWithPills() {
      return this.series.map(s => {
        let displayStates = [];
        try {
          const stateData = JSON.parse(s.state);
          displayStates.push(...[...new Set(Object.values(stateData))]);
        } catch (e) {
          displayStates.push(s.state.split(':')[0]);
        }

        if (s.active_status && s.active_status !== '{}') {
          try {
            const activeStatus = JSON.parse(s.active_status);
            const torrentStates = Object.values(activeStatus).map(t => t.state);
            const torrentProgress = Object.values(activeStatus).map(t => t.progress);

            if (torrentStates.some(st => ['downloading', 'forcedDL', 'metaDL'].includes(st))) {
              displayStates.push('downloading');
            }
            const isReady = torrentProgress.some(p => p === 1) && 
                            !torrentStates.some(st => ['error', 'missingFiles'].includes(st));
            if (isReady) {
              displayStates.push('ready');
            }
          } catch (e) {}
        }
        
        let uniqueStates = [...new Set(displayStates)];

        const hasReady = uniqueStates.includes('ready');
        const hasWaiting = uniqueStates.includes('waiting');

        if (s.source_type === 'vk_video') {
            if (uniqueStates.length > 1 && hasWaiting && !hasReady) {
                uniqueStates = uniqueStates.filter(state => state !== 'waiting');
            }
        } else {
            if (hasReady && hasWaiting) {
                uniqueStates = uniqueStates.filter(state => state !== 'waiting');
            }
        }
        
        const activeLayers = this.layerHierarchy.filter(l => uniqueStates.includes(l));
        const priorityLayers = [...activeLayers].reverse();
        const totalCount = priorityLayers.length;
        const maxVisible = 3;
        let pillsToDisplay = [];

        if (totalCount > 0) {
            let visibleKeys = priorityLayers;
            if (totalCount > maxVisible) {
                visibleKeys = priorityLayers.slice(0, maxVisible);
                const overflowCount = totalCount - maxVisible;
                pillsToDisplay.push({ 
                    key: 'overflow', 
                    title: `+${overflowCount}`, 
                    icon: this.stateConfig.overflow.icon 
                });
            }

            visibleKeys.forEach(key => {
                pillsToDisplay.push({
                    key: key,
                    title: this.stateConfig[key]?.title || key,
                    icon: this.stateConfig[key]?.icon || ''
                });
            });
        }
        
        return {
          ...s,
          pills: pillsToDisplay.reverse(),
          displayStates: uniqueStates
        };
      });
    }
  },
  methods: {
    _updateIndicatorState(name, isActive) {
        const indicator = this.agentIndicators[name];
        if (!indicator) return;
        
        clearTimeout(indicator.timeoutId);

        if (isActive) {
            indicator.color = 'bg-success';
            indicator.pulse = true;
        } else {
            indicator.timeoutId = setTimeout(() => {
                indicator.color = 'bg-secondary';
                indicator.pulse = false;
            }, 1000);
        }
    },
    async loadInitialSeries() {
      this.isLoading = true;
      try {
        const response = await fetch('/api/series');
        if (!response.ok) throw new Error(`Ошибка сети: ${response.statusText}`);
        this.series = await response.json();
      } catch (error) { this.showToast(error.message, 'danger');
      } finally { this.isLoading = false; }
    },
    async loadAgentQueue() {
        try {
            const response = await fetch('/api/agent/queue');
            if (!response.ok) throw new Error('Ошибка загрузки очереди агента');
            this.agentQueue = await response.json();
        } catch (error) { this.showToast(error.message, 'danger'); }
    },
    connectEventSource() {
        if (this.eventSource) this.eventSource.close();
        this.eventSource = new EventSource('/api/stream');
        this.eventSource.onopen = () => console.log("SSE соединение установлено.");
        
        this.eventSource.onerror = (err) => {
            console.warn("SSE connection lost. Browser will attempt to reconnect.");
        };

        this.eventSource.addEventListener('agent_queue_update', (event) => {
            this.agentQueue = JSON.parse(event.data);
        });

        // ---> НАЧАЛО ИЗМЕНЕНИЙ В ЛОГИКЕ ИНДИКАТОРОВ <---

        this.eventSource.addEventListener('download_queue_update', (event) => {
            this.downloadQueue = JSON.parse(event.data);
            const indicator = this.agentIndicators.downloader;
            const isActive = this.downloadQueue.length > 0;
            
            clearTimeout(indicator.timeoutId); // Отменяем любой таймер от heartbeat
            indicator.color = isActive ? 'bg-primary' : 'bg-secondary'; // Синий, если активен
            indicator.pulse = isActive;
        });
        
        this.eventSource.addEventListener('slicing_queue_update', (event) => {
            this.slicingQueue = JSON.parse(event.data);
            const indicator = this.agentIndicators.slicing;
            const isActive = this.slicingQueue.length > 0;

            clearTimeout(indicator.timeoutId); // Отменяем любой таймер от heartbeat
            indicator.color = isActive ? 'bg-primary' : 'bg-secondary'; // Синий, если активен
            indicator.pulse = isActive;
        });
        
        this.eventSource.addEventListener('scanner_status_update', (event) => {
            this.scannerStatus = JSON.parse(event.data);
            const indicator = this.agentIndicators.monitoring;
            
            clearTimeout(indicator.timeoutId);

            if (this.scannerStatus.is_scanning || this.scannerStatus.is_awaiting_tasks) {
                indicator.color = 'bg-primary';
                indicator.pulse = true;
            } else {
                indicator.color = 'bg-secondary';
                indicator.pulse = false;
            }
        });
        
        this.eventSource.addEventListener('agent_heartbeat', (event) => {
            const data = JSON.parse(event.data);
            const indicatorName = data.name === 'torrents' ? 'monitoring' : data.name; // 'torrents' это тоже 'monitoring'
            const indicator = this.agentIndicators[indicatorName];
            if (!indicator) return;

            // Если индикатор уже горит синим (активная работа), не перебиваем его зеленым heartbeat'ом
            if (indicator.color === 'bg-primary') return;

            clearTimeout(indicator.timeoutId);
            
            let pulseColor = 'bg-success'; // Зеленый для heartbeat по умолчанию
            if (indicatorName === 'monitoring') {
                 if (data.activity === 'qbit_check') pulseColor = 'bg-success';
                 else if (data.activity === 'file_verify') pulseColor = 'bg-info';
            }
            
            indicator.color = pulseColor;
            indicator.pulse = true;
            
            indicator.timeoutId = setTimeout(() => {
                // Возвращаемся к базовому состоянию (серому или синему, если идет скан)
                if (indicatorName === 'monitoring' && (this.scannerStatus.is_scanning || this.scannerStatus.is_awaiting_tasks)) {
                    indicator.color = 'bg-primary';
                    indicator.pulse = true;
                } else {
                    indicator.color = 'bg-secondary';
                    indicator.pulse = false;
                }
            }, 1000);
        });

        this.eventSource.addEventListener('series_added', (event) => {
            const newSeries = JSON.parse(event.data);
            this.series.push(newSeries);
            this.showToast(`Добавлен сериал: ${newSeries.name}`, 'success');
        });
        this.eventSource.addEventListener('series_updated', (event) => {
            const updatedSeries = JSON.parse(event.data);
            const index = this.series.findIndex(s => s.id === updatedSeries.id);
            if (index !== -1) {
                Object.assign(this.series[index], updatedSeries);
            }
        });
        this.eventSource.addEventListener('series_deleted', (event) => {
            const { id } = JSON.parse(event.data);
            const index = this.series.findIndex(s => s.id === id);
            if (index !== -1) {
                const seriesName = this.series[index].name;
                this.series.splice(index, 1);
                this.showToast(`Удален сериал: ${seriesName}`, 'warning');
            }
        });
    },
    isSeriesBusy(series) {
        const busyStates = ['scanning', 'metadata', 'renaming', 'checking', 'activation'];
        if (!series || !series.displayStates) return false;
        return series.displayStates.some(state => busyStates.includes(state));
    },
    getLayerStyle(series, layerName) {
        const activeLayers = this.layerHierarchy.filter(l => series.displayStates.includes(l));
        const visibleCount = activeLayers.length;
        if (visibleCount === 0) return { width: '0%' };
        const visibleIndex = activeLayers.indexOf(layerName);
        if (visibleIndex === -1) return { width: '0%' };
        const width = ((visibleCount - visibleIndex) / visibleCount) * 100;
        const style = { width: `${width}%` };
        if (width > 0 && width < 99.9) {
            style.boxShadow = '4px 0 12px rgba(0, 0, 0, 0.2)';
        }
        return style;
    },
    getAnimationClass(series) {
        const states = series.displayStates;
        const hasReady = states.includes('ready');
        const hasWaiting = states.includes('waiting');

        if (hasReady && hasWaiting) {
            return 'stripes-stopped';
        }

        if (states.length === 1) {
            if (['error', 'ready'].includes(states[0])) return 'stripes-stopped';
            if (['waiting', 'viewing'].includes(states[0])) return 'stripes-slow';
        }

        return 'stripes-normal';
    },
    async openStatusModal(id) {
        this.activeSeriesId = id;
        try {
            const seriesToUpdate = this.seriesWithPills.find(s => s.id === id);
            if (!seriesToUpdate) return;

            let originalStates = new Set(seriesToUpdate.displayStates);
            let stateWasChangedByModal = false;
            
            if (!originalStates.has('viewing')) {
                await this.setSeriesState(id, [...originalStates, 'viewing']);
                stateWasChangedByModal = true;
            }

            const modalComponent = this.$refs.statusModal;
            if (modalComponent) {
                modalComponent.open(id);
                const modalEl = modalComponent.$refs.statusModal;
                modalEl.addEventListener('hidden.bs.modal', async () => {
                    if (stateWasChangedByModal) {
                        const currentSeries = this.seriesWithPills.find(s => s.id === id);
                        if (currentSeries) {
                            const finalStates = currentSeries.displayStates.filter(st => st !== 'viewing');
                            await this.setSeriesState(id, finalStates.length > 0 ? finalStates : 'waiting');
                        }
                    }
                    this.activeSeriesId = null;
                }, { once: true });
            } else {
                 this.showToast(`Универсальный компонент модального окна не найден.`, 'danger');
                 if (stateWasChangedByModal) await this.setSeriesState(id, [...originalStates]);
                 this.activeSeriesId = null;
            }
        } catch (error) {
            this.showToast('Ошибка при открытии окна статуса: ' + error.message, 'danger');
            this.activeSeriesId = null;
        }
    },
    openAddModal() {
      this.activeSeriesId = null;
      this.$refs.addModal.open();
    },
    openSettingsModal() {
        this.$refs.settingsModal.open();
    },
    openLogsModal() {
        this.$refs.logsModal.open();
    },
    async setSeriesState(id, state) {
        try {
            let finalState;
            if (Array.isArray(state)) {
                const stateObject = {};
                state.forEach((s, i) => stateObject[i] = s);
                finalState = stateObject;
            } else {
                finalState = state;
            }

            const response = await fetch(`/api/series/${id}/state`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ state: finalState })
            });
            if (!response.ok) throw new Error('Ошибка обновления статуса');
        } catch (error) { this.showToast(error.message, 'danger'); }
    },
    async scanSeries(id) {
        this.activeSeriesId = id;
        try {
            const scanResponse = await fetch(`/api/series/${id}/scan`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            const scanData = await scanResponse.json();
            if (!scanResponse.ok) {
                throw new Error(scanData.error || `Ошибка сканирования (статус ${scanResponse.status})`);
            }
            let message = "Сканирование завершено.";
            if (scanData.tasks_created > 0) {
                message = `Создано задач для агента: ${scanData.tasks_created}.`;
            }
            this.showToast(message, 'success');
        } catch (error) {
            this.showToast(error.message, 'danger');
        } finally { this.activeSeriesId = null; }
    },
    async deleteSeries(id) {
        const seriesToDelete = this.series.find(s => s.id === id);
        if (!seriesToDelete) return;
        
        try {
            const result = await this.$refs.confirmationModal.open(
                'Удаление сериала', 
                `Вы уверены, что хотите удалить сериал <strong>${seriesToDelete.name}</strong>?`,
                {
                    text: 'Удалить также записи из qBittorrent (файлы на диске останутся)',
                    checked: true
                }
            );

            if (result.confirmed) {
                const deleteFromQb = result.checkboxState;
                const response = await fetch(`/api/series/${id}?delete_from_qb=${deleteFromQb}`, { method: 'DELETE' });
                if (!response.ok) {
                    const data = await response.json().catch(() => ({error: 'Не удалось прочитать ответ сервера'}));
                    throw new Error(data.error || 'Ошибка удаления сериала');
                }
            }
        } catch (isCancelled) {
            if (isCancelled === false) {
                this.showToast('Удаление отменено.', 'info');
            } else {
                this.showToast(`Ошибка: ${isCancelled.message || 'Неизвестная ошибка'}`, 'danger');
            }
        }
    },
    async toggleAutoScan(id, enabled) {
        try {
            const response = await fetch(`/api/series/${id}/toggle_auto_scan`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: enabled })
            });
            if (!response.ok) throw new Error('Ошибка изменения статуса авто-сканирования');
            this.showToast(`Авто-сканирование ${enabled ? 'включено' : 'выключено'}`, 'info');
        } catch (error) {
            this.showToast(error.message, 'danger');
            const seriesItem = this.series.find(s => s.id === id);
            if (seriesItem) seriesItem.auto_scan_enabled = !enabled;
        }
    },
    formatScanTime(isoString) {
        if (!isoString) return 'Никогда';
        const date = new Date(isoString.endsWith('Z') ? isoString : isoString + 'Z');
        return date.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    },
    showToast(message, type = 'success') {
      this.toastMessage = message;
      const toastEl = document.getElementById('saveToast');
      const toast = bootstrap.Toast.getOrCreateInstance(toastEl);
      toastEl.className = `toast align-items-center text-bg-${type} border-0`;
      toast.show();
    }
  },
  watch: {
    'agentIndicators': {
      handler(newIndicators) {
        const monitorEl = document.getElementById('indicator-monitoring');
        if (monitorEl) {
          monitorEl.className = newIndicators.monitoring.pulse ? 'indicator-pulse' : '';
          monitorEl.style.backgroundColor = `var(--bs-${newIndicators.monitoring.color.replace('bg-', '')})`;
        }
        
        const downloaderEl = document.getElementById('indicator-downloader');
        if (downloaderEl) {
          downloaderEl.className = newIndicators.downloader.pulse ? 'indicator-pulse' : '';
          downloaderEl.style.backgroundColor = `var(--bs-${newIndicators.downloader.color.replace('bg-', '')})`;
        }
        
        const slicerEl = document.getElementById('indicator-slicing');
        if (slicerEl) {
          slicerEl.className = newIndicators.slicing.pulse ? 'indicator-pulse' : '';
          slicerEl.style.backgroundColor = `var(--bs-${newIndicators.slicing.color.replace('bg-', '')})`;
        }
      },
      deep: true
    }
  }
});

app.component('draggable', vuedraggable);

app.mount('#app');