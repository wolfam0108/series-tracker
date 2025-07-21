const StatusTabProperties = {
  template: `
    <div>
        <div v-if="isLoading" class="text-center p-5"><div class="spinner-border" role="status"></div></div>
        <div v-else>
            <div class="modern-fieldset mb-4">
                <div class="fieldset-header"><h6 class="fieldset-title mb-0">Информация о сериале</h6></div>
                <div class="fieldset-content">
                    <div class="modern-form-group">
                        <label class="modern-label">URL-адрес сериала</label>
                        <input :value="series.url" type="text" class="modern-input" readonly>
                    </div>
                    <div class="row">
                        <div class="col-md-6"><div class="modern-form-group"><label class="modern-label">Название (RU)</label><input v-model="series.name" type="text" class="modern-input"></div></div>
                        <div class="col-md-6"><div class="modern-form-group"><label class="modern-label">Название (EN)</label><input v-model="series.name_en" type="text" class="modern-input"></div></div>
                        <div class="col-md-6"><div class="modern-form-group"><label class="modern-label">Путь сохранения</label><input v-model="series.save_path" type="text" class="modern-input"></div></div>
                        <div class="col-md-6"><div class="modern-form-group"><label class="modern-label">Сезон</label><input v-model="series.season" type="text" class="modern-input" :disabled="isSeasonless"></div></div>
                        <div class="col-md-6"><div class="modern-form-group mb-md-0"><label class="modern-label">Качество (ручной ввод)</label><input v-model="series.quality_override" type="text" class="modern-input" placeholder="Напр: BDRip 1080p"></div></div>
                        <div class="col-md-6"><div class="modern-form-group mb-0"><label class="modern-label">Разрешение (ручной ввод)</label><input v-model="series.resolution_override" type="text" class="modern-input" placeholder="Напр: 1080p"></div></div>
                    </div>
                </div>
            </div>
            
            <div v-if="series.source_type === 'torrent' && series.site && series.site.includes('kinozal')" class="modern-fieldset mb-4">
                <div class="fieldset-content py-3">
                    <div class="modern-form-check form-switch d-flex justify-content-center m-0">
                        <input class="form-check-input" type="checkbox" role="switch" v-model="isSeasonless">
                        <label class="modern-form-check-label">Раздача содержит несколько сезонов</label>
                    </div>
                </div>
            </div>

            <div v-if="series.source_type === 'torrent' && series.site && (series.site.includes('anilibria') || series.site.includes('aniliberty'))" class="modern-fieldset mb-4">
                 <div class="fieldset-header"><h6 class="fieldset-title mb-0">Выбор качества</h6></div>
                 <div class="fieldset-content">
                     <div class="modern-input-group">
                         <span class="input-group-text">Качество</span>
                         <select v-model="series.quality" class="modern-select" :disabled="siteTorrentsLoading">
                             <option v-for="opt in episodeQualityOptions" :value="opt">{{ opt }}</option>
                         </select>
                     </div>
                 </div>
            </div>
            
             <div v-if="series.source_type === 'torrent' && series.site && series.site.includes('astar')" class="modern-fieldset mb-4">
                 <div class="fieldset-header"><h6 class="fieldset-title mb-0">Выбор качества</h6></div>
                 <div class="fieldset-content">
                    <div v-for="(episodes, index) in sortedQualityOptionsKeys" :key="episodes">
                         <div v-if="episodeQualityOptions[episodes] && episodeQualityOptions[episodes].length > 1" class="modern-input-group" :class="{ 'mb-3': index < sortedQualityOptionsKeys.length - 1 }">
                             <span class="input-group-text" style="min-width: 130px;">Эпизоды {{ episodes }}</span>
                             <select v-model="series.qualityByEpisodes[episodes]" class="modern-select">
                                 <option v-for="option in episodeQualityOptions[episodes]" :value="option">{{ option }}</option>
                             </select>
                         </div>
                     </div>
                     <div v-if="!siteTorrentsLoading && Object.values(episodeQualityOptions).every(o => o.length <= 1)" class="text-muted small">Для данного релиза нет альтернативных версий.</div>
                 </div>
            </div>
            
            <div v-if="series.source_type === 'torrent'">
                <h6>Торренты с сайта (согласно выбранному качеству)</h6>
                <div class="position-relative">
                    <transition name="fade"><div v-if="siteTorrentsLoading" class="loading-overlay"></div></transition>
                    <div class="div-table table-site-torrents">
                        <div class="div-table-header"><div class="div-table-cell">ID</div><div class="div-table-cell">Ссылка</div><div class="div-table-cell">Дата</div><div class="div-table-cell">Эпизоды</div><div class="div-table-cell">Качество</div></div>
                        <div class="div-table-body"><transition-group name="list" tag="div">
                            <div v-for="t in filteredSiteTorrents" :key="t.torrent_id" class="div-table-row" :class="{'row-danger': siteDataIsStale && !siteTorrentsLoading}"><div class="div-table-cell">{{ t.torrent_id }}</div><div class="div-table-cell">{{ t.link }}</div><div class="div-table-cell">{{ t.date_time }}</div><div class="div-table-cell">{{ t.episodes }}</div><div class="div-table-cell">{{ t.quality }}</div></div>
                        </transition-group></div>
                    </div>
                </div>
                <small v-if="siteDataIsStale" class="text-danger d-block mt-2">Не удалось обновить данные с сайта, показана последняя сохраненная версия.</small>
            </div>
            
             <div class="d-flex justify-content-end mt-4">
                <button class="btn btn-primary" @click="updateSeries" :disabled="!series.id || isSaving">
                     <span v-if="isSaving" class="spinner-border spinner-border-sm me-2"></span>
                     <i v-else class="bi bi-check-lg me-2"></i>
                    Сохранить
                </button>
            </div>
        </div>
    </div>
  `,
  props: {
    seriesId: { type: Number, required: true },
    isActive: { type: Boolean, default: false },
  },
  emits: ['show-toast', 'series-updated'],
  data() {
    return {
      isLoading: true,
      isSaving: false,
      siteTorrentsLoading: false,
      siteDataIsStale: false,
      series: { qualityByEpisodes: {} },
      allSiteTorrents: [],
      episodeQualityOptions: {},
      isSeasonless: false,
    };
  },
  watch: {
    isActive(newVal) {
      if (newVal) this.load();
    }
  },
  computed: {
    sortedQualityOptionsKeys() {
        if (!this.series.site || !this.series.site.includes('astar')) return [];
        return sortEpisodeKeys(Object.keys(this.episodeQualityOptions));
    },
    filteredSiteTorrents() {
        if (!this.series.id || this.allSiteTorrents.length === 0) return [];
        const site = this.series.site;
        if (site.includes('anilibria') || site.includes('aniliberty')) {
            return this.allSiteTorrents.filter(t => t.quality === this.series.quality);
        }
        if (site.includes('astar')) {
            const allChoices = Object.values(this.series.qualityByEpisodes);
            return this.allSiteTorrents.filter(t => (this.episodeQualityOptions[t.episodes] || []).length <= 1 ? allChoices.includes(t.quality) : t.quality === this.series.qualityByEpisodes[t.episodes]);
        }
        return this.allSiteTorrents;
    }
  },
  methods: {
    async load() {
        this.isLoading = true;
        try {
            const response = await fetch(`/api/series/${this.seriesId}`);
            if (!response.ok) throw new Error('Сериал не найден');
            this.series = await response.json();
            
            if (this.series.site && this.series.site.includes('kinozal')) this.isSeasonless = !this.series.season;
            if (!this.series.qualityByEpisodes) this.series.qualityByEpisodes = {};

            if (this.series.source_type === 'torrent') this.refreshSiteTorrents(); 
        } catch (error) { this.$emit('show-toast', error.message, 'danger');
        } finally { this.isLoading = false; }
    },
    _buildQualityOptions(torrents) {
        const site = this.series.site;
        if (site.includes('anilibria') || site.includes('aniliberty')) {
            this.episodeQualityOptions = [...new Set(torrents.filter(t => t.quality).map(t => t.quality))];
            if (!this.series.quality || !this.episodeQualityOptions.includes(this.series.quality)) this.series.quality = this.episodeQualityOptions.length > 0 ? this.episodeQualityOptions[0] : '';
        } else if (site.includes('astar')) {
            Object.keys(this.episodeQualityOptions).forEach(key => delete this.episodeQualityOptions[key]);
            const episodeVersions = {};
            torrents.forEach(t => { if (t.episodes) { if (!episodeVersions[t.episodes]) episodeVersions[t.episodes] = []; if (t.quality) episodeVersions[t.episodes].push(t.quality); } });
            Object.assign(this.episodeQualityOptions, episodeVersions);
            const savedQualities = this.series.quality ? this.series.quality.split(';') : [];
            let qualityIndex = 0;
            this.sortedQualityOptionsKeys.forEach(episodes => {
                if (this.episodeQualityOptions[episodes].length > 1) {
                    this.series.qualityByEpisodes[episodes] = savedQualities[qualityIndex] || this.episodeQualityOptions[episodes].find(q => q !== 'old') || this.episodeQualityOptions[episodes][0];
                    qualityIndex++;
                } else { this.series.qualityByEpisodes[episodes] = this.episodeQualityOptions[episodes][0]; }
            });
        }
    },
    async refreshSiteTorrents() {
        this.siteTorrentsLoading = true; this.siteDataIsStale = false;
        try {
            const dbTorrentsRes = await fetch(`/api/series/${this.seriesId}/torrents`);
            if(dbTorrentsRes.ok) this.allSiteTorrents = await dbTorrentsRes.json();
            this._buildQualityOptions(this.allSiteTorrents);
            const response = await fetch('/api/parse_url', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: this.series.url }) });
            const data = await response.json();
            if (data.success) { this.allSiteTorrents = data.torrents; this._buildQualityOptions(this.allSiteTorrents); } 
            else { this.siteDataIsStale = true; this.$emit('show-toast', `Ошибка парсинга: ${data.error}`, 'warning'); }
        } catch (error) { this.siteDataIsStale = true; this.$emit('show-toast', 'Ошибка сети при обновлении с сайта', 'danger');
        } finally { this.siteTorrentsLoading = false; }
    },
    async updateSeries() {
        this.isSaving = true;
        try {
            let qualityString = ''; const site = this.series.site;
            if (site.includes('anilibria') || site.includes('aniliberty')) { qualityString = this.series.quality; } 
            else if (site.includes('astar')) {
                const qualitiesToSave = [], singleVersionQualities = new Set();
                this.sortedQualityOptionsKeys.forEach(episodes => { if (this.episodeQualityOptions[episodes] && this.episodeQualityOptions[episodes].length > 1) qualitiesToSave.push(this.series.qualityByEpisodes[episodes]); });
                this.sortedQualityOptionsKeys.forEach(episodes => { if (this.episodeQualityOptions[episodes] && this.episodeQualityOptions[episodes].length === 1) singleVersionQualities.add(this.episodeQualityOptions[episodes][0]); });
                qualityString = [...qualitiesToSave, ...Array.from(singleVersionQualities)].join(';');
            }
            const payload = {
                name: this.series.name, name_en: this.series.name_en, save_path: this.series.save_path,
                season: this.isSeasonless ? '' : this.series.season, quality: qualityString,
                quality_override: this.series.quality_override, resolution_override: this.series.resolution_override,
            };
            const response = await fetch(`/api/series/${this.seriesId}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            if (response.ok) { this.$emit('show-toast', 'Изменения сохранены', 'success'); this.$emit('series-updated'); } 
            else { throw new Error((await response.json()).error || 'Ошибка сохранения'); }
        } catch (error) { this.$emit('show-toast', `Сетевая ошибка: ${error.message}`, 'danger'); 
        } finally { this.isSaving = false; }
    },
  },
  mounted() {
    if (this.isActive) {
        this.load();
    }
  }
};