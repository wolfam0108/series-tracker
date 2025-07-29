const StatusTabProperties = {
template: `
    <div>
        <transition name="fade">
            <div v-if="editableSeries.id">
                <div v-if="editableSeries.source_type === 'vk_video'" class="modern-fieldset mb-4">
                    <div class="fieldset-header"><h6 class="fieldset-title mb-0">Настройки VK Video</h6></div>
                    <div class="fieldset-content">
                        <div class="mb-3">
                            <label class="modern-label">Режим поиска</label>
                            <div class="btn-group w-100">
                                <input type="radio" class="btn-check" name="vk_search_mode_edit" id="vk_search_edit" value="search" v-model="editableSeries.vk_search_mode" autocomplete="off">
                                <label class="btn btn-outline-primary" for="vk_search_edit"><i class="bi bi-search me-2"></i>Быстрый поиск (video.search)</label>
                                
                                <input type="radio" class="btn-check" name="vk_search_mode_edit" id="vk_get_all_edit" value="get_all" v-model="editableSeries.vk_search_mode" autocomplete="off">
                                <label class="btn btn-outline-primary" for="vk_get_all_edit"><i class="bi bi-card-list me-2"></i>Полное сканирование (video.get)</label>
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-md-6">
                                <label class="modern-label">Ссылка на канал</label>
                                <input v-model.trim="vkChannelUrl" type="text" class="modern-input" placeholder="https://vkvideo.ru/@канал">
                            </div>
                            <div class="col-md-6">
                                <label class="modern-label">Поисковые запросы (через /)</label>
                                <input v-model.trim="vkQuery" type="text" class="modern-input" placeholder="Название 1 / Название 2">
                            </div>
                        </div>
                    </div>
                </div>

                <div class="modern-fieldset mb-4">
                    <div class="fieldset-header"><h6 class="fieldset-title mb-0">Информация о сериале: {{ editableSeries.name }}</h6></div>
                    <div class="fieldset-content">
                        <div class="row">
                            <div class="col-md-6"><div class="modern-form-group"><label class="modern-label">Название (RU)</label><input v-model="editableSeries.name" type="text" class="modern-input"></div></div>
                            <div class="col-md-6"><div class="modern-form-group"><label class="modern-label">Название (EN)</label><input v-model="editableSeries.name_en" type="text" class="modern-input"></div></div>
                            <div class="col-md-6"><div class="modern-form-group"><label class="modern-label">Путь сохранения</label><input v-model="editableSeries.save_path" type="text" class="modern-input"></div></div>
                            <div class="col-md-6"><div class="modern-form-group"><label class="modern-label">Сезон</label><input v-model="editableSeries.season" type="text" class="modern-input" :disabled="isSeasonless"></div></div>
                            <div class="col-md-6"><div class="modern-form-group mb-md-0"><label class="modern-label">Качество (ручной ввод)</label><input v-model="editableSeries.quality_override" type="text" class="modern-input" placeholder="Напр: BDRip 1080p"></div></div>
                            <div class="col-md-6"><div class="modern-form-group mb-0"><label class="modern-label">Разрешение (ручной ввод)</label><input v-model="editableSeries.resolution_override" type="text" class="modern-input" placeholder="Напр: 1080p"></div></div>
                        </div>
                    </div>
                </div>
                
                <div v-if="editableSeries.source_type === 'vk_video' || (editableSeries.site && editableSeries.site.includes('kinozal'))" class="modern-fieldset mb-4">
                    <div class="fieldset-content py-3">
                        <div class="modern-form-check form-switch d-flex justify-content-center m-0">
                            <input class="form-check-input" type="checkbox" role="switch" v-model="isSeasonless">
                            <label class="modern-form-check-label">Раздача содержит несколько сезонов</label>
                        </div>
                    </div>
                </div>

                <div v-if="editableSeries.source_type === 'torrent' && editableSeries.site && (editableSeries.site.includes('anilibria') || editableSeries.site.includes('aniliberty'))" class="modern-fieldset mb-4">
                     <div class="fieldset-header"><h6 class="fieldset-title mb-0">Выбор качества</h6></div>
                     <div class="fieldset-content">
                         <div class="modern-input-group">
                             <span class="input-group-text">Качество</span>
                             <select v-model="editableSeries.quality" class="modern-select" :disabled="siteTorrentsLoading">
                                 <option v-for="opt in episodeQualityOptions" :value="opt">{{ opt }}</option>
                             </select>
                         </div>
                     </div>
                </div>
                
                 <div v-if="editableSeries.source_type === 'torrent' && editableSeries.site && editableSeries.site.includes('astar')" class="modern-fieldset mb-4">
                     <div class="fieldset-header"><h6 class="fieldset-title mb-0">Выбор качества</h6></div>
                     <div class="fieldset-content">
                        <div v-for="(episodes, index) in sortedQualityOptionsKeys" :key="episodes">
                             <div v-if="episodeQualityOptions[episodes] && episodeQualityOptions[episodes].length > 1" class="modern-input-group" :class="{ 'mb-3': index < sortedQualityOptionsKeys.length - 1 }">
                                 <span class="input-group-text" style="min-width: 130px;">Эпизоды {{ episodes }}</span>
                                 <select v-model="editableSeries.qualityByEpisodes[episodes]" class="modern-select">
                                     <option v-for="option in episodeQualityOptions[episodes]" :value="option">{{ option }}</option>
                                 </select>
                             </div>
                         </div>
                         <div v-if="!siteTorrentsLoading && Object.values(episodeQualityOptions).every(o => o.length <= 1)" class="text-muted small">Для данного релиза нет альтернативных версий.</div>
                     </div>
                </div>
                
                <div v-if="editableSeries.source_type === 'torrent'">
                    <h6>Торренты с сайта (согласно выбранному качеству)</h6>
                    <transition name="fade" mode="out-in">
                        <div v-if="siteTorrentsLoading" key="loading" class="div-table table-site-torrents animate-pulse">
                            <div class="div-table-header"><div class="div-table-cell" v-for="i in 5" :key="i">&nbsp;</div></div>
                            <div class="div-table-body">
                                <div v-for="i in 3" :key="i" class="div-table-row">
                                    <div class="div-table-cell"><div class="skeleton-line short"></div></div>
                                    <div class="div-table-cell"><div class="skeleton-line long"></div></div>
                                    <div class="div-table-cell"><div class="skeleton-line"></div></div>
                                    <div class="div-table-cell"><div class="skeleton-line"></div></div>
                                    <div class="div-table-cell"><div class="skeleton-line"></div></div>
                                </div>
                            </div>
                        </div>
                        <div v-else key="content">
                            <div class="div-table table-site-torrents">
                                <div class="div-table-header"><div class="div-table-cell">ID</div><div class="div-table-cell">Ссылка</div><div class="div-table-cell">Дата</div><div class="div-table-cell">Эпизоды</div><div class="div-table-cell">Качество</div></div>
                                <div class="div-table-body"><transition-group name="list" tag="div">
                                    <div v-for="t in filteredSiteTorrents" :key="t.torrent_id" class="div-table-row" :class="{'row-danger': siteDataIsStale && !siteTorrentsLoading}"><div class="div-table-cell">{{ t.torrent_id }}</div><div class="div-table-cell">{{ t.link }}</div><div class="div-table-cell">{{ t.date_time }}</div><div class="div-table-cell">{{ t.episodes }}</div><div class="div-table-cell">{{ t.quality }}</div></div>
                                </transition-group></div>
                            </div>
                            <small v-if="siteDataIsStale" class="text-danger d-block mt-2">Не удалось обновить данные с сайта, показана последняя сохраненная версия.</small>
                        </div>
                    </transition>
                </div>
            </div>
        </transition>
    </div>
  `,
  props: {
    seriesId: { type: Number, required: true },
    isActive: { type: Boolean, default: false },
  },
  emits: ['show-toast', 'series-updated'],
  data() {
    return {
      isSaving: false,
      siteTorrentsLoading: false,
      siteDataIsStale: false,
      editableSeries: { qualityByEpisodes: {} },
      allSiteTorrents: [],
      episodeQualityOptions: {},
      isSeasonless: false,
      vkChannelUrl: '',
      vkQuery: '',
    };
  },
  watch: {
    isActive: {
        handler(newVal) {
            if (newVal) {
                this.load();
            }
        },
        immediate: true
    }
  },
  computed: {
    reconstructedUrl() {
        if (this.editableSeries.source_type === 'vk_video') {
            return `${this.vkChannelUrl}|${this.vkQuery}`;
        }
        return this.editableSeries.url || '';
    },
    sortedQualityOptionsKeys() {
        if (!this.editableSeries.site || !this.editableSeries.site.includes('astar')) return [];
        return sortEpisodeKeys(Object.keys(this.episodeQualityOptions));
    },
    filteredSiteTorrents() {
        if (!this.editableSeries.id || this.allSiteTorrents.length === 0) return [];
        const site = this.editableSeries.site;
        if (site.includes('anilibria') || site.includes('aniliberty')) {
            return this.allSiteTorrents.filter(t => t.quality === this.editableSeries.quality);
        }
        if (site.includes('astar')) {
            const allChoices = Object.values(this.editableSeries.qualityByEpisodes);
            return this.allSiteTorrents.filter(t => (this.episodeQualityOptions[t.episodes] || []).length <= 1 ? allChoices.includes(t.quality) : t.quality === this.editableSeries.qualityByEpisodes[t.episodes]);
        }
        return this.allSiteTorrents;
    }
  },
  methods: {
    async load() {
        try {
            const response = await fetch(`/api/series/${this.seriesId}`);
            if (!response.ok) throw new Error('Сериал не найден');
            const seriesData = await response.json();
            
            if (seriesData.source_type === 'vk_video') {
                const [channel, query] = seriesData.url.split('|', 2);
                this.vkChannelUrl = channel || '';
                this.vkQuery = query || '';
            } else {
                this.vkChannelUrl = '';
                this.vkQuery = '';
            }
            
            this.editableSeries = seriesData;
            
            if (this.editableSeries.site && this.editableSeries.site.includes('kinozal')) this.isSeasonless = !this.editableSeries.season;
            if (!this.editableSeries.qualityByEpisodes) this.editableSeries.qualityByEpisodes = {};

            if (this.editableSeries.source_type === 'torrent') {
                this.refreshSiteTorrents(); 
            }
        } catch (error) { 
            this.$emit('show-toast', error.message, 'danger');
        }
    },
    _buildQualityOptions(torrents) {
        const site = this.editableSeries.site;
        if (site.includes('anilibria') || site.includes('aniliberty')) {
            this.episodeQualityOptions = [...new Set(torrents.filter(t => t.quality).map(t => t.quality))];
            if (!this.editableSeries.quality || !this.episodeQualityOptions.includes(this.editableSeries.quality)) this.editableSeries.quality = this.episodeQualityOptions.length > 0 ? this.episodeQualityOptions[0] : '';
        } else if (site.includes('astar')) {
            Object.keys(this.episodeQualityOptions).forEach(key => delete this.episodeQualityOptions[key]);
            const episodeVersions = {};
            torrents.forEach(t => { if (t.episodes) { if (!episodeVersions[t.episodes]) episodeVersions[t.episodes] = []; if (t.quality) episodeVersions[t.episodes].push(t.quality); } });
            Object.assign(this.episodeQualityOptions, episodeVersions);
            const savedQualities = this.editableSeries.quality ? this.editableSeries.quality.split(';') : [];
            let qualityIndex = 0;
            this.sortedQualityOptionsKeys.forEach(episodes => {
                if (this.episodeQualityOptions[episodes].length > 1) {
                    this.editableSeries.qualityByEpisodes[episodes] = savedQualities[qualityIndex] || this.episodeQualityOptions[episodes].find(q => q !== 'old') || this.episodeQualityOptions[episodes][0];
                    qualityIndex++;
                } else { this.editableSeries.qualityByEpisodes[episodes] = this.episodeQualityOptions[episodes][0]; }
            });
        }
    },
    async refreshSiteTorrents() {
        this.siteTorrentsLoading = true; 
        this.siteDataIsStale = false;
        try {
            const dbTorrentsRes = await fetch(`/api/series/${this.seriesId}/torrents`);
            if(dbTorrentsRes.ok) this.allSiteTorrents = await dbTorrentsRes.json();
            this._buildQualityOptions(this.allSiteTorrents);
            const response = await fetch('/api/parse_url', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: this.editableSeries.url }) });
            const data = await response.json();
            if (data.success) { 
                this.allSiteTorrents = data.torrents; 
                this._buildQualityOptions(this.allSiteTorrents); 
            } else { 
                this.siteDataIsStale = true; 
                this.$emit('show-toast', `Ошибка парсинга: ${data.error}`, 'warning'); 
            }
        } catch (error) { 
            this.siteDataIsStale = true; 
            this.$emit('show-toast', 'Ошибка сети при обновлении с сайта', 'danger');
        } finally { 
            this.siteTorrentsLoading = false; 
        }
    },
    async updateSeries() {
        this.isSaving = true;
        try {
            let qualityString = ''; 
            const site = this.editableSeries.site;
            if (site.includes('anilibria') || site.includes('aniliberty')) { 
                qualityString = this.editableSeries.quality; 
            } else if (site.includes('astar')) {
                const qualitiesToSave = [], singleVersionQualities = new Set();
                this.sortedQualityOptionsKeys.forEach(episodes => { if (this.episodeQualityOptions[episodes] && this.episodeQualityOptions[episodes].length > 1) qualitiesToSave.push(this.editableSeries.qualityByEpisodes[episodes]); });
                this.sortedQualityOptionsKeys.forEach(episodes => { if (this.episodeQualityOptions[episodes] && this.episodeQualityOptions[episodes].length === 1) singleVersionQualities.add(this.episodeQualityOptions[episodes][0]); });
                qualityString = [...qualitiesToSave, ...Array.from(singleVersionQualities)].join(';');
            }
            
            const payload = { ...this.editableSeries };
            payload.season = this.isSeasonless ? '' : this.editableSeries.season;
            payload.quality = qualityString;

            if (this.editableSeries.source_type === 'vk_video') {
                payload.url = this.reconstructedUrl;
            }

            const response = await fetch(`/api/series/${this.seriesId}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            if (response.ok) { 
                this.$emit('show-toast', 'Изменения сохранены', 'success'); 
                this.$emit('series-updated'); 
            } else { 
                throw new Error((await response.json()).error || 'Ошибка сохранения'); 
            }
        } catch (error) { 
            this.$emit('show-toast', `Сетевая ошибка: ${error.message}`, 'danger'); 
        } finally { 
            this.isSaving = false; 
        }
    },
  }
};