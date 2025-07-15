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
                <small><span class="legend-box row-new-compilation"></span>НК - Новая компиляция</small>
                <small><span class="legend-box row-discarded"></span>З - Заменен</small>
                <small><span class="legend-box row-redundant"></span>И - Избыточный</small>
                <small><span class="legend-box row-completed"></span>С - Скачан</small>
                <small><span class="legend-box row-ignored"></span>П - Пропущен</small>
            </div>
            <button class="modern-btn btn-sm btn-primary" @click="loadComposition" :disabled="isLoading">
                <span v-if="isLoading" class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                <i v-else class="bi bi-arrow-clockwise"></i>
                <span class="ms-1">Обновить</span>
            </button>
        </div>
        
        <div class="position-relative">
            <transition name="fade">
                <div v-if="isLoading" class="loading-overlay"></div>
            </transition>
            
            <div v-if="!mediaItems.length" class="empty-state">Нет данных для отображения. Запустите сканирование сериала, нажав "Обновить".</div>
            <div v-else class="div-table table-composition">
                <div class="div-table-header">
                    <div class="div-table-cell" style="flex: 0 0 50px;"></div>
                    <div class="div-table-cell status-col">Статус</div>
                    <div class="div-table-cell">S/E</div>
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
                        <div class="div-table-cell" :title="getLinkFromItem(item)">{{ getLinkFromItem(item) }}</div>
                        <div class="div-table-cell">{{ getVoiceoverTag(item) }}</div>
                        <div class="div-table-cell">{{ formatDate(item.publication_date || (item.source_data && item.source_data.publication_date)) }}</div>
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
             const epA = a.episode_start || (a.result && a.result.extracted ? a.result.extracted.episode || a.result.extracted.start : 0);
             const epB = b.episode_start || (b.result && b.result.extracted ? b.result.extracted.episode || b.result.extracted.start : 0);
             return epB - epA;
        });
    }
  },
  methods: {
    async loadComposition() {
        this.isLoading = true;
        this.$emit('show-toast', 'Запуск сканирования и анализа...', 'info');
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
        if (item.is_ignored_by_user) return 'row-ignored';
        const statusClassMap = {
            'completed': 'row-completed',
            'discarded': 'row-discarded',
            'redundant': 'row-redundant',
            'new': 'row-new',
            'new_compilation': 'row-new-compilation',
            'pending': 'row-new'
        };
        return statusClassMap[item.status] || '';
    },
    getStatusText(item) {
        if (item.is_ignored_by_user) return 'П'; // Пропущен
        const statusMap = {
            'new': 'Н', 'new_compilation': 'НК',
            'completed': 'С', 'downloaded': 'С',
            'discarded': 'З', 'redundant': 'И',
            'pending': 'О', 'downloading': 'ЗГ',
        };
        return statusMap[item.status] || '?';
    },
    isEffectivelyIgnored(item) {
        if (item.is_ignored_by_user) return true;
        return ['discarded', 'redundant'].includes(item.status);
    },
    formatEpisode(item) {
        const seriesData = item.series || {};
        const extractedData = (item.result && item.result.extracted) || {};
        
        const seasonNum = extractedData.season || seriesData.season || 1;
        const season = String(seasonNum).padStart(2, '0');

        const startNum = item.episode_start || extractedData.episode || extractedData.start;
        if (startNum === undefined) return 'N/A';
        const start = String(startNum).padStart(2, '0');
        
        const endNum = item.episode_end || extractedData.end;
        if (endNum && endNum !== startNum) {
             const end = String(endNum).padStart(2, '0');
             return `s${season}e${start}-e${end}`;
        }
        return `s${season}e${start}`;
    },
    formatDate(isoString) {
        if (!isoString) return '-';
        return new Date(isoString).toLocaleDateString('ru-RU');
    },
    getLinkFromItem(item) {
        return item.source_url || (item.source_data ? item.source_data.url : 'URL не найден');
    },
    getVoiceoverTag(item) {
        if (item.result && item.result.extracted && item.result.extracted.voiceover) {
            return item.result.extracted.voiceover;
        }
        return item.voiceover_tag || '-';
    }
  },
  mounted() {
    this.loadComposition();
  },
};