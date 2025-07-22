const SeriesCompositionManager = {
  props: {
    seriesId: { type: Number, required: true },
    isActive: { type: Boolean, default: false },
  },
  template: `
    <div class="composition-manager">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <div class="modern-form-check form-switch m-0">
                <input class="form-check-input" type="checkbox" role="switch" id="showOnlyPlannedSwitch" v-model="showOnlyPlanned">
                <label class="modern-form-check-label" for="showOnlyPlannedSwitch">Показывать только запланированные</label>
            </div>
        </div>
        
        <div class="position-relative">

            <div v-if="isLoading" class="composition-cards-container">
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
                <div class="test-result-card-compact animate-pulse" style="animation-delay: 0.4s;">
                     <div style="display: flex; flex-direction: column; gap: 12px;">
                        <div class="card-line">
                            <div style="height: 16px; background-color: #e0e0e0; border-radius: 6px; width: 50%;"></div>
                            <div style="height: 24px; background-color: #e0e0e0; border-radius: 6px; width: 48px;"></div>
                        </div>
                        <div style="height: 12px; background-color: #e0e0e0; border-radius: 6px; width: 75%;"></div>
                        <div class="card-line">
                            <div style="height: 12px; background-color: #e0e0e0; border-radius: 6px; width: 45%;"></div>
                            <div style="height: 12px; background-color: #e0e0e0; border-radius: 6px; width: 20%;"></div>
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
                            
                            <div v-if="item.type === 'compilation'"
                                 class="test-result-card-compact"
                                 :class="getCardClass(item)">
                                
                                <div class="card-line">
                                    <strong class="card-title" :title="item.source_data.title">{{ item.source_data.title }}</strong>
                                    <div class="form-check form-switch">
                                        <input class="form-check-input" type="checkbox" role="switch"
                                               :id="'check-' + item.unique_id"
                                               :checked="isItemInPlan(item)"
                                               :disabled="isSeasonIgnored(seasonNumber) || item.is_ignored_by_user || item.slicing_status === 'completed'"
                                               @change="toggleItemIgnored(item)">
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
      mediaItems: [],
      slicedFiles: [],
      showOnlyPlanned: true,
      ignoredSeasons: [], 
    };
  },
  emits: ['show-toast'],
  watch: {
    isActive(newVal) {
      if (newVal) {
        this.loadComposition();
      }
    }
  },
  computed: {
    displayItems() {
        const items = [];

        this.mediaItems.forEach(item => {
            items.push({
                ...item,
                type: 'compilation',
            });
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
            
            if (!acc[season]) {
                acc[season] = [];
            }
            acc[season].push(item);
            return acc;
        }, {});

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
    async loadComposition() {
        if (this.isLoading) return;
        this.isLoading = true;
        this.mediaItems = [];
        this.slicedFiles = [];
        this.ignoredSeasons = [];
        try {
            const compResponse = await fetch(`/api/series/${this.seriesId}/composition`);
            if (!compResponse.ok) throw new Error('Ошибка построения плана композиции');
            this.mediaItems = await compResponse.json();

            const seriesResponse = await fetch(`/api/series/${this.seriesId}`);
            if (!seriesResponse.ok) throw new Error('Ошибка загрузки данных сериала');
            const seriesData = await seriesResponse.json();
            this.ignoredSeasons = seriesData.ignored_seasons ? JSON.parse(seriesData.ignored_seasons) : [];

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

        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        } finally {
            this.isLoading = false;
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
        // Для уже обработанных или нарезанных файлов
        if (item.episode_start != null) {
            return item.episode_start;
        }
        // Для новых одиночных серий
        if (item.result?.extracted?.episode != null) {
            return item.result.extracted.episode;
        }
        // Для новых компиляций
        if (item.result?.extracted?.start != null) {
            return item.result.extracted.start;
        }
        // Если номер не найден, отправляем в конец списка
        return Infinity;
    },

    isSeasonIgnored(seasonNumber) {
        if (seasonNumber === 'undefined') return false;
        return this.ignoredSeasons.includes(parseInt(seasonNumber, 10));
    },
    isItemInPlan(item) {
        if (item.type !== 'compilation') return false;
        const seasonNumber = item.result?.extracted?.season ?? 'undefined';
        if (this.isSeasonIgnored(seasonNumber)) return false;
        if (item.is_ignored_by_user) return false;
        return item.status === 'in_plan_single' || item.status === 'in_plan_compilation';
    },
    getCardClass(item) {
        if (item.slicing_status === 'completed') {
            return 'archived';
        }

        const season = item.result?.extracted?.season ?? 1;
        if (item.is_ignored_by_user || this.isSeasonIgnored(season)) {
            return 'no-match';
        }

        const isPlanned = ['in_plan_single', 'in_plan_compilation'].includes(item.status);
        if (isPlanned) {
            return item.local_status === 'completed' ? 'success' : 'pending';
        }
        
        return 'no-match';
    },
    getSeasonTitle(seasonNumber) {
        if (seasonNumber === 'undefined') {
            return 'Не определено';
        }
        return `Сезон ${String(seasonNumber).padStart(2, '0')}`;
    },
    formatEpisode(item) {
        if (!item.result || !item.result.extracted) return '-';
        const extracted = item.result.extracted;
        const season = String(extracted.season ?? 1).padStart(2, '0');
        if (extracted.episode !== undefined) {
             return `s${season}e${String(extracted.episode).padStart(2, '0')}`;
        }
        if (extracted.start !== undefined && extracted.end !== undefined) {
             return `s${season}e${String(extracted.start).padStart(2, '0')}-e${String(extracted.end).padStart(2, '0')}`;
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
    getBaseName(path) {
        if (!path) return '';
        return path.split(/[\\/]/).pop();
    },
  },
  mounted() {
    this.loadComposition();
  },
};