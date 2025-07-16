const SeriesCompositionManager = {
  props: {
    seriesId: {
      type: Number,
      required: true,
    },
  },
  template: `
    <div class="composition-manager">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <div class="d-flex align-items-center gap-3 legend">
                <small><b>Легенда:</b></small>
                <small><span class="legend-box row-new"></span>Н - Новый</small>
                <small><span class="legend-box row-completed"></span>С - Скачан</small>
                <small><span class="legend-box row-ignored"></span>П - Пропущен</small>
                <small><span class="legend-box row-unavailable"></span>У - Устарел (не найден при последнем сканировании)</small>
            </div>
            <button class="btn btn-sm btn-primary" @click="loadComposition" :disabled="isLoading">
                <span v-if="isLoading" class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                <i v-else class="bi bi-arrow-clockwise"></i>
                <span class="ms-1">Обновить</span>
            </button>
        </div>
        
        <div class="position-relative">
            <transition name="fade">
                <div v-if="isLoading" class="loading-overlay"></div>
            </transition>
            
            <div v-if="!mediaItems.length" class="empty-state">Нет данных для отображения. Нажмите "Обновить", чтобы запустить сканирование.</div>
            <div v-else class="div-table table-composition">
                <div class="div-table-header">
                    <div class="div-table-cell" style="flex: 0 0 50px;"></div>
                    <div class="div-table-cell status-col">Статус</div>
                    <div class="div-table-cell">S/E</div>
                    <div class="div-table-cell">UID</div>
                    <div class="div-table-cell">Тип</div>
                    <div class="div-table-cell">Доступен</div>
                    <div class="div-table-cell">Ссылка</div>
                    <div class="div-table-cell">Тег</div>
                    <div class="div-table-cell">Дата</div>
                </div>
                <div class="div-table-body">
                    <div v-for="item in sortedMediaItems" :key="item.id || item.unique_id" class="div-table-row" :class="getRowClass(item)">
                        <div class="div-table-cell" style="flex: 0 0 50px;">
                            <input type="checkbox" class="form-check-input" 
                                   :checked="!isEffectivelyIgnored(item)"
                                   @change="toggleIgnore(item)">
                        </div>
                        <div class="div-table-cell status-col">{{ getStatusText(item) }}</div>
                        <div class="div-table-cell">{{ formatEpisode(item) }}</div>
                        <div class="div-table-cell uid-col" :title="item.unique_id">{{ item.unique_id }}</div>
                        <div class="div-table-cell">{{ formatItemType(item) }}</div>
                        <div class="div-table-cell">{{ formatAvailability(item) }}</div>
                        <div class="div-table-cell" :title="getLinkFromItem(item)">{{ getLinkFromItem(item) }}</div>
                        <div class="div-table-cell">{{ getVoiceoverTag(item) }}</div>
                        <div class="div-table-cell">{{ formatDate(item.publication_date) }}</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
  `,
  data() {
    return {
      isLoading: false,
      mediaItems: [],
    };
  },
  emits: ['show-toast'],
  computed: {
    sortedMediaItems() {
        if (!this.mediaItems) return [];
        return [...this.mediaItems].sort((a, b) => {
             const epA = a.episode_start ?? 0;
             const epB = b.episode_start ?? 0;
             return epB - epA;
        });
    }
  },
  methods: {
    async loadComposition() {
        this.isLoading = true;
        this.$emit('show-toast', 'Запуск сканирования и получение данных...', 'info');
        try {
            const response = await fetch(`/api/series/${this.seriesId}/composition`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Ошибка загрузки композиции сериала');
            this.mediaItems = data;
        } catch (error) {
            console.error(error);
            this.$emit('show-toast', error.message, 'danger');
        } finally {
            this.isLoading = false;
        }
    },
    async toggleIgnore(item) {
        if (!item.id) {
            this.$emit('show-toast', 'Элемент еще не сохранен в БД. Пожалуйста, обновите страницу.', 'warning');
            return;
        }
        const newIgnoreStatus = !item.is_ignored_by_user;
        try {
            const response = await fetch(`/api/media-items/${item.id}/ignore`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_ignored: newIgnoreStatus })
            });
            if (!response.ok) throw new Error('Ошибка обновления статуса');
            item.is_ignored_by_user = newIgnoreStatus;
        } catch (error) {
             this.$emit('show-toast', error.message, 'danger');
        }
    },
    getRowClass(item) {
        if (item.is_available === false) return 'row-unavailable';
        if (item.is_ignored_by_user) return 'row-ignored';
        return item.status === 'completed' ? 'row-completed' : 'row-new';
    },
    getStatusText(item) {
        if (item.is_available === false) return 'У'; // Устарел
        if (item.is_ignored_by_user) return 'П'; // Пропущен
        return item.status === 'completed' ? 'С' : 'Н'; // Скачан / Новый
    },
    isEffectivelyIgnored(item) {
        return item.is_ignored_by_user;
    },
    // --- ИЗМЕНЕНИЕ: Логика определения сезона теперь имеет приоритеты ---
    formatEpisode(item) {
        let seasonNumber = 1; // Значение по умолчанию

        // Приоритет 1: Номер сезона из самого медиа-элемента (если он есть)
        if (item.season !== null && item.season !== undefined) {
            seasonNumber = item.season;
        } 
        // Приоритет 2: Номер сезона из родительского сериала (если есть)
        else if (item.series?.season) {
            const match = item.series.season.match(/\d+/);
            if (match) {
                seasonNumber = parseInt(match[0], 10);
            }
        }
        
        const season = String(seasonNumber).padStart(2, '0');
        const start = String(item.episode_start ?? 0).padStart(2, '0');
        
        if (item.episode_end) {
             const end = String(item.episode_end).padStart(2, '0');
             return `s${season}e${start}-e${end}`;
        }
        return `s${season}e${start}`;
    },
    formatItemType(item) {
        return item.episode_end ? 'Range' : 'Single';
    },
    formatAvailability(item) {
        return item.is_available ? 'Да' : 'Нет';
    },
    formatDate(isoString) {
        if (!isoString) return '-';
        return new Date(isoString).toLocaleDateString('ru-RU');
    },
    getLinkFromItem(item) {
        return item.source_url || 'URL не найден';
    },
    getVoiceoverTag(item) {
        return item.voiceover_tag || '-';
    }
  },
  mounted() {
    this.loadComposition();
  },
};