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
            <div class="modern-form-check form-switch m-0">
                <input class="form-check-input" type="checkbox" role="switch" id="showOnlyPlannedSwitch" v-model="showOnlyPlanned">
                <label class="modern-form-check-label" for="showOnlyPlannedSwitch">Показывать только запланированные</label>
            </div>
            <button class="btn btn-sm btn-primary" @click="loadComposition" :disabled="isLoading">
                <span v-if="isLoading" class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                <i v-else class="bi bi-arrow-clockwise"></i>
                <span class="ms-1">Обновить план</span>
            </button>
        </div>
        
        <div class="position-relative">
            <transition name="fade">
                <div v-if="isLoading" class="loading-overlay"></div>
            </transition>
            
            <div v-if="!sortedMediaItems.length" class="empty-state">
                Нет данных для отображения. Нажмите "Обновить план".
            </div>

            <transition-group v-else name="list" tag="div" class="composition-cards-container">
                <div v-for="item in filteredMediaItems" :key="item.unique_id" 
                     class="test-result-card-compact" 
                     :class="getCardClass(item)">
                    
                    <div class="card-line">
                        <strong class="card-title" :title="item.source_data.title">{{ item.source_data.title }}</strong>
                        <div class="form-check form-switch">
                            <input class="form-check-input" type="checkbox" role="switch" 
                                   :id="'check-' + item.unique_id"
                                   :checked="isItemInPlan(item)"
                                   @change="toggleSelection(item)">
                            <label class="form-check-label" :for="'check-' + item.unique_id"></label>
                        </div>
                    </div>

                    <div class="card-line text-muted small">
                        <span class="card-url" :title="item.source_data.url">{{ item.source_data.url }}</span>
                        <span>{{ formatDate(item.source_data.publication_date) }}</span>
                    </div>

                    <div class="card-line small">
                        <span class="card-episode-info">
                            <i class="bi me-1" :class="formatItemType(item).icon"></i>
                            {{ formatEpisode(item) }} ({{ getVoiceoverTag(item) }})
                        </span>
                        <span class="card-rule-name" :title="item.unique_id">{{ item.unique_id }}</span>
                    </div>

                </div>
            </transition-group>
        </div>
    </div>
  `,
  data() {
    return {
      isLoading: false,
      mediaItems: [],
      userSelection: {},
      showOnlyPlanned: true, // Новый флаг для фильтрации
    };
  },
  emits: ['show-toast'],
  computed: {
    sortedMediaItems() {
      if (!this.mediaItems) return [];
      return [...this.mediaItems].sort((a, b) => {
          const epA = a.result?.extracted?.episode ?? a.result?.extracted?.start ?? 0;
          const epB = b.result?.extracted?.episode ?? b.result?.extracted?.start ?? 0;
          if (epA !== epB) {
              return epA - epB;
          }
          return new Date(b.source_data.publication_date) - new Date(a.source_data.publication_date);
      });
    },
    filteredMediaItems() {
        if (!this.showOnlyPlanned) {
            return this.sortedMediaItems;
        }
        return this.sortedMediaItems.filter(item => this.isItemInPlan(item));
    }
  },
  methods: {
    async loadComposition() {
        this.isLoading = true;
        this.userSelection = {};
        this.showOnlyPlanned = true; // Сбрасываем фильтр при обновлении
        this.$emit('show-toast', 'Запуск построения плана загрузки...', 'info');
        try {
            const response = await fetch(`/api/series/${this.seriesId}/composition`);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Ошибка построения плана');
            this.mediaItems = data.map(item => ({...item, unique_id: this.generateId(item.source_data.url, item.source_data.publication_date)}));
        } catch (error) {
            console.error(error);
            this.$emit('show-toast', error.message, 'danger');
        } finally {
            this.isLoading = false;
        }
    },
    generateId(url, date) {
        const str = `${url}${date}`;
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash |= 0; 
        }
        return `uid_${Math.abs(hash)}`;
    },
    isItemInPlan(item) {
        if (this.userSelection.hasOwnProperty(item.unique_id)) {
            return this.userSelection[item.unique_id];
        }
        return item.status === 'in_plan_single' || item.status === 'in_plan_compilation';
    },
    toggleSelection(item) {
        this.userSelection[item.unique_id] = !this.isItemInPlan(item);
    },
    getCardClass(item) {
        // Логика для элементов, не входящих в план, остается
        if (!this.isItemInPlan(item)) {
            return 'no-match';
        }
        
        // --- НОВАЯ ЛОГИКА ---
        // Если статус "завершено" - класс 'success' (зеленый)
        if (item.local_status === 'completed') {
            return 'success';
        }
        
        // Во всех остальных случаях (pending) - класс 'pending' (желтый)
        return 'pending';
    },
    formatEpisode(item) {
        if (!item.result || !item.result.extracted) return '-';
        const extracted = item.result.extracted;
        const season = String(extracted.season ?? 1).padStart(2, '0');
        
        if (extracted.episode !== undefined) {
             const start = String(extracted.episode).padStart(2, '0');
             return `s${season}e${start}`;
        }
        if (extracted.start !== undefined && extracted.end !== undefined) {
             const start = String(extracted.start).padStart(2, '0');
             const end = String(extracted.end).padStart(2, '0');
             return `s${season}e${start}-e${end}`;
        }
        return '-';
    },
    formatItemType(item) {
        if (!item.result || !item.result.extracted) return { icon: 'bi-question-circle', text: '-' };
        const isRange = item.result.extracted.start !== undefined;
        return {
            icon: isRange ? 'bi-collection-fill' : 'bi-film',
            text: isRange ? 'Range' : 'Single',
        };
    },
    getVoiceoverTag(item) {
        return item.result?.extracted?.voiceover || 'N/A';
    },
    formatDate(isoString) {
        if (!isoString) return '-';
        const date = new Date(isoString);
        return date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' });
    },
  },
  mounted() {
    this.loadComposition();
  },
};