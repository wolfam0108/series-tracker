const ChapterManager = {
  name: 'ChapterManager',
  props: {
    seriesId: { type: Number, required: true },
    isActive: { type: Boolean, default: false },
  },
  template: `
    <div class="chapter-manager">
        <div v-if="isLoading" class="text-center p-5"><div class="spinner-border" role="status"></div></div>
        <div v-else-if="!compilationItems.length" class="empty-state">
            В плане загрузки для этого сериала нет видео-компиляций.
        </div>

        <!-- НАЧАЛО ИЗМЕНЕНИЙ: Полностью заменена структура карточки -->
        <transition-group v-else name="list" tag="div" class="compilation-cards-container">
            <div v-for="item in compilationItems" :key="item.unique_id" 
                 class="slicing-card slicing-card-accent" 
                 :class="getCardClass(item)">
                
                <div class="slicing-card-header">
                    <strong class="compilation-title" :title="item.final_filename || item.source_url">
                        {{ getBaseName(item.final_filename) || 'Компиляция ' + item.episode_start + '-' + item.episode_end }}
                    </strong>
                    <div class="d-flex gap-2">
                        <button class="control-btn" @click="fetchChapters(item)" :disabled="item.isLoadingChapters" title="Проверить оглавление">
                            <span v-if="item.isLoadingChapters" class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                            <i v-else class="bi bi-search"></i>
                        </button>
                        <button 
                            v-if="canSlice(item)"
                            class="control-btn text-primary" 
                            @click="createSlicingTask(item)" 
                            :disabled="isSliceButtonDisabled(item)"
                            :title="getSliceButtonTitle(item)">
                                <i class="bi bi-scissors"></i>
                        </button>
                    </div>
                </div>

                <div v-if="item.chapters && item.chapters.length" class="slicing-card-body">
                    <span v-for="(chapter, index) in item.chapters" :key="index" class="chapter-pill">
                        {{ chapter.time }} ({{ chapter.title }})
                    </span>
                </div>

                <div class="slicing-card-footer card-footer-status">
                    <span>{{ getStatusText(item) }}</span>
                </div>
            </div>
        </transition-group>
        <!-- КОНЕЦ ИЗМЕНЕНИЙ -->
    </div>
  `,
  data() {
    return {
      isLoading: false,
      compilationItems: [], 
    };
  },
  emits: ['show-toast'],
  watch: {
    isActive(newVal) {
      if (newVal) {
        this.loadMediaItems();
      }
    }
  },
  methods: {
    async loadMediaItems() {
      if (this.isLoading) return;
      this.isLoading = true;
      try {
        const mediaItemsResponse = await fetch(`/api/series/${this.seriesId}/media-items`);
        if (!mediaItemsResponse.ok) throw new Error('Ошибка загрузки медиа-элементов');
        const rawMediaItems = await mediaItemsResponse.json();
        
        const seriesResponse = await fetch(`/api/series/${this.seriesId}`);
        if (!seriesResponse.ok) throw new Error('Ошибка загрузки данных сериала');
        const seriesData = await seriesResponse.json();
        const ignoredSeasons = seriesData.ignored_seasons ? JSON.parse(seriesData.ignored_seasons) : [];

        this.compilationItems = rawMediaItems
          .filter(item => {
            const season = item.season ?? 1;
            const isCompilation = item.episode_end && item.episode_end > item.episode_start;
            const isDownloaded = item.status === 'completed';
            const isIgnoredBySeason = ignoredSeasons.includes(season);
            
            const showBecauseActive = isDownloaded && !item.is_ignored_by_user && !isIgnoredBySeason;
            const showBecauseCompletedSlicing = ['completed', 'completed_with_errors', 'error'].includes(item.slicing_status);

            return isCompilation && (showBecauseActive || showBecauseCompletedSlicing);
          })
          .map(item => ({
            ...item,
            chapters: item.chapters ? JSON.parse(item.chapters) : null,
            isLoadingChapters: false,
          }))
          .sort((a, b) => a.episode_start - b.episode_start);

      } catch (error) {
        this.$emit('show-toast', error.message, 'danger');
      } finally {
        this.isLoading = false;
      }
    },
    async fetchChapters(item) {
        item.isLoadingChapters = true; 
        try {
            const response = await fetch(`/api/media-items/${item.unique_id}/chapters`, { method: 'POST' });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Ошибка получения глав');
            item.chapters = data; 
        } catch(error) {
            this.$emit('show-toast', error.message, 'danger');
        } finally {
            item.isLoadingChapters = false;
        }
    },
    canSlice(item) {
        return item.chapters && item.chapters.length > 0;
    },
    isSliceButtonDisabled(item) {
        const allowed_statuses = ['none', 'completed_with_errors', 'error'];
        return !allowed_statuses.includes(item.slicing_status);
    },
    getSliceButtonTitle(item) {
        const statusMap = {
            'none': 'Начать нарезку на эпизоды',
            'completed_with_errors': 'Восстановить недостающие файлы',
            'pending': 'В очереди на нарезку',
            'slicing': 'В процессе нарезки...',
            'completed': 'Нарезка успешно завершена',
            'error': 'Произошла ошибка. Попробовать снова?',
        };
        return statusMap[item.slicing_status] || 'Начать нарезку';
    },
    async createSlicingTask(item) {
        if (!confirm(`Вы уверены, что хотите запустить нарезку для файла "${this.getBaseName(item.final_filename)}"?`)) return;
        
        item.slicing_status = 'pending';
        
        try {
            const response = await fetch(`/api/media-items/${item.unique_id}/slice`, {
                method: 'POST'
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Ошибка создания задачи');
            this.$emit('show-toast', 'Задача на нарезку успешно создана.', 'success');
        } catch(error) {
            this.$emit('show-toast', error.message, 'danger');
            item.slicing_status = 'error';
        }
    },
    // --- ИЗМЕНЕНИЕ: Метод теперь возвращает классы для цветовых акцентов ---
    getCardClass(item) {
      if (item.chapters === null) return 'status-warning';
      if (item.chapters.length === 0) return 'status-danger';
      if (item.chapters.length === this.getExpectedCount(item)) {
        return 'status-success';
      }
      return 'status-danger';
    },
    // --- ИЗМЕНЕНИЕ: Метод теперь возвращает полный текст статуса ---
    getStatusText(item) {
        const found = item.chapters ? item.chapters.length : 0;
        const expected = this.getExpectedCount(item);
        
        if (item.chapters === null) return 'Не проверено';
        if (found === 0) return `${found} из ${expected} глав (Оглавление не найдено)`;
        if (found === expected) return `${found} из ${expected} глав (Соответствует)`;
        return `${found} из ${expected} глав (Несоответствие)`;
    },
    getBaseName(path) {
        if (!path) return '';
        return path.split(/[\\/]/).pop();
    },
    getExpectedCount(item) {
        return item.episode_end - item.episode_start + 1;
    },
  },
  mounted() {
    this.loadMediaItems();
  },
};
