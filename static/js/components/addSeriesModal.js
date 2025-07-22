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
                    <div class="modern-form-group">
                        <label for="seriesUrl" class="modern-label">URL для парсинга</label>
                        <input v-model.trim="newSeries.url" @input="debounceParseUrl" type="text" 
                               class="modern-input" 
                               :class="{'is-invalid': urlError, 'is-valid': sourceType !== 'torrent' || parsed}" 
                               id="seriesUrl" placeholder="Вставьте URL с трекера или VK Video">
                        <div v-if="urlError" class="invalid-feedback">{{ urlError }}</div>
                    </div>
                    
                    <div v-if="parsing" class="text-center my-4">
                        <div class="spinner-border" role="status"><span class="visually-hidden">Получение информации...</span></div>
                        <p class="mt-2">Получение информации...</p>
                    </div>

                    <div v-if="parsed || sourceType === 'vk_video'">
                        <div v-if="sourceType === 'vk_video'">
                            <div class="modern-fieldset mt-4">
                                <div class="fieldset-header"><h6 class="fieldset-title mb-0">Настройки для VK Video</h6></div>
                                <div class="fieldset-content">
                                    <div class="row">
                                        <div class="col-md-6">
                                            <label class="modern-label">Ссылка на канал</label>
                                            <input v-model.trim="vkChannelUrl" type="text" class="modern-input" placeholder="https://vkvideo.ru/@канал">
                                        </div>
                                        <div class="col-md-6">
                                            <label class="modern-label">Поисковый запрос</label>
                                            <input v-model.trim="vkQuery" type="text" class="modern-input" placeholder="Название сериала">
                                        </div>
                                    </div>
                                    <div class="modern-form-group mt-3">
                                        <label class="modern-label">Профиль правил парсера</label>
                                        <select v-model="newSeries.parser_profile_id" class="modern-select">
                                            <option :value="null">-- Не выбрано --</option>
                                            <option v-for="profile in parserProfiles" :key="profile.id" :value="profile.id">{{ profile.name }}</option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="modern-fieldset mt-4">
                            <div class="fieldset-header"><h6 class="fieldset-title mb-0">Информация о сериале</h6></div>
                            <div class="fieldset-content">
                                <div class="row">
                                    <div class="col-md-6">
                                        <div class="modern-form-group">
                                            <label for="seriesNameRu" class="modern-label">Название (RU)</label>
                                            <input v-model="newSeries.name" type="text" 
                                                   class="modern-input" 
                                                   :class="{'is-invalid': !isNameValid && showValidation, 'is-valid': isNameValid && showValidation}" 
                                                   id="seriesNameRu" placeholder="Название на русском">
                                            <div v-if="!isNameValid && showValidation" class="invalid-feedback">Поле обязательно для заполнения</div>
                                        </div>
                                    </div>
                                    <div class="col-md-6">
                                        <div class="modern-form-group">
                                            <label for="seriesNameEn" class="modern-label">Название (EN)</label>
                                            <input v-model.trim="newSeries.name_en" type="text" 
                                                   class="modern-input" 
                                                   :class="{'is-invalid': !isNameEnValid && showValidation, 'is-valid': isNameEnValid && showValidation}" 
                                                   id="seriesNameEn" placeholder="Название на английском">
                                            <div v-if="!isNameEnValid && showValidation" class="invalid-feedback">Поле обязательно для заполнения</div>
                                        </div>
                                    </div>
                                    <div class="col-md-6">
                                        <div class="modern-form-group">
                                            <label for="savePath" class="modern-label">Путь сохранения</label>
                                            <input v-model.trim="newSeries.save_path" type="text" 
                                                   class="modern-input" 
                                                   :class="{'is-invalid': !isSavePathValid && showValidation, 'is-valid': isSavePathValid && showValidation}" 
                                                   id="savePath" placeholder="/path/to/save">
                                            <div v-if="!isSavePathValid && showValidation" class="invalid-feedback">Поле обязательно для заполнения</div>
                                        </div>
                                    </div>
                                    <div class="col-md-6">
                                        <div class="modern-form-group">
                                            <label for="season" class="modern-label">Сезон</label>
                                            <input v-model.trim="newSeries.season" type="text" 
                                                   class="modern-input" 
                                                   :class="{'is-invalid': !isSeasonValid && showValidation && !isSeasonless, 'is-valid': isSeasonValid && showValidation}" 
                                                   id="season" placeholder="s01" :disabled="isSeasonless">
                                            <div v-if="!isSeasonValid && showValidation && !isSeasonless" class="invalid-feedback">Формат: s01, s02, и т.д.</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div v-if="sourceType === 'vk_video' || (site && site.includes('kinozal'))" class="modern-fieldset mt-4">
                             <div class="fieldset-content py-3">
                                <div class="modern-form-check form-switch d-flex justify-content-center m-0">
                                    <input class="form-check-input" type="checkbox" role="switch" id="seasonlessSwitch" v-model="isSeasonless">
                                    <label class="modern-form-check-label" for="seasonlessSwitch">Раздача содержит несколько сезонов (или сезон не важен)</label>
                                </div>
                            </div>
                        </div>
                        
                        <div class="modern-fieldset mt-4" v-if="sourceType === 'torrent' && (site.includes('anilibria') || site.includes('aniliberty') || site.includes('astar'))">
                            <div class="fieldset-header"><h6 class="fieldset-title mb-0">Выбор качества</h6></div>
                            <div class="fieldset-content">
                                <div v-if="site.includes('anilibria') || site.includes('aniliberty')">
                                    <div v-if="isQualityOptionsReady && episodeQualityOptions.all && episodeQualityOptions.all.length > 0" class="modern-input-group">
                                        <span class="input-group-text">Качество</span>
                                        <select v-model="newSeries.qualityByEpisodes.all" class="modern-select" id="quality">
                                            <option v-for="option in episodeQualityOptions.all" :value="option">{{ option }}</option>
                                        </select>
                                    </div>
                                    <div v-else-if="isQualityOptionsReady" class="text-danger">Качества не найдены</div>
                                </div>
                                
                                <div v-if="site.includes('astar') && isQualityOptionsReady">
                                    <p class="text-muted small">Для релизов Astar можно выбрать предпочтительную версию для каждой группы эпизодов.</p>
                                    <div v-for="(episodes, index) in sortedQualityOptionsKeys" :key="episodes">
                                        <div v-if="episodeQualityOptions[episodes].length > 1" class="modern-input-group" :class="{ 'mb-3': index < sortedQualityOptionsKeys.length - 1 }">
                                            <span class="input-group-text" style="min-width: 130px;">Эпизоды {{ episodes }}</span>
                                            <select v-model="newSeries.qualityByEpisodes[episodes]" class="modern-select">
                                                <option v-for="option in episodeQualityOptions[episodes]" :value="option">{{ option }}</option>
                                            </select>
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
        newSeries: { url: '', save_path: '', name: '', name_en: '', season: 's01', qualityByEpisodes: {}, parser_profile_id: null }, 
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
    };
  },
  computed: {
    isSavePathValid() { return this.newSeries.save_path.trim().length > 0; },
    isNameValid() { return this.newSeries.name.trim().length > 0; },
    isNameEnValid() { return this.newSeries.name_en.trim().length > 0; },
    isSeasonValid() { 
        if (this.isSeasonless) return true;
        return /^s\d{2}$/.test(this.newSeries.season.trim()); 
    },
    canAddSeries() { 
        if (this.sourceType === 'vk_video') {
            return this.vkChannelUrl && this.newSeries.parser_profile_id && this.isNameValid && this.isNameEnValid && this.isSavePathValid;
        }
        return this.parsed && this.isSavePathValid && this.isNameValid && this.isNameEnValid && this.isSeasonValid; 
    },
    sortedQualityOptionsKeys() {
        if (!this.site.includes('astar')) return [];
        return sortEpisodeKeys(Object.keys(this.episodeQualityOptions));
    }
  },
  emits: ['series-added', 'show-toast'],
  methods: {
    async open() {
      this.newSeries = { url: '', save_path: '', name: '', name_en: '', season: 's01', qualityByEpisodes: {}, parser_profile_id: null };
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
            
            this.newSeries.name = data.title.ru || '';
            this.newSeries.name_en = data.title.en || '';
            this.parserData = data;
            Object.keys(this.episodeQualityOptions).forEach(key => delete this.episodeQualityOptions[key]);
            Object.keys(this.newSeries.qualityByEpisodes).forEach(key => delete this.newSeries.qualityByEpisodes[key]);
            
            // ---> ИЗМЕНЕНИЕ ЗДЕСЬ <---
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
            }
            this.isQualityOptionsReady = true; 
            this.parsed = true;
            this.showValidation = true;
        } catch (error) { 
            this.urlError = error.message;
            this.parsed = false; 
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
            } else {
                payload.source_type = 'torrent';
                // ---> И ИЗМЕНЕНИЕ ЗДЕСЬ <---
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