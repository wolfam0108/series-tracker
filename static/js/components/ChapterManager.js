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

        <transition-group v-else name="list" tag="div" class="compilation-cards-container compact-layout">
            <div v-for="item in compilationItems" :key="item.unique_id" class="list-card compilation-card-compact" :class="getCardClass(item)">
                <div class="card-row">
                    <strong class="compilation-title" :title="item.source_url">
                        {{ getBaseName(item.final_filename) || 'Компиляция ' + item.episode_start + '-' + item.episode_end }}
                    </strong>
                    <button class="control-btn" @click="fetchChapters(item)" :disabled="item.isLoadingChapters" title="Проверить оглавление">
                        <span v-if="item.isLoadingChapters" class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                        <i v-else class="bi bi-search"></i>
                    </button>
                </div>
                <div v-if="item.chapters && item.chapters.length" class="card-row chapter-wrap-container">
                    <span v-for="(chapter, index) in item.chapters" :key="index" class="chapter-pill">
                        {{ chapter.time }} ({{ chapter.title }})
                    </span>
                </div>
                <div class="card-row card-footer-status">
                    <span>{{ getChapterCountText(item) }}</span>
                    <span>{{ getStatusText(item) }}</span>
                </div>
            </div>
        </transition-group>
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
        const response = await fetch(`/api/series/${this.seriesId}/media-items`);
        if (!response.ok) throw new Error('Ошибка загрузки медиа-элементов');
        const rawMediaItems = await response.json();
        
        this.compilationItems = rawMediaItems
          .filter(item => item.episode_end && item.episode_end > item.episode_start && item.status === 'completed')
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
    getCardClass(item) {
      // Если проверка еще не проводилась, статус "Не проверено" (желтый)
      if (item.chapters === null) return 'status-yellow';

      // Если проверка была, но главы не найдены (пустой массив), статус "Ошибка" (красный)
      if (item.chapters.length === 0) return 'status-red';

      // Если количество глав совпадает, статус "Соответствует" (зеленый)
      if (item.chapters.length === this.getExpectedCount(item)) {
        return 'status-green';
      }

      // В остальных случаях (несоответствие количества) - статус "Ошибка" (красный)
      return 'status-red';
    },
    getChapterCountText(item) {
        const found = item.chapters ? item.chapters.length : 0;
        const expected = this.getExpectedCount(item);
        return `${found} из ${expected} глав`;
    },
    getStatusText(item) {
        if (!item.chapters) return 'Не проверено';
        if (item.chapters.length === 0) return 'Оглавление не найдено';
        if (item.chapters.length === this.getExpectedCount(item)) return 'Соответствует';
        return 'Несоответствие';
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