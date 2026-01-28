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
                            class="control-btn text-info"
                            @click="fetchFilteredChapters(item)"
                            :disabled="item.isLoadingChapters"
                            title="Проверить и отфильтровать оглавление">
                            <span v-if="item.isLoadingChapters" class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                            <i v-else class="bi bi-funnel"></i>
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
                    <!-- Отображаем отфильтрованные главы -->
                    <div v-if="item.filteredChapters && item.filteredChapters.length">
                        <div class="chapter-section">
                            <h6>Активные главы ({{ item.filteredChapters.length }}):</h6>
                            <div class="chapter-list">
                                <span v-for="(chapter, index) in item.filteredChapters" :key="'filtered-' + index" class="chapter-pill chapter-active">
                                    {{ chapter.time }} ({{ chapter.title }})
                                </span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Отображаем мусорные главы -->
                    <div v-if="item.garbageChapters && item.garbageChapters.length" class="chapter-section">
                        <h6>Мусорные главы ({{ item.garbageChapters.length }}):</h6>
                        <div class="chapter-list">
                            <span v-for="(chapter, index) in item.garbageChapters" :key="'garbage-' + index" class="chapter-pill chapter-garbage"
                                  :title="chapter.garbage_reason">
                                {{ chapter.time }} ({{ chapter.title }})
                                <i class="bi bi-x-circle"></i>
                            </span>
                        </div>
                    </div>
                    
                    <!-- Отображаем все главы, если фильтрация не применялась -->
                    <div v-if="!item.filteredChapters && !item.garbageChapters">
                        <div class="chapter-list">
                            <span v-for="(chapter, index) in item.chapters" :key="index" class="chapter-pill">
                                {{ chapter.time }} ({{ chapter.title }})
                            </span>
                        </div>
                    </div>
                    
                    <!-- Кнопки управления фильтрацией -->
                    <div v-if="item.garbageChapters && item.garbageChapters.length" class="chapter-controls">
                        <button class="btn btn-sm btn-outline-secondary me-2" @click="toggleChapterSelection(item)">
                            <i class="bi bi-check-square"></i> Выбрать главы вручную
                        </button>
                        <button class="btn btn-sm btn-outline-primary" @click="createSlicingTaskWithFilter(item)">
                            <i class="bi bi-scissors"></i> Нарезать с фильтрацией
                        </button>
                    </div>
                    
                    <!-- Интерфейс ручного выбора глав -->
                    <div v-if="item.showChapterSelection" class="chapter-selection mt-3">
                        <h6>Ручной выбор глав для нарезки:</h6>
                        <div class="chapter-checkbox-list">
                            <div v-for="(chapter, index) in item.chapters" :key="'select-' + index" class="form-check">
                                <input class="form-check-input" type="checkbox"
                                       :id="'chapter-' + item.unique_id + '-' + index"
                                       v-model="item.selectedChapters"
                                       :value="index">
                                <label class="form-check-label" :for="'chapter-' + item.unique_id + '-' + index">
                                    {{ chapter.time }} - {{ chapter.title }}
                                </label>
                            </div>
                        </div>
                        <div class="mt-2">
                            <button class="btn btn-sm btn-primary" @click="applyManualChapterFilter(item)">
                                Применить фильтр
                            </button>
                            <button class="btn btn-sm btn-secondary" @click="toggleChapterSelection(item)">
                                Отмена
                            </button>
                        </div>
                    </div>
                </div>

                <div class="slicing-card-footer card-footer-status">
                    <span>{{ getStatusText(item) }}</span>
                    <div v-if="item.statusMessage" class="status-message mt-1">
                        <small>{{ item.statusMessage }}</small>
                    </div>
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
        
        this.compilationItems = rawMediaItems
          .filter(item => {
            // Условия для отображения на вкладке "Нарезка":
            // 1. Это должна быть компиляция (есть начало и конец эпизода).
            const isCompilation = item.episode_end && item.episode_end > item.episode_start;
            // 2. Файл должен быть уже скачан.
            const isDownloaded = item.status === 'completed';
            // 3. Компиляция должна быть в активном плане на нарезку.
            const isInPlan = item.plan_status === 'in_plan_compilation';
            // 4. Или же процесс нарезки для нее уже был запущен (чтобы видеть ошибки/результат).
            const wasProcessedBySlicer = item.slicing_status !== 'none';

            return isCompilation && isDownloaded && (isInPlan || wasProcessedBySlicer);
          })
          .map(item => ({
            ...item,
            chapters: item.chapters ? JSON.parse(item.chapters) : null,
            filteredChapters: null,
            garbageChapters: null,
            selectedChapters: [],
            showChapterSelection: false,
            statusMessage: null,
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
            // Сбрасываем фильтрацию при обычном получении глав
            item.filteredChapters = null;
            item.garbageChapters = null;
            item.statusMessage = null;
        } catch(error) {
            this.$emit('show-toast', error.message, 'danger');
        } finally {
            item.isLoadingChapters = false;
        }
    },
    
    async fetchFilteredChapters(item) {
        item.isLoadingChapters = true;
        try {
            const response = await fetch(`/api/media-items/${item.unique_id}/chapters/filtered`, { method: 'POST' });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Ошибка фильтрации глав');
            
            item.chapters = data.chapters;
            item.filteredChapters = data.filtered_chapters;
            item.garbageChapters = data.garbage_chapters;
            item.statusMessage = data.status_message;
            
            this.$emit('show-toast', 'Главы успешно отфильтрованы', 'success');
        } catch(error) {
            this.$emit('show-toast', error.message, 'danger');
        } finally {
            item.isLoadingChapters = false;
        }
    },
    canSlice(item) {
        return item.chapters && item.chapters.length > 0;
    },
    
    toggleChapterSelection(item) {
        item.showChapterSelection = !item.showChapterSelection;
        if (item.showChapterSelection) {
            // Инициализируем выбранные главы текущими активными (не мусорными)
            if (item.filteredChapters) {
                // Если есть отфильтрованные главы, используем их
                item.selectedChapters = item.filteredChapters.map(ch =>
                    item.chapters.findIndex(c => c.time === ch.time && c.title === ch.title)
                );
            } else {
                // Иначе выбираем все главы
                item.selectedChapters = item.chapters.map((_, index) => index);
            }
        }
    },
    
    async applyManualChapterFilter(item) {
        try {
            const response = await fetch(`/api/media-items/${item.unique_id}/chapters/mark-garbage`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    garbage_indices: item.chapters.map((_, index) => index)
                        .filter(index => !item.selectedChapters.includes(index))
                })
            });
            
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Ошибка ручной разметки глав');
            
            item.chapters = data.chapters;
            item.filteredChapters = data.filtered_chapters;
            item.garbageChapters = data.garbage_chapters;
            item.statusMessage = data.status_message;
            item.showChapterSelection = false;
            
            this.$emit('show-toast', 'Ручная разметка глав применена', 'success');
        } catch(error) {
            this.$emit('show-toast', error.message, 'danger');
        }
    },
    
    async createSlicingTaskWithFilter(item) {
        try {
            const garbageIndices = item.garbageChapters ?
                item.garbageChapters.map(ch => ch.original_index) : [];
            
            const result = await this.$root.$refs.confirmationModal.open(
                'Запуск нарезки с фильтрацией',
                `Вы уверены, что хотите запустить нарезку для файла: <br><strong>${this.getBaseName(item.final_filename)}</strong>?<br>
                 Будет создано ${item.filteredChapters ? item.filteredChapters.length : item.chapters.length} эпизодов.`
            );
            if (!result.confirmed) {
                this.$emit('show-toast', 'Нарезка отменена.', 'info');
                return;
            }
        } catch (isCancelled) {
             if (isCancelled === false) {
                this.$emit('show-toast', 'Нарезка отменена.', 'info');
             }
             return;
        }
        
        item.slicing_status = 'pending';
        
        try {
            const garbageIndices = item.garbageChapters ?
                item.garbageChapters.map(ch => ch.original_index) : [];
            
            const response = await fetch(`/api/media-items/${item.unique_id}/slice-with-filter`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    garbage_indices: garbageIndices
                })
            });
            const data = await response.json();
            if (!response.ok) {
                // Если ошибка связана с несоответствием количества глав, показываем детальную информацию
                if (data.error && data.error.includes('не совпадает')) {
                    this.$emit('show-toast', data.error, 'warning');
                    return;
                }
                throw new Error(data.error || 'Ошибка создания задачи');
            }
            this.$emit('show-toast', 'Задача на нарезку с фильтрацией успешно создана.', 'success');
        } catch(error) {
            this.$emit('show-toast', error.message, 'danger');
            item.slicing_status = 'error';
        }
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
        try {
            const result = await this.$root.$refs.confirmationModal.open(
                'Запуск нарезки',
                `Вы уверены, что хотите запустить нарезку для файла: <br><strong>${this.getBaseName(item.final_filename)}</strong>?`
            );
            if (!result.confirmed) {
                this.$emit('show-toast', 'Нарезка отменена.', 'info');
                return;
            }
        } catch (isCancelled) {
             if (isCancelled === false) {
                this.$emit('show-toast', 'Нарезка отменена.', 'info');
             }
             // Если isCancelled не false, значит произошла ошибка, но здесь нам не нужно ее обрабатывать
             return;
        }
        
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
