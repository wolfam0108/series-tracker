const SeriesCompositionManager = {
  props: {
    seriesId: { type: Number, required: true },
    series: { type: Object, required: true },
    isActive: { type: Boolean, default: false },
  },
  template: `
    <div class="composition-manager">
        <div class="modern-fieldset mb-4">
            <div class="fieldset-header">
                <h6 class="fieldset-title"><i class="bi bi-toggles2 me-2"></i>Настройки композиции</h6>
                <div class="d-flex gap-2">
                    <button class="btn btn-warning btn-sm" @click="reprocessVkFiles" :disabled="isLoading || isReprocessing || renameableFilesCount === 0">
                        <span v-if="isReprocessing" class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                        <i v-else class="bi bi-pencil-square"></i>
                        <span class="ms-1">{{ isReprocessing ? 'В процессе...' : 'Переприменить правила' }}</span>
                    </button>
                    <button class="btn btn-primary btn-sm" @click="handleManualRefresh" :disabled="isLoading">
                        <span v-if="isLoading && isManualRefresh" class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                        <i v-else class="bi bi-arrow-clockwise"></i>
                        <span class="ms-1">Обновить с VK</span>
                    </button>
                </div>
            </div>
            <div class="fieldset-content">
                <div class="row gy-4 align-items-center">
                    <div class="col-lg-4">
                        <h6 class="mb-2">Опции отображения</h6>
                        <div class="modern-form-check form-switch mb-2">
                            <input class="form-check-input" type="checkbox" role="switch" id="autoUpdateSwitch" v-model="autoUpdateEnabled" :disabled="seriesSearchMode === 'get_all'">
                            <label class="modern-form-check-label" for="autoUpdateSwitch">Авто-обновление</label>
                        </div>
                        <div class="modern-form-check form-switch m-0">
                            <input class="form-check-input" type="checkbox" role="switch" id="showOnlyPlannedSwitch" v-model="showOnlyPlanned">
                            <label class="modern-form-check-label" for="showOnlyPlannedSwitch">Только запланированные</label>
                        </div>
                    </div>
                    <div class="col-lg-8">
                         <div v-if="availableQualities.length > 0" class="quality-settings-block">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <h6 class="mb-0">Приоритет качества</h6>
                                <button class="btn btn-primary btn-sm" @click="saveQualityPriority" :disabled="isSavingPriority">
                                    <span v-if="isSavingPriority" class="spinner-border spinner-border-sm"></span>
                                    <i v-else class="bi bi-save"></i>
                                    <span class="ms-1">Сохранить приоритет</span>
                                </button>
                            </div>
                            <draggable
                                v-model="qualityPriority"
                                class="quality-priority-list"
                                item-key="quality"
                                ghost-class="ghost-pill"
                                animation="200">
                                <template #item="{ element }">
                                    <div class="quality-pill">
                                        <span>{{ formatResolution(element).text }}</span>
                                    </div>
                                </template>
                            </draggable>
                         </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="position-relative">
            <div v-if="isLoading && !isManualRefresh" class="composition-cards-container">
                <div class="test-result-card-compact animate-pulse">
                    <div style="display: flex; flex-direction: column; gap: 12px;">
                        <div class="card-line">
                            <div style="height: 16px; background-color: #e0e0e0; border-radius: 6px; width: 60%;"></div>
                            <div style="height: 24px; background-color: #e0e0e0; border-radius: 6px; width: 48px;"></div>
                        </div>
                        <div style="height: 12px; background-color: #e0e0e0; border-radius: 6px; width: 80%;"></div>
                        <div class="card-line">
                            <div style="height: 12px; background-color: #e0e0e0; border-radius: 6px; width: 40%;"></div>
                            <div style="height: 12px; background-color: #e0e0e0; border-radius: 6px; width: 25%;"></div>
                        </div>
                    </div>
                </div>
                <div class="test-result-card-compact animate-pulse" style="animation-delay: 0.2s;">
                     <div style="display: flex; flex-direction: column; gap: 12px;">
                        <div class="card-line">
                            <div style="height: 16px; background-color: #e0e0e0; border-radius: 6px; width: 70%;"></div>
                            <div style="height: 24px; background-color: #e0e0e0; border-radius: 6px; width: 48px;"></div>
                        </div>
                        <div style="height: 12px; background-color: #e0e0e0; border-radius: 6px; width: 100%;"></div>
                        <div class="card-line">
                            <div style="height: 12px; background-color: #e0e0e0; border-radius: 6px; width: 30%;"></div>
                            <div style="height: 12px; background-color: #e0e0e0; border-radius: 6px; width: 35%;"></div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div v-else-if="!mediaItems.length && !slicedFiles.length && !isLoading" class="empty-state">
                Нет данных для отображения.
            </div>

            <div v-else class="season-groups-container">
                <div v-for="seasonNumber in sortedSeasons" :key="seasonNumber" class="season-group">
                    <h5 class="season-header">
                        <span>{{ getSeasonTitle(seasonNumber) }}</span>
                        <div v-if="seasonNumber !== 'undefined'" class="modern-form-check form-switch m-0">
                            <input 
                                class="form-check-input" 
                                type="checkbox" 
                                role="switch" 
                                :id="'season-switch-' + seasonNumber"
                                :checked="!isSeasonIgnored(seasonNumber)"
                                @change="toggleSeasonIgnored(seasonNumber)">
                        </div>
                    </h5>
                    
                    <transition-group name="list" tag="div" class="composition-cards-container">
                        <div v-for="item in filteredGroupedItems[seasonNumber]" :key="item.unique_id">
                            
                            <div v-if="item.type === 'compilation'"
                                 class="test-result-card-compact"
                                 :class="getCardClass(item)">
                                
                                <div class="card-line">
                                    <strong class="card-title" style="font-size: 16px;">
                                        {{ series.name }} {{ formatEpisode(item) }}
                                    </strong>
                                    <div class="d-flex align-items-center">
                                        <div v-if="item.source_data.resolution" class="quality-badge me-2">
                                            <span>{{ item.source_data.resolution }}p</span>
                                        </div>
                                        <div class="modern-form-check form-switch m-0" :title="item.is_ignored_by_user ? 'Снова включить в план' : 'Исключить из плана'">
                                            <input 
                                                class="form-check-input" 
                                                type="checkbox" 
                                                role="switch" 
                                                :id="'ignore-switch-' + item.unique_id"
                                                :checked="!item.is_ignored_by_user"
                                                :disabled="item.slicing_status === 'completed'"
                                                @change="toggleItemIgnored(item)">
                                        </div>
                                    </div>
                                </div>

                                <div class="path-info small mt-2">
                                    <span class="path-label">Исходник:</span>
                                    <span class="path-value text-muted" :title="item.source_title">{{ item.source_title }}</span>
                                </div>

                                <div class="path-info small">
                                    <span class="path-label">Сейчас:</span>
                                    <span v-if="item.final_filename" class="path-value text-muted" :title="item.final_filename">
                                        {{ getBaseName(item.final_filename) }}
                                    </span>
                                    <span v-else class="path-value text-muted fst-italic">Файл еще не скачан</span>
                                </div>

                                <div class="path-info small" :class="getNewPathClass(item)">
                                    <span class="path-label">Будет:</span>
                                    <span v-if="item.new_filename_preview" class="path-value" :title="item.new_filename_preview">
                                        {{ getBaseName(item.new_filename_preview) }}
                                    </span>
                                    <span v-else class="path-value fst-italic">Не удалось сформировать имя</span>
                                </div>

                                <div class="card-line small mt-2">
                                    <span>Тег: <strong>{{ getVoiceoverTag(item) }}</strong></span>
                                    <span>Статус: <strong>{{ item.status }}</strong></span>
                                    <span class="card-rule-name" :title="item.unique_id">ID: {{ item.unique_id.substring(0, 8) }}</span>
                                </div>
                            </div>

                            <div v-if="item.type === 'missing'" class="test-result-card-compact missing-card">
                                <div class="card-line">
                                    <strong class="card-title">Эпизод {{ item.episode_start }} - отсутствует</strong>
                                    <span><i class="bi bi-eye-slash-fill"></i></span>
                                </div>
                            </div>

                            <div v-if="item.type === 'sliced'" class="test-result-card-compact sliced-file-card" :class="{'status-error': item.status === 'missing'}">
                                <div class="card-line">
                                    <strong class="card-title" style="font-size: 16px;">
                                        {{ series.name }} s{{ String(item.season).padStart(2, '0') }}e{{ String(item.episode_number).padStart(2, '0') }}
                                    </strong>
                                    <div class="d-flex align-items-center gap-2">
                                        <div v-if="item.parent_resolution" class="quality-badge">
                                            <span>{{ item.parent_resolution }}p</span>
                                        </div>
                                        <span class="badge bg-primary"><i class="bi bi-check-circle-fill me-1"></i>Нарезан</span>
                                    </div>
                                </div>
                                <div class="path-info small mt-2">
                                    <span class="path-label">Источник:</span>
                                    <span class="path-value text-muted" :title="item.parent_filename">{{ getBaseName(item.parent_filename) }}</span>
                                </div>
                                <div class="path-info small">
                                    <span class="path-label">Сейчас:</span>
                                    <span v-if="item.file_path" class="path-value text-muted" :title="item.file_path">
                                        {{ getBaseName(item.file_path) }}
                                    </span>
                                    <span v-else class="path-value text-muted fst-italic">Путь не найден</span>
                                </div>
                                <div class="path-info small" :class="getNewPathClass(item)">
                                    <span class="path-label">Будет:</span>
                                    <span v-if="item.new_filename_preview" class="path-value" :title="item.new_filename_preview">
                                        {{ getBaseName(item.new_filename_preview) }}
                                    </span>
                                    <span v-else class="path-value fst-italic">Не удалось сформировать имя</span>
                                </div>
                            </div>
                        </div>
                    </transition-group>
                </div>
            </div>
        </div>
    </div>
  `,
  data() {
    return {
      isLoading: false,
      isManualRefresh: false,
      mediaItems: [],
      slicedFiles: [],
      renamePreviews: [],
      isReprocessing: false, 
      renameableFilesCount: 0,
      showOnlyPlanned: true,
      ignoredSeasons: [],
      availableQualities: [],
      qualityPriority: [],
      isSavingPriority: false,
      autoUpdateEnabled: true,
      seriesSearchMode: 'search',
    };
  },
  emits: ['show-toast'],
computed: {
    // 1. СОЗДАЕМ ЕДИНЫЙ, ПЛОСКИЙ И СРАЗУ ОТСОРТИРОВАННЫЙ МАССИВ
    allItems() {
        const items = [];
        
        // Добавляем родительские файлы (компиляции)
        this.mediaItems.forEach(item => {
            const preview = this.renamePreviews.find(p => p.unique_id === item.unique_id);
            items.push({ 
                ...item, 
                type: 'compilation',
                new_filename_preview: preview ? preview.new_filename_preview : null,
            });
        });

        // Добавляем дочерние файлы (нарезку)
        this.slicedFiles.forEach(file => {
            const preview = this.renamePreviews.find(p => p.unique_id === `sliced-${file.id}`);
            const parent = this.mediaItems.find(m => m.unique_id === file.source_media_item_unique_id);
            items.push({
                ...file,
                type: 'sliced',
                unique_id: `sliced-${file.id}`,
                new_filename_preview: preview ? preview.new_filename_preview : null,
                parent_resolution: parent ? parent.source_data.resolution : null,
                // Явно добавляем ключи для сортировки и группировки
                season: file.season ?? (parent ? parent.season : 1),
                episode_start: file.episode_number,
            });
        });
        
        // ВЫПОЛНЯЕМ ЕДИНУЮ СОРТИРОВКУ ДЛЯ ВСЕХ ЭЛЕМЕНТОВ СРАЗУ
        items.sort((a, b) => {
            const epA = this.getEpisodeStart(a);
            const epB = this.getEpisodeStart(b);

            // Сортируем по номеру эпизода в убывающем порядке (99, 50, 49...)
            if (epB !== epA) {
                return epB - epA;
            }
            
            // Если номера эпизодов совпадают (компиляция 1-50 и нарезка 50),
            // компиляция (родитель) должна идти выше (раньше) в списке.
            if (a.type === 'compilation' && b.type === 'sliced') return -1;
            if (a.type === 'sliced' && b.type === 'compilation') return 1;
            
            return 0;
        });
        
        return items;
    },

    // 2. ГРУППИРУЕМ УЖЕ ОТСОРТИРОВАННЫЙ МАССИВ
    groupedItems() {
        // Берем уже готовый, отсортированный массив allItems
        const groups = this.allItems.reduce((acc, item) => {
            const season = item.season ?? item.result?.extracted?.season ?? 'undefined';
            if (!acc[season]) acc[season] = [];
            acc[season].push(item);
            return acc;
        }, {});
        
        // 3. ДОБАВЛЯЕМ "ПРОПАВШИЕ" И СЛЕГКА ПОДПРАВЛЯЕМ СОРТИРОВКУ
        for (const seasonNumber in groups) {
            const itemsInSeason = groups[seasonNumber];
            if (itemsInSeason.length === 0) continue;

            const coveredEpisodes = new Set();
            let minEpisode = Infinity;
            let maxEpisode = -Infinity;

            itemsInSeason.forEach(item => {
                const start = this.getEpisodeStart(item);
                const end = item.episode_end ?? item.result?.extracted?.end ?? start;
                if (start !== Infinity) {
                    for (let i = start; i <= end; i++) { coveredEpisodes.add(i); }
                    minEpisode = Math.min(minEpisode, start);
                    maxEpisode = Math.max(maxEpisode, end);
                }
            });

            if (minEpisode === Infinity) continue;

            for (let i = minEpisode; i <= maxEpisode; i++) {
                if (!coveredEpisodes.has(i)) {
                    itemsInSeason.push({
                        type: 'missing',
                        unique_id: `missing-s${seasonNumber}-e${i}`,
                        season: parseInt(seasonNumber, 10),
                        episode_start: i,
                    });
                }
            }
            
            // Повторная сортировка, чтобы правильно расставить "пропавшие" карточки
            itemsInSeason.sort((a, b) => {
                const epA = this.getEpisodeStart(a);
                const epB = this.getEpisodeStart(b);
                return epB - epA;
            });
        }
        
        return groups;
    },

    // 4. ОСТАЛЬНЫЕ СВОЙСТВА ОСТАЮТСЯ БЕЗ ИЗМЕНЕНИЙ
    filteredGroupedItems() {
        if (!this.showOnlyPlanned) {
            return this.groupedItems;
        }
        const filtered = {};
        for (const season in this.groupedItems) {
            const itemsInSeason = this.groupedItems[season].filter(item => {
                if (item.type === 'missing') return true;
                if (item.type === 'sliced') return true;
                if (item.slicing_status === 'completed' && item.is_ignored_by_user) return true;
                return this.isItemInPlan(item);
            });
            if (itemsInSeason.length > 0) {
                filtered[season] = itemsInSeason;
            }
        }
        return filtered;
    },

    sortedSeasons() {
        return Object.keys(this.filteredGroupedItems).sort((a, b) => {
            if (a === 'undefined') return 1;
            if (b === 'undefined') return -1;
            return parseInt(a, 10) - parseInt(b, 10);
        });
    },
},
  methods: {
    async loadComposition(forceRefresh = false) {
        if (!this.isManualRefresh) {
            this.$emit('show-toast', forceRefresh ? 'Запущено обновление из VK...' : 'Загрузка локальной композиции...', 'info');
        }
        
        this.isLoading = true;
        try {
            // Сначала ждем завершения основного запроса на композицию
            const compRes = await fetch(`/api/series/${this.seriesId}/composition?refresh=${forceRefresh}`);
            // И только потом запрашиваем предпросмотр
            const previewRes = await fetch(`/api/series/${this.seriesId}/rename_preview`);

            if (!compRes.ok) {
                const errorData = await compRes.json();
                throw new Error(errorData.error || 'Ошибка построения композиции');
            }
            if (!previewRes.ok) {
                 throw new Error('Ошибка загрузки предпросмотра имен');
            }

            const previewData = await previewRes.json();
            this.mediaItems = await compRes.json();
            
            this.renamePreviews = previewData.preview;
            this.renameableFilesCount = previewData.needs_rename_count;

            const seriesResponse = await fetch(`/api/series/${this.seriesId}`);
            const seriesData = await seriesResponse.json();
            this.initializeQualityPriority(seriesData, this.mediaItems);

            await this.loadAndVerifySlicedFiles();
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        } finally {
            this.isLoading = false;
            this.isManualRefresh = false;
        }
    },
    async reprocessVkFiles() {
        this.isReprocessing = true;
        this.$emit('show-toast', 'Запущена задача на переименование файлов...', 'info');
        try {
            const response = await fetch(`/api/series/${this.seriesId}/reprocess_vk_files`, { method: 'POST' });
            const data = await response.json();
            if (!response.ok) {
                this.isReprocessing = false;
                throw new Error(data.error || 'Ошибка при запуске переименования');
            }
        } catch (error) {
            this.isReprocessing = false;
            this.$emit('show-toast', error.message, 'danger');
        }
    },
    onRenamingComplete() {
        this.$emit('show-toast', 'Переименование файлов завершено. Обновление...', 'success');
        this.isReprocessing = false;
        this.loadComposition(false);
    },
    getNewPathClass(item) {
        const current_filename = item.type === 'compilation' ? item.final_filename : item.file_path;
        if (!item.new_filename_preview) {
            return 'path-error';
        }
        if (current_filename && this.getBaseName(current_filename) !== this.getBaseName(item.new_filename_preview)) {
            return 'path-mismatch';
        }
        return 'path-ok';
    },
    getCardClass(item) {
        // Если компиляция была нарезана и исходник удален - это "архивный" файл
        if (item.slicing_status === 'completed' && !item.final_filename) {
            return 'archived'; // Новый серый статус
        }
        if (item.status === 'error' || item.slicing_status === 'error' || item.slicing_status === 'completed_with_errors') {
            return 'pending'; // Желтый для любых ошибок
        }
        if (item.is_ignored_by_user || this.isSeasonIgnored(item.season ?? item.result?.extracted?.season ?? 1)) {
            return 'no-match';
        }
        const isPlanned = ['in_plan_single', 'in_plan_compilation'].includes(item.plan_status);
        if (isPlanned) {
            if (item.status === 'completed') {
                return 'success';
            }
            return 'pending';
        }
        return 'no-match';
    },
    handleManualRefresh() {
        this.isManualRefresh = true;
        this.$emit('show-toast', 'Запущено полное обновление композиции из VK...', 'info');
        this.loadComposition(true);
    },
    formatResolution(resolution) {
        if (!resolution) return { text: 'N/A' };
        if (resolution >= 2160) return { text: `4K ${resolution}` };
        if (resolution >= 1080) return { text: `FHD ${resolution}` };
        if (resolution >= 720) return { text: `HD ${resolution}` };
        if (resolution >= 480) return { text: `SD ${resolution}` };
        return { text: `${resolution}p` };
    },
    async saveQualityPriority() {
        this.isSavingPriority = true;
        try {
            const response = await fetch(`/api/series/${this.seriesId}/vk-quality-priority`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ priority: this.qualityPriority })
            });
            if (!response.ok) throw new Error('Ошибка сохранения приоритета');
            this.$emit('show-toast', 'Приоритет качества сохранен. Перезагрузка...', 'success');
            await this.loadComposition(true);
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        } finally {
            this.isSavingPriority = false;
        }
    },
    initializeQualityPriority(seriesData, allItems) {
        const allResolutions = [...new Set(allItems.map(item => item.source_data.resolution).filter(res => res > 0))];
        this.availableQualities = allResolutions.sort((a, b) => b - a);

        let savedPriority = [];
        try {
            if (seriesData.vk_quality_priority) {
                savedPriority = JSON.parse(seriesData.vk_quality_priority);
            }
        } catch (e) { /* ignore */ }

        const finalPriority = [...savedPriority];
        this.availableQualities.forEach(q => {
            if (!finalPriority.includes(q)) {
                finalPriority.push(q);
            }
        });
        this.qualityPriority = finalPriority.filter(q => this.availableQualities.includes(q));
    },
    async initialize() {
        if (this.isLoading) return;
        this.isLoading = true;
        try {
            const seriesResponse = await fetch(`/api/series/${this.seriesId}`);
            if (!seriesResponse.ok) throw new Error('Ошибка загрузки данных сериала');
            const seriesData = await seriesResponse.json();
            
            this.seriesSearchMode = seriesData.vk_search_mode || 'search';
            this.ignoredSeasons = seriesData.ignored_seasons ? JSON.parse(seriesData.ignored_seasons) : [];

            if (this.seriesSearchMode === 'get_all') {
                this.autoUpdateEnabled = false;
            } else {
                const savedState = localStorage.getItem(`composition_autoupdate_${this.seriesId}`);
                this.autoUpdateEnabled = savedState !== null ? JSON.parse(savedState) : true;
            }

            await this.loadComposition(this.autoUpdateEnabled);
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        } finally {
            this.isLoading = false;
        }
    },
    async loadAndVerifySlicedFiles() {
        const slicedResponse = await fetch(`/api/series/${this.seriesId}/sliced-files`);
        if (!slicedResponse.ok) throw new Error('Ошибка загрузки нарезанных файлов');
        this.slicedFiles = await slicedResponse.json();
        const uniqueCompilationIds = [...new Set(this.slicedFiles.map(f => f.source_media_item_unique_id))];
        for (const uid of uniqueCompilationIds) {
            try {
                await fetch(`/api/media-items/${uid}/verify-sliced-files`, { method: 'POST' });
            } catch (verifyError) {
                console.warn(`Не удалось проверить файлы для компиляции ${uid}:`, verifyError);
            }
        }
        if (uniqueCompilationIds.length > 0) {
             const refreshedSlicedResponse = await fetch(`/api/series/${this.seriesId}/sliced-files`);
             this.slicedFiles = await refreshedSlicedResponse.json();
        }
    },
    async toggleItemIgnored(item) {
        const isCurrentlyIgnored = item.is_ignored_by_user;
        const newIgnoredState = !isCurrentlyIgnored;
        item.is_ignored_by_user = newIgnoredState;
        try {
            const response = await fetch(`/api/media-items/${item.unique_id}/ignore`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_ignored: newIgnoredState })
            });
            if (!response.ok) throw new Error('Ошибка сохранения');
        } catch(error) {
            this.$emit('show-toast', error.message, 'danger');
            item.is_ignored_by_user = isCurrentlyIgnored;
        }
    },
    async toggleSeasonIgnored(seasonNumber) {
        seasonNumber = parseInt(seasonNumber, 10);
        const isCurrentlyIgnored = this.ignoredSeasons.includes(seasonNumber);
        let newIgnoredSeasons = [...this.ignoredSeasons];
        if (isCurrentlyIgnored) {
            newIgnoredSeasons = newIgnoredSeasons.filter(s => s !== seasonNumber);
        } else {
            newIgnoredSeasons.push(seasonNumber);
        }
        this.ignoredSeasons = newIgnoredSeasons;
        try {
            const response = await fetch(`/api/series/${this.seriesId}/ignored-seasons`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ seasons: newIgnoredSeasons })
            });
            if (!response.ok) throw new Error('Ошибка сохранения настроек сезона');
        } catch(error) {
            this.$emit('show-toast', error.message, 'danger');
            this.ignoredSeasons = this.ignoredSeasons.filter(s => s !== seasonNumber);
        }
    },
    getEpisodeStart(item) {
        if (item.episode_start != null) return item.episode_start;
        if (item.result?.extracted?.episode != null) return item.result.extracted.episode;
        if (item.result?.extracted?.start != null) return item.result.extracted.start;
        return Infinity;
    },
    isSeasonIgnored(seasonNumber) {
        if (seasonNumber === 'undefined') return false;
        return this.ignoredSeasons.includes(parseInt(seasonNumber, 10));
    },
    isItemInPlan(item) {
        if (item.type !== 'compilation') return false;
        
        const seasonNumber = item.season ?? item.result?.extracted?.season ?? 'undefined';
        if (this.isSeasonIgnored(seasonNumber)) return false;
        if (item.is_ignored_by_user) return false;
        
        const plannedStatuses = ['in_plan_single', 'in_plan_compilation'];
        return plannedStatuses.includes(item.plan_status);
    },
    getSeasonTitle(seasonNumber) {
        if (seasonNumber === 'undefined') return 'Не определено';
        return `Сезон ${String(seasonNumber).padStart(2, '0')}`;
    },
    formatEpisode(item) {
        if (!item.result || !item.result.extracted) return '-';
        const extracted = item.result.extracted;
        const season = String(extracted.season ?? 1).padStart(2, '0');
        if (extracted.episode != null) return `s${season}e${String(extracted.episode).padStart(2, '0')}`;
        if (extracted.start != null && extracted.end != null) return `s${season}e${String(extracted.start).padStart(2, '0')}-e${String(extracted.end).padStart(2, '0')}`;
        return '-';
    },
    getVoiceoverTag(item) {
        return item.result?.extracted?.voiceover || 'N/A';
    },
    getBaseName(path) {
        if (!path) return '';
        return path.split(/[\\/]/).pop();
    },
  },
};