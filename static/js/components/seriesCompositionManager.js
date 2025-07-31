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
                <button class="btn btn-primary" @click="handleManualRefresh" :disabled="isLoading">
                    <span v-if="isLoading && isManualRefresh" class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                    <i v-else class="bi bi-arrow-clockwise"></i>
                    <span class="ms-1">Обновить</span>
                </button>
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
            
            <div v-else-if="!displayItems.length && !isLoading" class="empty-state">
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
                            
                            <div v-if="item.type === 'compilation' && !(item.slicing_status === 'completed' && item.is_ignored_by_user)"
                                 class="test-result-card-compact"
                                 :class="getCardClass(item)">
                                
                                <div class="card-line">
                                    <strong class="card-title" style="font-size: 16px;">{{ series.name }} {{ formatEpisode(item) }}</strong>
                                    
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
                                                @change="toggleItemIgnored(item)">
                                        </div>
                                    </div>
                                </div>

                                <div class="card-line text-muted small">
                                    <span><strong>Файл:</strong> {{ item.final_filename || 'Ожидает загрузки' }}</span>
                                </div>

                                <div class="card-line small">
                                    <span>Качество: <strong>{{ item.source_data.resolution ? item.source_data.resolution + 'p' : 'N/A' }}</strong></span>
                                    <span>Тег: <strong>{{ getVoiceoverTag(item) }}</strong></span>
                                    <span>Статус: <strong>{{ item.status }}</strong></span>
                                    <span class="card-rule-name" :title="item.unique_id">ID: {{ item.unique_id.substring(0, 8) }}</span>
                                </div>
                            </div>

                            <div v-if="item.type === 'missing'"
                                 class="test-result-card-compact missing-card">
                                <div class="card-line">
                                    <strong class="card-title">Эпизод {{ item.episode_start }} - отсутствует</strong>
                                    <span><i class="bi bi-eye-slash-fill"></i></span>
                                </div>
                            </div>

                            <div v-if="item.type === 'sliced'"
                                 class="test-result-card-compact sliced-file-card"
                                 :class="{'status-error': item.status === 'missing'}">
                                <div class="card-line">
                                    <strong class="card-title d-flex align-items-center" :title="item.file_path">
                                        <i class="bi bi-file-earmark-check-fill me-2"></i> <span>{{ getBaseName(item.file_path) }}</span>
                                    </strong>
                                    <span v-if="item.status === 'completed'" class="badge bg-primary"><i class="bi bi-check-circle-fill me-1"></i>Нарезан</span>
                                    <span v-else-if="item.status === 'missing'" class="badge bg-danger"><i class="bi bi-exclamation-triangle-fill me-1"></i>Файл отсутствует</span>
                                </div>
                                <div class="card-line text-muted small">
                                    <span>Источник: {{ getBaseName(item.parent_filename) }}</span>
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
    sortedAvailableQualities() {
        return [...this.availableQualities].sort((a, b) => b - a);
    },
    displayItems() {
        const items = [];
        this.mediaItems.forEach(item => {
            items.push({ ...item, type: 'compilation' });
        });
        this.slicedFiles.forEach(file => {
            items.push({
                type: 'sliced',
                unique_id: `sliced-${file.id}`,
                season: file.season,
                episode_start: file.episode_number,
                file_path: file.file_path,
                parent_filename: file.parent_filename,
                status: file.status,
            });
        });
        return items;
    },
    groupedItems() {
        const groups = this.displayItems.reduce((acc, item) => {
            const season = item.season ?? item.result?.extracted?.season ?? 'undefined';
            if (season === 'undefined') return acc;
            if (!acc[season]) acc[season] = [];
            acc[season].push(item);
            return acc;
        }, {});

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
                    for (let i = start; i <= end; i++) {
                        coveredEpisodes.add(i);
                    }
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
        }

        for (const season in groups) {
            groups[season].sort((a, b) => {
                const epA = this.getEpisodeStart(a);
                const epB = this.getEpisodeStart(b);
                return epB - epA;
            });
        }
        
        return groups;
    },
    filteredGroupedItems() {
        if (!this.showOnlyPlanned) {
            return this.groupedItems;
        }
        const filtered = {};
        for (const season in this.groupedItems) {
            const itemsInSeason = this.groupedItems[season].filter(item => {
                if (item.type === 'missing') return true;
                if (item.type === 'sliced') return true;
                if (item.is_ignored_by_user && item.slicing_status === 'completed') return true;
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
    async loadComposition(forceRefresh = false) {
        // ИЗМЕНЕНИЕ: Убрана строка this.isManualRefresh = forceRefresh;
        if (!this.isManualRefresh) { // Не показываем тост, если обновление ручное (тост уже показан в handleManualRefresh)
            this.$emit('show-toast', forceRefresh ? 'Запущено обновление из VK...' : 'Загрузка локальной композиции...', 'info');
        }
        
        this.isLoading = true;
        try {
            const url = `/api/series/${this.seriesId}/composition?refresh=${forceRefresh}`;
            const response = await fetch(url);
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Ошибка построения композиции');
            }
            this.mediaItems = await response.json();

            const seriesResponse = await fetch(`/api/series/${this.seriesId}`);
            const seriesData = await seriesResponse.json();
            this.initializeQualityPriority(seriesData, this.mediaItems);

            await this.loadAndVerifySlicedFiles();
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        } finally {
            this.isLoading = false;
            this.isManualRefresh = false; // Сбрасываем флаг в конце
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
    getCardClass(item) {
        // ПРИОРИТЕТ №1: Если нарезка завершена, карточка всегда серая ("архивная").
        if (item.slicing_status === 'completed') {
            return 'no-match';
        }

        // Остальная логика остается без изменений
        if (item.status === 'error') {
            return 'pending'; // Желтый для ошибки
        }
        if (item.is_ignored_by_user || this.isSeasonIgnored(item.season ?? item.result?.extracted?.season ?? 1)) {
            return 'no-match'; // Серый для игнорируемых вручную
        }

        const isPlanned = ['in_plan_single', 'in_plan_compilation'].includes(item.plan_status);

        if (isPlanned) {
            if (item.status === 'completed') {
                return 'success'; // Зеленый для скачанных, но еще НЕ НАРЕЗАННЫХ
            }
            // Для статусов pending и downloading
            return 'pending'; 
        }

        // Все остальное (redundant, discarded, и т.д.) будет серым
        return 'no-match';
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
    formatItemType(item) {
        if (!item.result || !item.result.extracted) return { icon: 'bi-question-circle', text: '-' };
        const isRange = item.result.extracted.start !== undefined;
        return { icon: isRange ? 'bi-collection-fill' : 'bi-film', text: isRange ? 'Range' : 'Single' };
    },
    getVoiceoverTag(item) {
        return item.result?.extracted?.voiceover || 'N/A';
    },
    formatDate(isoString) {
        if (!isoString) return '-';
        const date = new Date(isoString);
        return date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' });
    },
    getBaseName(path) {
        if (!path) return '';
        return path.split(/[\\/]/).pop();
    },
  },
};
