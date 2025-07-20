const SettingsAgentsTab = {
  name: 'SettingsAgentsTab',
  props: {
    series: {
      type: Array,
      required: true,
      default: () => []
    },
    agentQueue: {
      type: Array,
      required: true,
      default: () => []
    },
    downloadQueue: {
      type: Array,
      required: true,
      default: () => []
    },
    slicingQueue: {
        type: Array,
        required: true,
        default: () => []
    },
  },
  template: `
    <div class="settings-tab-content">
        <div class="modern-fieldset mb-4">
            <div class="fieldset-header">
                <i class="bi bi-cpu me-2"></i>
                <h6 class="fieldset-title mb-0">Очередь задач Агента Обработки</h6>
            </div>
            <div class="fieldset-content">
                <div class="div-table table-agent-queue">
                    <div class="div-table-header">
                        <div class="div-table-cell">ID Сериала</div>
                        <div class="div-table-cell">ID Торрента</div>
                        <div class="div-table-cell">Хеш qb</div>
                        <div class="div-table-cell">Стадия Агента</div>
                    </div>
                    <div class="div-table-body position-relative">
                        <transition-group name="list" tag="div">
                            <div v-for="task in agentQueue" :key="task.hash" class="div-table-row" :class="getAgentRowClass(task.stage)">
                                <div class="div-table-cell" :title="task.series_id">{{ task.series_id }}</div>
                                <div class="div-table-cell" :title="task.torrent_id">{{ task.torrent_id }}</div>
                                <div class="div-table-cell" :title="task.hash" style="word-break: break-all;">{{ task.hash }}</div>
                                <div class="div-table-cell" :title="task.stage">{{ task.stage }}</div>
                            </div>
                        </transition-group>
                        <div v-if="!agentQueue.length" class="div-table-row">
                            <div class="div-table-cell text-center" style="grid-column: 1 / -1;">Очередь пуста</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="modern-fieldset mb-4">
            <div class="fieldset-header d-flex justify-content-between align-items-center">
                <div>
                    <i class="bi bi-camera-reels me-2"></i>
                    <h6 class="fieldset-title mb-0 d-inline-block">Очередь Агента Загрузки (yt-dlp)</h6>
                </div>
            </div>
            <div class="fieldset-content">
                 <div class="div-table table-download-queue">
                    <div class="div-table-header">
                        <div class="div-table-cell">Сериал</div>
                        <div class="div-table-cell">Файл</div>
                        <div class="div-table-cell">Статус</div>
                        <div class="div-table-cell">Ошибка</div>
                    </div>
                    <div class="div-table-body position-relative">
                        <transition-group name="list" tag="div">
                            <div v-for="task in downloadQueue" :key="task.id" class="div-table-row">
                                <div class="div-table-cell" :title="getSeriesName(task.series_id)">{{ getSeriesName(task.series_id) }}</div>
                                <div class="div-table-cell" :title="task.save_path">{{ getBaseName(task.save_path) }}</div>
                                <div class="div-table-cell">
                                    <span class="badge" :class="getDownloadStatusClass(task.status)">{{ task.status }}</span>
                                </div>
                                <div class="div-table-cell error-cell" :title="task.error_message">{{ task.error_message }}</div>
                            </div>
                        </transition-group>
                        <div v-if="!downloadQueue.length" class="div-table-row">
                            <div class="div-table-cell text-center" style="grid-column: 1 / -1;">Очередь загрузок пуста</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="modern-fieldset mb-4">
            <div class="fieldset-header">
                <i class="bi bi-scissors me-2"></i>
                <h6 class="fieldset-title mb-0">Очередь Агента Нарезки (ffmpeg)</h6>
            </div>
            <div class="fieldset-content">
                 <div class="div-table table-slicing-queue">
                    <div class="div-table-header">
                        <div class="div-table-cell">Сериал</div>
                        <div class="div-table-cell">Статус</div>
                        <div class="div-table-cell">Прогресс</div>
                        <div class="div-table-cell">Ошибка</div>
                    </div>
                    <div class="div-table-body position-relative">
                        <transition-group name="list" tag="div">
                            <div v-for="task in slicingQueue" :key="task.id" class="div-table-row">
                                <div class="div-table-cell">{{ getSeriesName(task.series_id) }}</div>
                                <div class="div-table-cell">
                                    <span class="badge" :class="getDownloadStatusClass(task.status)">{{ task.status }}</span>
                                </div>
                                <div class="div-table-cell">
                                    <span class="fw-bold">{{ formatSlicingProgress(task) }}</span>
                                </div>
                                <div class="div-table-cell error-cell" :title="task.error_message">{{ task.error_message }}</div>
                            </div>
                        </transition-group>
                        <div v-if="!slicingQueue.length" class="div-table-row">
                            <div class="div-table-cell text-center" style="grid-column: 1 / -1;">Очередь нарезки пуста</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="modern-fieldset">
            <div class="fieldset-header">
                <i class="bi bi-broadcast-pin me-2"></i>
                <h6 class="fieldset-title mb-0">Активные статусы торрентов (Мониторинг)</h6>
            </div>
            <div class="fieldset-content">
                <div class="div-table table-active-statuses">
                     <div class="div-table-header">
                        <div class="div-table-cell">Сериал</div>
                        <div class="div-table-cell">Хеш</div>
                        <div class="div-table-cell">Статус qBit</div>
                        <div class="div-table-cell">Прогресс</div>
                        <div class="div-table-cell">Скорость DL</div>
                        <div class="div-table-cell">ETA</div>
                    </div>
                    <div class="div-table-body position-relative">
                        <transition-group name="list" tag="div">
                            <div v-for="status in flatTorrentStatuses" :key="status.hash" class="div-table-row">
                                <div class="div-table-cell" :title="status.seriesName">{{ status.seriesName }}</div>
                                <div class="div-table-cell" :title="status.hash" style="word-break: break-all;">{{ status.hash.substring(0, 12) }}...</div>
                                <div class="div-table-cell" :title="status.state">{{ translateStatus(status.state) }}</div>
                                <div class="div-table-cell">
                                    <div class="progress" style="height: 20px; width: 100%; font-size: 12px;">
                                        <div class="progress-bar" role="progressbar" :style="{width: (status.progress * 100) + '%'}" :aria-valuenow="status.progress * 100" aria-valuemin="0" aria-valuemax="100">
                                            {{ (status.progress * 100).toFixed(1) }}%
                                        </div>
                                    </div>
                                </div>
                                <div class="div-table-cell">{{ formatSpeed(status.dlspeed) }}</div>
                                <div class="div-table-cell">{{ formatEta(status.eta) }}</div>
                            </div>
                        </transition-group>
                         <div v-if="!flatTorrentStatuses.length" class="div-table-row">
                            <div class="div-table-cell text-center" style="grid-column: 1 / -1;">Нет активных торрентов для мониторинга.</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
  `,
  data() {
    return {}
  },
  computed: {
    flatTorrentStatuses() {
        const statuses = [];
        this.series.forEach(s => {
            if (s.active_status && typeof s.active_status === 'string' && s.active_status !== '{}') {
                try {
                    const activeStatus = JSON.parse(s.active_status);
                    Object.entries(activeStatus).forEach(([hash, statusData]) => {
                        statuses.push({
                            seriesName: s.name,
                            hash: hash,
                            ...statusData
                        });
                    });
                } catch (e) {
                    console.error("Ошибка парсинга active_status для сериала:", s.name, e);
                }
            }
        });
        return statuses;
    }
  },
  methods: {
    formatSlicingProgress(task) {
        try {
            const progress = JSON.parse(task.progress_chapters || '{}');
            const total = Object.keys(progress).length;
            if (total === 0) {
                // Если прогресса еще нет, пытаемся посчитать по главам из media_item (может быть неточно)
                return '0 / ?';
            }
            const completed = Object.values(progress).filter(s => s === 'completed').length;
            return `${completed} / ${total}`;
        } catch(e) {
            return 'Ошибка';
        }
    },
    getSeriesName(seriesId) {
        const series = this.series.find(s => s.id === seriesId);
        return series ? series.name : `ID: ${seriesId}`;
    },
    getBaseName(path) {
        if (!path) return '';
        return path.split(/[\\/]/).pop();
    },
    getDownloadStatusClass(status) {
        const map = {
            'pending': 'bg-secondary',
            'downloading': 'bg-primary',
            'slicing': 'bg-info',
            'completed': 'bg-success',
            'error': 'bg-danger',
        };
        return map[status] || 'bg-dark';
    },
    getAgentRowClass(stage) {
        const stageToClassMap = {
            'awaiting_metadata': 'row-state-metadata',
            'renaming': 'row-state-renaming',
            'rechecking': 'row-state-checking',
            'activating': 'row-state-activation',
        };
        const mappedStage = stageToClassMap[stage];
        if (mappedStage) {
            return mappedStage;
        }
        if (['polling_for_size', 'awaiting_pause_before_rename'].includes(stage)) {
            return 'row-state-metadata';
        }
        return '';
    },
    formatSpeed(bytes) {
        if (!bytes || bytes === 0) return '0 B/s';
        const k = 1024;
        const sizes = ['B/s', 'KB/s', 'MB/s', 'GB/s'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },
    formatEta(seconds) {
        if (seconds === 8640000 || !seconds) return '∞';
        const d = Math.floor(seconds / (3600*24));
        const h = Math.floor(seconds % (3600*24) / 3600);
        const m = Math.floor(seconds % 3600 / 60);
        const s = Math.floor(seconds % 60);
        
        if (d > 0) return `${d}д ${h}ч`;
        if (h > 0) return `${h}ч ${m}м`;
        if (m > 0) return `${m}м ${s}с`;
        return `${s}с`;
    },
    translateStatus(state) {
        const statuses = { 
            'uploading': 'Раздача', 'forcedUP': 'Раздача', 
            'downloading': 'Загрузка', 'forcedDL': 'Загрузка', 'metaDL': 'Метаданные',
            'stalledUP': 'Ожидание (R)', 'stalledDL': 'Ожидание (D)', 
            'checkingUP': 'Проверка (R)', 'checkingDL': 'Проверка (D)', 'checkingResumeData': 'Проверка', 
            'pausedUP': 'Пауза (R)', 'pausedDL': 'Пауза (D)', 
            'queuedUP': 'В очереди (R)', 'queuedDL': 'В очереди (D)', 
            'allocating': 'Выделение места', 'moving': 'Перемещение', 
            'error': 'Ошибка', 'missingFiles': 'Нет файлов' 
        };
        return statuses[state] || state || 'Неизвестно';
    }
  }
};