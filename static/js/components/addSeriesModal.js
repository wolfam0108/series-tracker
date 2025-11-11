// static/js/components/addSeriesModal.js

const AddSeriesModal = {
  template: `
    <div class="modal fade" ref="addModal" tabindex="-1" aria-labelledby="addModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-xl">
            <div class="modal-content modern-modal" style="max-height: 90vh; display: flex; flex-direction: column;">
                <div class="modal-header modern-header">
                    <h5 class="modal-title" id="addModalLabel"><i class="bi bi-plus-circle me-2"></i>Добавить новый сериал</h5>
                    <button type="button" class="btn-close modern-close" @click="close" aria-label="Close"></button>
                </div>
                <div class="modal-body modern-body" style="overflow-y: auto; flex-grow: 1;">
                    <div class="field-group">
                        <constructor-group :class="urlValidationClasses">
                            <div class="constructor-item item-label-icon" title="URL для парсинга"><i class="bi bi-link-45deg"></i></div>
                            <div class="constructor-item item-floating-label">
                                <input v-model.trim="newSeries.url" @input="debounceParseUrl" type="text" class="item-input" id="seriesUrl" placeholder=" ">
                                <label for="seriesUrl">URL для парсинга</label>
                            </div>
                        </constructor-group>
                        <div v-if="urlError" class="invalid-feedback mt-2">{{ urlError }}</div>
                    </div>
                    
                    <div v-if="parsing" class="animate-pulse">
                        <div class="modern-fieldset mt-4">
                            <div class="fieldset-header"><div class="skeleton-line short" style="height: 20px; width: 30%;"></div></div>
                            <div class="fieldset-content">
                                <div class="row">
                                    <div class="col-md-6"><div class="skeleton-line long mb-3"></div></div>
                                    <div class="col-md-6"><div class="skeleton-line long mb-3"></div></div>
                                    <div class="col-md-6"><div class="skeleton-line long mb-3"></div></div>
                                    <div class="col-md-6"><div class="skeleton-line long mb-3"></div></div>
                                </div>
                            </div>
                        </div>
                        <div class="modern-fieldset mt-4">
                            <div class="fieldset-header"><div class="skeleton-line short" style="height: 20px; width: 25%;"></div></div>
                            <div class="fieldset-content">
                                <div class="skeleton-line long"></div>
                            </div>
                        </div>
                    </div>

                    <div v-if="parsed || sourceType === 'vk_video'">
                        <div v-if="sourceType === 'vk_video'" class="modern-fieldset mt-4">
                            <div class="fieldset-header"><h6 class="fieldset-title mb-0">Настройки для VK Video</h6></div>
                            <div class="fieldset-content">
                                <div class="mb-4">
                                    <label class="modern-label">Режим поиска</label>
                                    <div class="btn-group w-100">
                                        <input type="radio" class="btn-check" name="vk_search_mode_add" id="vk_search_add" value="search" v-model="newSeries.vk_search_mode" autocomplete="off">
                                        <label class="btn btn-outline-primary" for="vk_search_add"><i class="bi bi-search me-2"></i>Быстрый поиск</label>
                                        <input type="radio" class="btn-check" name="vk_search_mode_add" id="vk_get_all_add" value="get_all" v-model="newSeries.vk_search_mode" autocomplete="off">
                                        <label class="btn btn-outline-primary" for="vk_get_all_add"><i class="bi bi-card-list me-2"></i>Полное сканирование</label>
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
                                                <input v-model.trim="vkChannelUrl" type="text" @input="autoCorrectSlash($event, 'vkChannelUrl')" class="item-input" id="vk-channel-url" placeholder=" ">
                                                <label for="vk-channel-url">Ссылка на канал</label>
                                            </div>
                                        </constructor-group>
                                    </div>
                                    <div class="col-md-6">
                                        <constructor-group :class="vkQueryClasses">
                                            <div class="constructor-item item-label-icon" title="Поисковые запросы"><i class="bi bi-search"></i></div>
                                            <div class="constructor-item item-floating-label">
                                                <input v-model.trim="vkQuery" type="text" class="item-input" id="vk-query" placeholder=" ">
                                                <label for="vk-query">Поисковые запросы (через /)</label>
                                            </div>
                                        </constructor-group>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="modern-fieldset mt-4">
                            <div class="fieldset-header"><h6 class="fieldset-title mb-0">Информация о сериале</h6></div>
                            <div class="fieldset-content">
                                <div class="row">
                                    <div class="col-md-6">
                                        <constructor-group :class="nameClasses">
                                            <div class="constructor-item item-label-icon" title="Название (RU)"><i class="bi bi-type"></i></div>
                                            <div class="constructor-item item-floating-label">
                                                <input v-model="newSeries.name" type="text" class="item-input" id="seriesNameRu" placeholder=" ">
                                                <label for="seriesNameRu">Название (RU)</label>
                                            </div>
                                        </constructor-group>
                                    </div>
                                    <div class="col-md-6">
                                        <constructor-group :class="nameEnClasses">
                                            <div class="constructor-item item-label-icon" title="Название (EN)"><i class="bi bi-translate"></i></div>
                                            <div class="constructor-item item-floating-label">
                                                <input v-model.trim="newSeries.name_en" type="text" class="item-input" id="seriesNameEn" placeholder=" ">
                                                <label for="seriesNameEn">Название (EN)</label>
                                            </div>
                                        </constructor-group>
                                    </div>
                                </div>
                                <div class="row mt-3">
                                    <div class="col-md-6">
                                        <constructor-group :class="savePathClasses">
                                            <div class="constructor-item item-label-icon" title="Путь сохранения"><i class="bi bi-folder2-open"></i></div>
                                            <div class="constructor-item item-floating-label">
                                                <input v-model.trim="newSeries.save_path" type="text" @input="autoCorrectSlash($event, 'newSeries', 'save_path')" class="item-input" id="savePath" placeholder=" ">
                                                <label for="savePath">Путь сохранения</label>
                                            </div>
                                        </constructor-group>
                                    </div>
                                    <div class="col-md-6">
                                        <constructor-group :class="[seasonClasses, { 'is-disabled': isSeasonless }]">
                                            <div class="constructor-item item-label-icon" title="Сезон"><i class="bi bi-collection-play"></i></div>
                                            <div class="constructor-item item-floating-label">
                                                <input v-model.trim="newSeries.season" type="text" class="item-input" id="season" placeholder=" " :disabled="isSeasonless">
                                                <label for="season">Сезон (формат s01)</label>
                                            </div>
                                        </constructor-group>
                                    </div>
                                </div>
                                
                                <div class="field-group mt-3">
                                    <constructor-group :class="parserProfileClasses">
                                        <div class="constructor-item item-label-icon item-label-text-icon" title="Профиль правил">
                                            <i class="bi bi-funnel-fill"></i>
                                            <span>Профиль правил</span>
                                        </div>
                                        <constructor-item-select :options="parserProfileOptions" v-model="newSeries.parser_profile_id"></constructor-item-select>
                                    </constructor-group>
                                </div>

                            </div>
                        </div>
                        
                        <div v-if="sourceType === 'vk_video' || (site && (site.includes('kinozal') || site.includes('rutracker')))" class="modern-fieldset mt-4">
                             <div class="fieldset-content py-3">
                                <div class="modern-form-check form-switch d-flex justify-content-center m-0">
                                    <input class="form-check-input" type="checkbox" role="switch" id="seasonlessSwitch" v-model="isSeasonless">
                                    <label class="modern-form-check-label" for="seasonlessSwitch">Раздача содержит несколько сезонов (или сезон не важен)</label>
                                </div>
                            </div>
                        </div>
                        
                        <div v-if="trackerInfo && trackerInfo.ui_features.quality_selector" class="modern-fieldset mt-4">
                            <div class="fieldset-header"><h6 class="fieldset-title mb-0">Выбор качества</h6></div>
                            <div class="fieldset-content">
                                <div v-if="trackerInfo.ui_features.quality_selector === 'anilibria'">
                                    <div v-if="isQualityOptionsReady && qualityOptionsAnilibria.length > 0" class="field-group">
                                        <constructor-group>
                                            <div class="constructor-item item-label">Качество</div>
                                            <constructor-item-select :options="qualityOptionsAnilibria" v-model="newSeries.qualityByEpisodes.all"></constructor-item-select>
                                        </constructor-group>
                                    </div>
                                    <div v-else-if="isQualityOptionsReady" class="text-danger">Качества не найдены</div>
                                </div>
                                
                                <div v-if="trackerInfo.ui_features.quality_selector === 'astar' && isQualityOptionsReady">
                                    <p class="text-muted small">Для релизов Astar можно выбрать предпочтительную версию для каждой группы эпизодов.</p>
                                    <div v-for="(episodes, index) in sortedQualityOptionsKeys" :key="episodes">
                                        <div v-if="episodeQualityOptions[episodes].length > 1" class="field-group">
                                            <constructor-group>
                                                <div class="constructor-item item-label">Эпизоды {{ episodes }}</div>
                                                <constructor-item-select :options="episodeQualityOptions[episodes].map(q => ({text: q, value: q}))" v-model="newSeries.qualityByEpisodes[episodes]"></constructor-item-select>
                                            </constructor-group>
                                        </div>
                                    </div>
                                    <div v-if="Object.values(episodeQualityOptions).every(o => o.length <= 1)" class="text-muted small">
                                        Для данного релиза нет альтернативных версий.
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="mt-4" v-if="sourceType === 'torrent' && parserData && parserData.torrents.length > 0">
                            <h6>Доступные торренты ({{ parserData.torrents.length }})</h6>
                            <div class="div-table table-site-torrents">
                                <div class="div-table-header">
                                    <div class="div-table-cell">ID</div>
                                    <div class="div-table-cell">Ссылка</div>
                                    <div class="div-table-cell">Дата</div>
                                    <div class="div-table-cell">Эпизоды</div>
                                    <div class="div-table-cell">Качество</div>
                                </div>
                                <div class="div-table-body">
                                    <transition-group name="list" tag="div">
                                        <div class="div-table-row" v-for="torrent in parserData.torrents" :key="torrent.torrent_id">
                                            <div class="div-table-cell">{{ torrent.torrent_id }}</div>
                                            <div class="div-table-cell">{{ torrent.link }}</div>
                                            <div class="div-table-cell">{{ torrent.date_time }}</div>
                                            <div class="div-table-cell">{{ torrent.episodes }}</div>
                                            <div class="div-table-cell">{{ torrent.quality }}</div>
                                        </div>
                                    </transition-group>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="modal-footer modern-footer">
                    <button class="btn btn-primary" @click="addSeries" :disabled="!canAddSeries || parsing">
                        <i class="bi bi-check-lg me-2"></i>Добавить
                    </button>
                    <button type="button" class="btn btn-secondary" @click="close">
                        <i class="bi bi-x-lg me-2"></i>Отмена
                    </button>
                </div>
            </div>
        </div>
    </div>
  `,
  data() {
    return { 
        modal: null, 
        // --- ИЗМЕНЕНИЕ: Добавлен vk_search_mode ---
        newSeries: { url: '', save_path: '', name: '', name_en: '', season: 's01', qualityByEpisodes: {}, parser_profile_id: null, vk_search_mode: 'search' }, 
        isSeasonless: false,
        urlError: '', 
        parsing: false, 
        parsed: false, 
        site: '', 
        parserData: null, 
        episodeQualityOptions: {}, 
        isQualityOptionsReady: false, 
        debounceTimeout: null,
        showValidation: false,
        sourceType: 'torrent',
        vkChannelUrl: '',
        vkQuery: '',
        parserProfiles: [],
        trackerInfo: null,
    };
  },
    emits: ['series-added', 'show-toast'],
  computed: {
    shouldShowValidation() {
        // Показываем валидацию если:
        // 1. Была попытка отправки формы
        if (this.showValidation) return true; 
        // 2. Выбран режим VK
        if (this.sourceType === 'vk_video') return true; 
        // 3. В режиме торрента URL уже успешно распознан
        if (this.sourceType === 'torrent' && this.parsed) return true; 
        
        return false;
    },
    // --- НАЧАЛО ИЗМЕНЕНИЙ: Полностью исправленная логика валидации ---
    isSeasonValid() { 
        if (this.isSeasonless || this.sourceType === 'vk_video') return true;
        return /^s\d{2}$/.test(this.newSeries.season.trim()); 
    },
    canAddSeries() { 
        const isBaseInfoValid = !!this.newSeries.name && !!this.newSeries.name_en && !!this.newSeries.save_path;
        if (this.sourceType === 'vk_video') {
            const isVkSpecificValid = !!this.vkChannelUrl && !!this.newSeries.parser_profile_id;
            const isSearchModeValid = this.newSeries.vk_search_mode === 'search' ? !!this.vkQuery : true;
            return isBaseInfoValid && isVkSpecificValid && isSearchModeValid;
        }
        return this.parsed && isBaseInfoValid && this.isSeasonValid; 
    },
    sortedQualityOptionsKeys() {
        if (!this.site.includes('astar')) return [];
        return sortEpisodeKeys(Object.keys(this.episodeQualityOptions));
    },
    
    // Вычисляемые свойства для классов валидации
    urlValidationClasses() {
        if (!this.shouldShowValidation) return {};

        // Если парсер вернул явную ошибку, поле невалидно
        if (this.urlError) {
            return { 'is-valid': false, 'is-invalid': true };
        }

        let isValid = false;
        if (this.sourceType === 'vk_video') {
            // В режиме VK поле URL считается валидным, если из него удалось извлечь ссылку на канал.
            // Валидность поискового запроса проверяется в его собственном поле.
            isValid = !!this.vkChannelUrl;
        } else { // В режиме торрента
            isValid = this.parsed;
        }
        
        return { 'is-valid': isValid, 'is-invalid': !isValid };
    },
    vkChannelUrlClasses() {
        if (!this.shouldShowValidation) return {};
        return { 'is-valid': !!this.vkChannelUrl, 'is-invalid': !this.vkChannelUrl };
    },
    vkQueryClasses() {
        if (!this.shouldShowValidation || this.newSeries.vk_search_mode !== 'search') return {};
        return { 'is-valid': !!this.vkQuery, 'is-invalid': !this.vkQuery };
    },
    parserProfileClasses() {
        if (!this.shouldShowValidation) return {};
        return { 'is-valid': !!this.newSeries.parser_profile_id, 'is-invalid': !this.newSeries.parser_profile_id };
    },
    nameClasses() {
        if (!this.shouldShowValidation) return {};
        return { 'is-valid': !!this.newSeries.name, 'is-invalid': !this.newSeries.name };
    },
    nameEnClasses() {
        if (!this.shouldShowValidation) return {};
        return { 'is-valid': !!this.newSeries.name_en, 'is-invalid': !this.newSeries.name_en };
    },
    savePathClasses() {
        if (!this.shouldShowValidation) return {};
        return { 'is-valid': !!this.newSeries.save_path, 'is-invalid': !this.newSeries.save_path };
    },
    seasonClasses() {
        if (!this.shouldShowValidation || this.isSeasonless || this.sourceType === 'vk_video') return {};
        return { 'is-valid': this.isSeasonValid, 'is-invalid': !this.isSeasonValid };
    },
     // Для выпадающих списков
    parserProfileOptions() {
        const options = this.parserProfiles.map(p => ({ text: p.name, value: p.id }));
        return [{ text: 'Выберите профиль...', value: null }, ...options];
    },
    qualityOptionsAnilibria() {
         if (!this.episodeQualityOptions.all) return [];
         return this.episodeQualityOptions.all.map(q => ({ text: q, value: q }));
    },
    // --- КОНЕЦ ИЗМЕНЕНИЙ ---
  },
  methods: {
    async open() {
      this.newSeries = { url: '', save_path: '', name: '', name_en: '', season: 's01', qualityByEpisodes: {}, parser_profile_id: null, vk_search_mode: 'search' };
      this.isSeasonless = false;
      this.urlError = ''; 
      this.parsing = false; 
      this.parsed = false; 
      this.site = '';
      this.parserData = null; 
      this.episodeQualityOptions = {}; 
      this.isQualityOptionsReady = false;
      this.showValidation = false;
      this.sourceType = 'torrent';
      this.vkChannelUrl = '';
      this.vkQuery = '';
      this.parserProfiles = [];
      
      if (!this.modal) { this.modal = new bootstrap.Modal(this.$refs.addModal); }
      this.modal.show();
      await this.loadParserProfiles();
    },
    close() { this.modal.hide(); },
    async loadParserProfiles() {
        try {
            const response = await fetch('/api/parser-profiles');
            if (!response.ok) throw new Error('Ошибка загрузки профилей парсера');
            this.parserProfiles = await response.json();
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        }
    },
    autoCorrectSlash(event, modelKey, fieldKey = null) {
        const start = event.target.selectionStart;
        const correctedValue = event.target.value.replace(/\\/g, '/');
    
        if (fieldKey) {
            this[modelKey][fieldKey] = correctedValue;
        } else {
            this[modelKey] = correctedValue;
        }
    
        this.$nextTick(() => {
            event.target.value = correctedValue;
            event.target.setSelectionRange(start, start);
    });
    },

    debounceParseUrl() {
        clearTimeout(this.debounceTimeout);
        this.debounceTimeout = setTimeout(() => { this.handleUrlInput(); }, 500);
    },
    handleUrlInput() {
        this.urlError = '';
        this.parsed = false;
        if (!this.newSeries.url) {
            this.sourceType = 'torrent';
            return;
        };

        if (this.newSeries.url.includes('vkvideo.ru')) {
            this.sourceType = 'vk_video';
            this.parsed = false;
            try {
                const url = new URL(this.newSeries.url);
                this.vkChannelUrl = `${url.protocol}//${url.hostname}${url.pathname}`;
                this.vkQuery = url.searchParams.get('q') || '';
            } catch(e) {
                this.urlError = 'Некорректный URL для VK Video';
                this.vkChannelUrl = '';
                this.vkQuery = '';
            }
        } else {
            this.sourceType = 'torrent';
            this.parseTorrentUrl();
        }
    },
    async parseTorrentUrl() {
        this.parsing = true;
        try {
            const urlObject = new URL(this.newSeries.url);
            this.site = urlObject.hostname.replace(/^(www\.)/g, '');
        } catch (e) {
            this.urlError = 'Некорректный URL';
            this.parsing = false;
            return;
        }
        try {
            const response = await fetch('/api/parse_url', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: this.newSeries.url }) });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Ошибка парсинга URL');
            
            this.trackerInfo = data.tracker_info;

            this.newSeries.name = data.title.ru || '';
            this.newSeries.name_en = data.title.en || '';
            this.parserData = data;
            Object.keys(this.episodeQualityOptions).forEach(key => delete this.episodeQualityOptions[key]);
            Object.keys(this.newSeries.qualityByEpisodes).forEach(key => delete this.newSeries.qualityByEpisodes[key]);
            
            if (this.site.includes('anilibria') || this.site.includes('aniliberty')) {
                this.episodeQualityOptions.all = [...new Set(data.torrents.filter(t => t.quality).map(t => t.quality))];
                this.newSeries.qualityByEpisodes.all = this.episodeQualityOptions.all[0] || '';
            } else if (this.site.includes('astar')) {
                const episodeVersions = {};
                data.torrents.forEach(t => {
                    if (t.episodes) {
                        if (!episodeVersions[t.episodes]) episodeVersions[t.episodes] = [];
                        if (t.quality) episodeVersions[t.episodes].push(t.quality);
                    }
                });
                Object.assign(this.episodeQualityOptions, episodeVersions);
                this.sortedQualityOptionsKeys.forEach(episodes => {
                    const options = this.episodeQualityOptions[episodes];
                    this.newSeries.qualityByEpisodes[episodes] = options.find(q => q !== 'old') || options[0] || '';
                });
            } else if (this.site.includes('rutracker')) {
                // Для RuTracker также может быть доступна информация о качестве
                this.episodeQualityOptions.all = [...new Set(data.torrents.filter(t => t.quality).map(t => t.quality))];
                if (this.episodeQualityOptions.all.length > 0) {
                    this.newSeries.qualityByEpisodes.all = this.episodeQualityOptions.all[0] || '';
                }
            }
            this.isQualityOptionsReady = true;
            this.parsed = true;
            this.showValidation = true;
        } catch (error) {
            this.urlError = error.message;
            // Даже при ошибке парсинга, если домен определен как торрент-трекер, мы все равно показываем поля
            // Оставляем this.parsed = false, но не скрываем форму
        } finally { this.parsing = false; }
    },
    async addSeries() {
        this.showValidation = true;
        if (!this.canAddSeries) {
            this.$emit('show-toast', 'Пожалуйста, заполните все обязательные поля корректно.', 'danger');
            return;
        }

        try {
            let qualityString = '';
            let payload = {
                ...this.newSeries,
                site: this.site,
                season: this.isSeasonless ? '' : this.newSeries.season,
            };

            if (this.sourceType === 'vk_video') {
                payload.source_type = 'vk_video';
                payload.url = `${this.vkChannelUrl}|${this.vkQuery}`;
                payload.site = 'vkvideo.ru';
                // --- ИЗМЕНЕНИЕ: vk_search_mode уже есть в payload из newSeries ---
            } else {
                payload.source_type = 'torrent';
                if (this.site.includes('anilibria') || this.site.includes('aniliberty')) {
                    qualityString = this.newSeries.qualityByEpisodes.all;
                } else if (this.site.includes('astar')) {
                    const qualitiesToSave = this.sortedQualityOptionsKeys
                        .filter(episodes => this.episodeQualityOptions[episodes].length > 1)
                        .map(episodes => this.newSeries.qualityByEpisodes[episodes]);
                    
                    const singleVersionQualities = new Set(
                        this.sortedQualityOptionsKeys
                            .filter(episodes => this.episodeQualityOptions[episodes].length === 1)
                            .map(episodes => this.episodeQualityOptions[episodes][0])
                    );
                    qualityString = [...qualitiesToSave, ...Array.from(singleVersionQualities)].join(';');
                } else if (this.site.includes('rutracker')) {
                    // Для RuTracker сохраняем выбранное качество, если оно есть
                    qualityString = this.newSeries.qualityByEpisodes.all || '';
                }
                payload.quality = qualityString;
                payload.torrents = this.parserData ? this.parserData.torrents : [];
            }
            
            const response = await fetch('/api/series', { 
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify(payload) 
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Ошибка добавления сериала');
            
            this.$emit('series-added');
            this.$emit('show-toast', 'Сериал успешно добавлен', 'success');
            this.close();
        } catch (error) { 
            this.urlError = error.message; 
            this.$emit('show-toast', error.message, 'danger');
        }
    }
  }
};
