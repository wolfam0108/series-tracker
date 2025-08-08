const StatusTabProperties = {
  // --- НАЧАЛО ИЗМЕНЕНИЙ: Добавьте этот блок ---
  components: {
    'constructor-item-select': ConstructorItemSelect,
  },
template: `
<div>
    <transition name="fade">
        <div v-if="editableSeries.id">
            <div v-if="editableSeries.source_type === 'vk_video'" class="modern-fieldset mb-4">
                <div class="fieldset-header"><h6 class="fieldset-title mb-0">Настройки VK Video</h6></div>
                <div class="fieldset-content">
                    <div class="mb-4">
                        <label class="modern-label">Режим поиска</label>
                        <div class="btn-group w-100">
                            <input type="radio" class="btn-check" name="vk_search_mode_edit" id="vk_search_edit" value="search" v-model="editableSeries.vk_search_mode" autocomplete="off">
                            <label class="btn btn-outline-primary" for="vk_search_edit"><i class="bi bi-search me-2"></i>Быстрый поиск</label>
                            
                            <input type="radio" class="btn-check" name="vk_search_mode_edit" id="vk_get_all_edit" value="get_all" v-model="editableSeries.vk_search_mode" autocomplete="off">
                            <label class="btn btn-outline-primary" for="vk_get_all_edit"><i class="bi bi-card-list me-2"></i>Полное сканирование</label>
                        </div>
                        <small class="form-text text-muted mt-2 d-block">
                            <b>Быстрый поиск:</b> использует API поиска VK. Быстро, но может пропустить некоторые видео.
                            <br>
                            <b>Полное сканирование:</b> загружает список всех видео с канала, затем фильтрует. Медленнее, но надёжнее.
                        </small>
                    </div>
                    <div class="row">
                        <div class="col-md-6">
                            <constructor-group :class="vkChannelUrlClasses">
                                <div class="constructor-item item-label-icon" title="Ссылка на канал"><i class="bi bi-youtube"></i></div>
                                <div class="constructor-item item-floating-label">
                                    <input v-model.trim="vkChannelUrl" type="text" class="item-input" id="vk-channel-url-edit" placeholder=" ">
                                    <label for="vk-channel-url-edit">Ссылка на канал</label>
                                </div>
                            </constructor-group>
                        </div>
                        <div class="col-md-6">
                            <constructor-group :class="vkQueryClasses">
                                <div class="constructor-item item-label-icon" title="Поисковые запросы"><i class="bi bi-search"></i></div>
                                <div class="constructor-item item-floating-label">
                                    <input v-model.trim="vkQuery" type="text" class="item-input" id="vk-query-edit" placeholder=" ">
                                    <label for="vk-query-edit">Поисковые запросы (через /)</label>
                                </div>
                            </constructor-group>
                        </div>
                    </div>
                </div>
            </div>

            <div class="modern-fieldset mb-4">
                <div class="fieldset-header"><h6 class="fieldset-title mb-0">Информация о сериале: {{ editableSeries.name }}</h6></div>
                <div class="fieldset-content">
                    <div class="row">
                        <div class="col-md-6">
                             <constructor-group :class="nameClasses">
                                <div class="constructor-item item-label-icon" title="Название (RU)"><i class="bi bi-type"></i></div>
                                <div class="constructor-item item-floating-label">
                                    <input v-model="editableSeries.name" type="text" class="item-input" id="seriesNameRu-edit" placeholder=" ">
                                    <label for="seriesNameRu-edit">Название (RU)</label>
                                </div>
                            </constructor-group>
                        </div>
                        <div class="col-md-6">
                            <constructor-group :class="nameEnClasses">
                                <div class="constructor-item item-label-icon" title="Название (EN)"><i class="bi bi-translate"></i></div>
                                <div class="constructor-item item-floating-label">
                                    <input v-model.trim="editableSeries.name_en" type="text" class="item-input" id="seriesNameEn-edit" placeholder=" ">
                                    <label for="seriesNameEn-edit">Название (EN)</label>
                                </div>
                            </constructor-group>
                        </div>
                    </div>
                    <div class="row mt-3">
                        <div class="col-md-6">
                            <constructor-group :class="savePathClasses">
                                <div class="constructor-item item-label-icon" title="Путь сохранения"><i class="bi bi-folder2-open"></i></div>
                                <div class="constructor-item item-floating-label">
                                    <input v-model.trim="editableSeries.save_path" type="text" class="item-input" id="savePath-edit" placeholder=" ">
                                    <label for="savePath-edit">Путь сохранения</label>
                                </div>
                            </constructor-group>
                        </div>
                        <div class="col-md-6">
                            <constructor-group :class="[seasonClasses, {'is-disabled': isSeasonless}]">
                                <div class="constructor-item item-label-icon" title="Сезон"><i class="bi bi-collection-play"></i></div>
                                <div class="constructor-item item-floating-label">
                                    <input v-model.trim="editableSeries.season" type="text" class="item-input" id="season-edit" placeholder=" " :disabled="isSeasonless">
                                    <label for="season-edit">Сезон (формат s01)</label>
                                </div>
                            </constructor-group>
                        </div>
                    </div>
                    <div class="row mt-3">
                        <div class="col-md-6">
                            <constructor-group>
                                <div class="constructor-item item-label-icon" title="Качество (ручной ввод)"><i class="bi bi-badge-hd"></i></div>
                                <div class="constructor-item item-floating-label">
                                    <input v-model="editableSeries.quality_override" type="text" class="item-input" id="quality-override-edit" placeholder=" ">
                                    <label for="quality-override-edit">Качество (ручной ввод)</label>
                                </div>
                            </constructor-group>
                        </div>
                        <div class="col-md-6">
                            <constructor-group>
                                <div class="constructor-item item-label-icon" title="Разрешение (ручной ввод)"><i class="bi bi-aspect-ratio"></i></div>
                                <div class="constructor-item item-floating-label">
                                    <input v-model="editableSeries.resolution_override" type="text" class="item-input" id="resolution-override-edit" placeholder=" ">
                                    <label for="resolution-override-edit">Разрешение (ручной ввод)</label>
                                </div>
                            </constructor-group>
                        </div>
                    </div>
                    
                    <div v-if="editableSeries.source_type === 'torrent'" class="row mt-3">
                        <div class="col-12">
                            <constructor-group>
                                <div class="constructor-item item-label-icon item-label-text-icon" title="Профиль правил для переименования">
                                    <i class="bi bi-funnel-fill"></i>
                                    <span>Профиль правил</span>
                                </div>
                                <constructor-item-select 
                                    :options="parserProfileOptions" 
                                    v-model="editableSeries.parser_profile_id"
                                ></constructor-item-select>
                            </constructor-group>
                        </div>
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

            <div v-if="trackerInfo && trackerInfo.ui_features.quality_selector === 'anilibria'" class="modern-fieldset mb-4">
                 <div class="fieldset-header"><h6 class="fieldset-title mb-0">Выбор качества</h6></div>
                 <div class="fieldset-content">
                    <constructor-group>
                        <div class="constructor-item item-label">Качество</div>
                        <constructor-item-select :options="qualityOptionsAnilibria" v-model="editableSeries.quality" :disabled="siteTorrentsLoading"></constructor-item-select>
                    </constructor-group>
                 </div>
            </div>
            
             <div v-if="trackerInfo && trackerInfo.ui_features.quality_selector === 'astar'" class="modern-fieldset mb-4">
                 <div class="fieldset-header"><h6 class="fieldset-title mb-0">Выбор качества</h6></div>
                 <div class="fieldset-content">
                    <div v-for="(episodes, index) in sortedQualityOptionsKeys" :key="episodes">
                         <div v-if="episodeQualityOptions[episodes] && episodeQualityOptions[episodes].length > 1" class="field-group">
                             <constructor-group>
                                 <div class="constructor-item item-label">Эпизоды {{ episodes }}</div>
                                 <constructor-item-select :options="episodeQualityOptions[episodes].map(q => ({text: q, value: q}))" v-model="editableSeries.qualityByEpisodes[episodes]"></constructor-item-select>
                             </constructor-group>
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
  emits: ['show-toast', 'series-updated', 'saving-state'],
  data() {
    return {
      isSaving: false,
      siteTorrentsLoading: false,
      siteDataIsStale: false,
      editableSeries: { qualityByEpisodes: {} },
      originalSavePath: '',
      allSiteTorrents: [],
      episodeQualityOptions: {},
      isSeasonless: false,
      vkChannelUrl: '',
      vkQuery: '',
      parserProfiles: [],
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
        // Вычисляемые свойства для классов валидации
    vkChannelUrlClasses() {
        return { 'is-valid': !!this.vkChannelUrl, 'is-invalid': !this.vkChannelUrl };
    },
    vkQueryClasses() {
        if (this.editableSeries.vk_search_mode !== 'search') return {};
        return { 'is-valid': !!this.vkQuery, 'is-invalid': !this.vkQuery };
    },
    nameClasses() {
        return { 'is-valid': !!this.editableSeries.name, 'is-invalid': !this.editableSeries.name };
    },
    nameEnClasses() {
        return { 'is-valid': !!this.editableSeries.name_en, 'is-invalid': !this.editableSeries.name_en };
    },
    savePathClasses() {
        return { 'is-valid': !!this.editableSeries.save_path, 'is-invalid': !this.editableSeries.save_path };
    },
    seasonClasses() {
        if (this.isSeasonless) return {};
        const isValid = /^s\d{2}$/.test(this.editableSeries.season);
        return { 'is-valid': isValid, 'is-invalid': !isValid };
    },
    // --- КОНЕЦ ИЗМЕНЕНИЙ ---
    qualityOptionsAnilibria() {
         if (!this.episodeQualityOptions || !this.episodeQualityOptions.length) return [];
         return this.episodeQualityOptions.map(q => ({ text: q, value: q }));
    },
    qualityOptionsAnilibria() {
         if (!this.episodeQualityOptions || !this.episodeQualityOptions.length) return [];
         return this.episodeQualityOptions.map(q => ({ text: q, value: q }));
    },
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
    },
        parserProfileOptions() {
        const options = this.parserProfiles.map(p => ({ text: p.name, value: p.id }));
        return [{ text: 'Не выбрано', value: null }, ...options];
    },
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
            this.originalSavePath = seriesData.save_path;
            
            const sourceType = this.editableSeries.source_type;
            const site = this.editableSeries.site || '';
            if (sourceType === 'vk_video' || site.includes('kinozal')) {
                this.isSeasonless = !this.editableSeries.season;
            }
            if (!this.editableSeries.qualityByEpisodes) this.editableSeries.qualityByEpisodes = {};

            this.loadParserProfiles();

            if (this.editableSeries.source_type === 'torrent') {
                this.refreshSiteTorrents(); 
            }
        } catch (error) { 
            this.$emit('show-toast', error.message, 'danger');
        }  
    },
    async loadParserProfiles() {
        try {
            const response = await fetch('/api/parser-profiles');
            if (!response.ok) throw new Error('Ошибка загрузки профилей');
            this.parserProfiles = await response.json();
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
            const dbTorrentsRes = await fetch(`/api/series/${this.seriesId}/torrents/history`);
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
        this.$emit('saving-state', true);

        const pathHasChanged = this.editableSeries.save_path !== this.originalSavePath;

        // Собираем все остальные изменения, кроме пути
        const otherChangesPayload = { ...this.editableSeries };
        delete otherChangesPayload.save_path;

        let qualityString = '';
        const site = otherChangesPayload.site;
        if (site && (site.includes('anilibria') || site.includes('aniliberty'))) {
            qualityString = otherChangesPayload.quality;
        } else if (site && site.includes('astar')) {
            const qualitiesToSave = [], singleVersionQualities = new Set();
            this.sortedQualityOptionsKeys.forEach(episodes => { if (this.episodeQualityOptions[episodes] && this.episodeQualityOptions[episodes].length > 1) qualitiesToSave.push(otherChangesPayload.qualityByEpisodes[episodes]); });
            this.sortedQualityOptionsKeys.forEach(episodes => { if (this.episodeQualityOptions[episodes] && this.episodeQualityOptions[episodes].length === 1) singleVersionQualities.add(this.episodeQualityOptions[episodes][0]); });
            qualityString = [...qualitiesToSave, ...Array.from(singleVersionQualities)].join(';');
        }
        otherChangesPayload.quality = qualityString;
        otherChangesPayload.season = this.isSeasonless ? '' : otherChangesPayload.season;

        if (otherChangesPayload.source_type === 'vk_video') {
            otherChangesPayload.url = this.reconstructedUrl;
        }

        const savePromises = [];

        // Если путь изменился, создаем задачу на перемещение
        if (pathHasChanged) {
            const relocatePromise = fetch(`/api/series/${this.seriesId}/relocate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ new_path: this.editableSeries.save_path })
            }).then(res => res.json().then(data => { if (!res.ok) throw new Error(data.error || 'Ошибка создания задачи на перемещение'); return data; }));
            savePromises.push(relocatePromise);
        }

        // Всегда отправляем запрос на обновление остальных данных
        const updatePromise = fetch(`/api/series/${this.seriesId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(otherChangesPayload)
        }).then(res => res.json().then(data => { if (!res.ok) throw new Error(data.error || 'Ошибка сохранения свойств'); return data; }));
        savePromises.push(updatePromise);

        try {
            await Promise.all(savePromises);
            this.$emit('show-toast', 'Изменения успешно сохранены. Перемещение запущено в фоновом режиме, если путь был изменен.', 'success');
            this.$emit('series-updated');
            this.originalSavePath = this.editableSeries.save_path;
        } catch (error) {
            this.$emit('show-toast', `Ошибка сохранения: ${error.message}`, 'danger');
        } finally {
            this.$emit('saving-state', false);
        }
    },
  }
};