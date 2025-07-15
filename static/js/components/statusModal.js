const StatusModal = {
  components: {
      'file-tree': FileTree,
      'series-composition-manager': SeriesCompositionManager,
  },
  template: `
    <div class="modal fade" ref="statusModal" tabindex="-1" aria-labelledby="statusModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-xl">
            <div class="modal-content modern-modal" style="max-height: 90vh; display: flex; flex-direction: column;">
                <div class="modal-header modern-header">
                    <h5 class="modal-title" id="statusModalLabel"><i class="bi bi-info-circle me-2"></i>Статус</h5>
                    
                    <ul class="nav modern-nav-tabs" id="statusTab" role="tablist">
                        <li class="nav-item" role="presentation">
                            <button class="nav-link modern-tab-link active" id="status-tab-generic" data-bs-toggle="tab" data-bs-target="#status-tab-pane-generic" type="button" role="tab" @click="activeTab = 'status'"><i class="bi bi-info-circle me-2"></i>Свойства</button>
                        </li>
                        <li v-if="selectedSeries.source_type === 'vk_video'" class="nav-item" role="presentation">
                            <button class="nav-link modern-tab-link" id="composition-tab-generic" data-bs-toggle="tab" data-bs-target="#composition-tab-pane-generic" type="button" role="tab" @click="activeTab = 'composition'"><i class="bi bi-diagram-3 me-2"></i>Композиция</button>
                        </li>
                        <li v-if="selectedSeries.source_type !== 'vk_video'" class="nav-item" role="presentation">
                            <button class="nav-link modern-tab-link" id="qb-torrents-tab-generic" data-bs-toggle="tab" data-bs-target="#qb-torrents-tab-pane-generic" type="button" role="tab" @click="activeTab = 'qb-torrents'"><i class="bi bi-download me-2"></i>Торренты qBit</button>
                        </li>
                        <li v-if="selectedSeries.source_type !== 'vk_video'" class="nav-item" role="presentation">
                            <button class="nav-link modern-tab-link" id="naming-tab-generic" data-bs-toggle="tab" data-bs-target="#naming-tab-pane-generic" type="button" role="tab" @click="onNamingTabClick"><i class="bi bi-tag me-2"></i>Нейминг</button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link modern-tab-link" id="history-tab-generic" data-bs-toggle="tab" data-bs-target="#history-tab-pane-generic" type="button" role="tab" @click="activeTab = 'history'"><i class="bi bi-clock-history me-2"></i>История</button>
                        </li>
                    </ul>
                    
                    <button type="button" class="btn-close modern-close" @click="close" aria-label="Close"></button>
                </div>
                <div class="modal-body modern-body" style="overflow-y: auto; flex-grow: 1;">
                    <div class="tab-content modern-tab-content" id="statusTabContent">
                        <div class="tab-pane fade show active" id="status-tab-pane-generic" role="tabpanel">
                            <div v-if="!selectedSeries.id" class="text-center"><div class="spinner-border" role="status"></div><p>Получение данных...</p></div>
                            <div v-else>
                                <div class="modern-fieldset mb-4">
                                    <div class="fieldset-header"><h6 class="fieldset-title mb-0">Информация о сериале ({{ selectedSeries.name }})</h6></div>
                                    <div class="fieldset-content">
                                        <div class="modern-form-group">
                                            <label class="modern-label">URL-адрес сериала</label>
                                            <input :value="selectedSeries.url" type="text" class="modern-input" readonly>
                                        </div>
                                        <div class="row">
                                            <div class="col-md-6">
                                                <div class="modern-form-group"><label class="modern-label">Название (RU)</label><input v-model="selectedSeries.name" type="text" class="modern-input"></div>
                                            </div>
                                            <div class="col-md-6">
                                                <div class="modern-form-group"><label class="modern-label">Название (EN)</label><input v-model="selectedSeries.name_en" type="text" class="modern-input"></div>
                                            </div>
                                            <div class="col-md-6">
                                                <div class="modern-form-group"><label class="modern-label">Путь сохранения</label><input v-model="selectedSeries.save_path" type="text" class="modern-input"></div>
                                            </div>
                                            <div class="col-md-6">
                                                <div class="modern-form-group"><label class="modern-label">Сезон</label><input v-model="selectedSeries.season" type="text" class="modern-input" :disabled="isSeasonless"></div>
                                            </div>
                                            <div class="col-md-6">
                                                <div class="modern-form-group mb-md-0"><label class="modern-label">Качество (ручной ввод)</label><input v-model="selectedSeries.quality_override" type="text" class="modern-input" placeholder="Напр: BDRip 1080p"></div>
                                            </div>
                                            <div class="col-md-6">
                                                <div class="modern-form-group mb-0"><label class="modern-label">Разрешение (ручной ввод)</label><input v-model="selectedSeries.resolution_override" type="text" class="modern-input" placeholder="Напр: 1080p"></div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                
                                <div v-if="selectedSeries.site && selectedSeries.site.includes('kinozal')" class="modern-fieldset mb-4">
                                    <div class="fieldset-content py-3">
                                        <div class="modern-form-check form-switch d-flex justify-content-center m-0">
                                            <input class="form-check-input" type="checkbox" role="switch" v-model="isSeasonless">
                                            <label class="modern-form-check-label">Раздача содержит несколько сезонов</label>
                                        </div>
                                    </div>
                                </div>

                                <div v-else-if="selectedSeries.site && (selectedSeries.site.includes('anilibria') || selectedSeries.site.includes('aniliberty'))" class="modern-fieldset mb-4">
                                    <div class="fieldset-header"><h6 class="fieldset-title mb-0">Выбор качества</h6></div>
                                    <div class="fieldset-content">
                                        <div class="modern-input-group">
                                            <span class="input-group-text">Качество</span>
                                            <select v-model="selectedSeries.quality" class="modern-select" :disabled="siteTorrentsLoading">
                                                <option v-for="opt in episodeQualityOptions" :value="opt">{{ opt }}</option>
                                            </select>
                                        </div>
                                    </div>
                                </div>

                                <div v-else-if="selectedSeries.site && selectedSeries.site.includes('astar')" class="modern-fieldset mb-4">
                                     <div class="fieldset-header"><h6 class="fieldset-title mb-0">Выбор качества</h6></div>
                                     <div class="fieldset-content">
                                        <div v-for="(episodes, index) in sortedQualityOptionsKeys" :key="episodes">
                                            <div v-if="episodeQualityOptions[episodes] && episodeQualityOptions[episodes].length > 1" class="modern-input-group" :class="{ 'mb-3': index < sortedQualityOptionsKeys.length - 1 }">
                                                <span class="input-group-text" style="min-width: 130px;">Эпизоды {{ episodes }}</span>
                                                <select v-model="selectedSeries.qualityByEpisodes[episodes]" class="modern-select">
                                                    <option v-for="option in episodeQualityOptions[episodes]" :value="option">{{ option }}</option>
                                                </select>
                                            </div>
                                        </div>
                                        <div v-if="!siteTorrentsLoading && Object.values(episodeQualityOptions).every(o => o.length <= 1)" class="text-muted small">Для данного релиза нет альтернативных версий.</div>
                                     </div>
                                </div>
                                
                                <div v-if="selectedSeries.source_type === 'torrent'">
                                    <h6>Торренты с сайта (согласно выбранному качеству)</h6>
                                    <div class="position-relative">
                                        <transition name="fade"><div v-if="siteTorrentsLoading" class="loading-overlay"></div></transition>
                                        <div class="div-table table-site-torrents">
                                            <div class="div-table-header">
                                                <div class="div-table-cell">ID</div><div class="div-table-cell">Ссылка</div><div class="div-table-cell">Дата</div><div class="div-table-cell">Эпизоды</div><div class="div-table-cell">Качество</div>
                                            </div>
                                            <div class="div-table-body">
                                                <transition-group name="list" tag="div">
                                                    <div v-for="t in filteredSiteTorrents" :key="t.torrent_id" class="div-table-row" :class="{'row-danger': siteDataIsStale && !siteTorrentsLoading}">
                                                        <div class="div-table-cell">{{ t.torrent_id }}</div><div class="div-table-cell">{{ t.link }}</div><div class="div-table-cell">{{ t.date_time }}</div><div class="div-table-cell">{{ t.episodes }}</div><div class="div-table-cell">{{ t.quality }}</div>
                                                    </div>
                                                </transition-group>
                                                <div v-if="!siteTorrentsLoading && filteredSiteTorrents.length === 0" class="div-table-row">
                                                    <div class="div-table-cell text-center" style="grid-column: 1 / -1;">Торренты не найдены.</div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    <small v-if="siteDataIsStale" class="text-danger d-block mt-2">Не удалось обновить данные с сайта, показана последняя сохраненная версия.</small>
                                </div>
                            </div>
                        </div>

                        <div class="tab-pane fade" id="composition-tab-pane-generic" role="tabpanel">
                            <series-composition-manager v-if="activeTab === 'composition'" :series-id="seriesId" @show-toast="emitToast" />
                        </div>

                        <div class="tab-pane fade" id="qb-torrents-tab-pane-generic" role="tabpanel">
                            <div class="d-flex justify-content-between align-items-center mb-3">
                                <h6>Торренты из qBittorrent</h6>
                                <button v-if="qbTorrents.length > 0 && !qbTorrentsLoading" class="modern-btn btn-danger btn-sm" @click="deleteAllTorrents"><i class="bi bi-trash me-2"></i>Удалить все из qBit</button>
                            </div>
                            <div class="position-relative">
                                <transition name="fade"><div v-if="qbTorrentsLoading" class="loading-overlay"></div></transition>
                                <div class="div-table table-qbit-info">
                                    <div class="div-table-header">
                                        <div class="div-table-cell">ID</div><div class="div-table-cell">Статус</div><div class="div-table-cell">Устарел?</div><div class="div-table-cell">Список файлов</div>
                                    </div>
                                    <div class="div-table-body">
                                        <transition-group name="list" tag="div">
                                            <div v-for="t in qbTorrents" :key="t.torrent_id" class="div-table-row" :class="{ 'row-danger': isObsolete(t) }">
                                                <div class="div-table-cell">{{ t.torrent_id }}</div><div class="div-table-cell">{{ translateStatus(t.state) }}</div><div class="div-table-cell">{{ isObsolete(t) ? 'Да' : 'Нет' }}</div><div class="div-table-cell"><file-tree :files="t.file_paths || []"></file-tree></div>
                                            </div>
                                        </transition-group>
                                    </div>
                                </div>
                            </div>
                            <p v-if="!qbTorrentsLoading && qbTorrents.length === 0">Торренты в qBittorrent не найдены.</p>
                        </div>

                        <div class="tab-pane fade" id="naming-tab-pane-generic" role="tabpanel">
                             <div v-if="!qbTorrents.length && !qbTorrentsLoading" class="text-center text-muted">Нет торрентов в qBittorrent для переименования.</div>
                             <div v-else>
                                <div v-for="torrent in qbTorrents" :key="torrent.qb_hash" class="div-table table-naming-preview mb-3 position-relative">
                                    <transition name="fade"><div v-if="renamingPreviews[torrent.qb_hash] && renamingPreviews[torrent.qb_hash].loading" class="loading-overlay"></div></transition>
                                    <div class="div-table-row" style="background-color: #e9ecef; font-weight: bold; grid-column: 1 / -1;"><div class="div-table-cell" style="flex: 100%;">Торрент ID: {{ torrent.torrent_id }}</div></div>
                                    <div class="div-table-header"><div class="div-table-cell">Файл на данный момент</div><div class="div-table-cell">Файл после переименования</div></div>
                                    <div class="div-table-body">
                                        <template v-if="renamingPreviews[torrent.qb_hash] && !renamingPreviews[torrent.qb_hash].loading">
                                            <div v-for="file in renamingPreviews[torrent.qb_hash].files" :key="file.original" class="div-table-row">
                                                <div class="div-table-cell">{{ file.original }}</div><div class="div-table-cell">{{ file.renamed }}</div>
                                            </div>
                                        </template>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="tab-pane fade" id="history-tab-pane-generic" role="tabpanel">
                             <h6>История торрентов в БД</h6>
                             <div class="position-relative">
                                <transition name="fade"><div v-if="historyLoading" class="loading-overlay"></div></transition>
                                 <div class="div-table table-torrents-history">
                                    <div class="div-table-header">
                                        <div class="div-table-cell">ID</div><div class="div-table-cell">Ссылка</div><div class="div-table-cell">Дата</div><div class="div-table-cell">Эпизоды</div><div class="div-table-cell">Качество</div><div class="div-table-cell">Активен?</div><div class="div-table-cell">Хеш qBit</div>
                                    </div>
                                    <div class="div-table-body">
                                        <transition-group name="list" tag="div">
                                            <div v-for="t in torrentHistory" :key="t.id" class="div-table-row">
                                                <div class="div-table-cell">{{ t.torrent_id }}</div><div class="div-table-cell">{{ t.link }}</div><div class="div-table-cell">{{ t.date_time }}</div><div class="div-table-cell">{{ t.episodes }}</div><div class="div-table-cell">{{ t.quality }}</div><div class="div-table-cell">{{ t.is_active ? 'Да' : 'Нет' }}</div><div class="div-table-cell">{{ t.qb_hash || 'N/A' }}</div>
                                            </div>
                                        </transition-group>
                                        <div v-if="!historyLoading && torrentHistory.length === 0" class="div-table-row">
                                            <div class="div-table-cell text-center" style="grid-column: 1 / -1;">История торрентов пуста.</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="modal-footer modern-footer">
                    <button v-if="activeTab === 'status'" class="modern-btn btn-primary" @click="updateSeries" :disabled="!selectedSeries.id || isBusy" :title="isBusy ? 'Нельзя сохранять во время активных операций' : 'Сохранить изменения'">
                        <i class="bi bi-check-lg me-2"></i>Сохранить
                    </button>
                    <button v-if="activeTab === 'naming'" class="modern-btn btn-success" @click="executeRename" :disabled="isRenaming || qbTorrents.length === 0">
                        <span v-if="isRenaming" class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                        <i v-else class="bi bi-pencil-square me-2"></i>
                        Переименовать все
                    </button>
                    <button class="modern-btn btn-secondary" @click="close"><i class="bi bi-x-lg me-2"></i>Закрыть</button>
                </div>
            </div>
        </div>
    </div>
  `,
  data() {
    return { 
        modal: null, seriesId: null, 
        siteTorrentsLoading: false, qbTorrentsLoading: false, historyLoading: false, isRenaming: false,
        siteDataIsStale: false, 
        selectedSeries: { qualityByEpisodes: {} }, 
        allSiteTorrents: [], qbTorrents: [], torrentHistory: [], renamingPreviews: {},
        episodeQualityOptions: {},
        isSeasonless: false,
        activeTab: 'status',
    };
  },
  emits: ['series-updated', 'show-toast'],
  computed: {
    isBusy() {
        const busyStates = ['scanning', 'metadata', 'renaming', 'checking', 'activation'];
        if (!this.selectedSeries || !this.selectedSeries.state) {
            return false;
        }
        try {
            const stateObj = JSON.parse(this.selectedSeries.state);
            if (typeof stateObj === 'object' && Object.keys(stateObj).length > 0) {
                const agentStates = Object.values(stateObj);
                const mappedStates = agentStates.map(stage => {
                    if (['awaiting_metadata', 'polling_for_size', 'awaiting_pause_before_rename'].includes(stage)) return 'metadata';
                    if (stage === 'rechecking') return 'checking';
                    return stage;
                });
                return mappedStates.some(state => busyStates.includes(state));
            }
        } catch(e) {
            return busyStates.includes(this.selectedSeries.state);
        }
        return false;
    },
    sortedQualityOptionsKeys() {
        if (!this.selectedSeries.site || !this.selectedSeries.site.includes('astar')) return [];
        return sortEpisodeKeys(Object.keys(this.episodeQualityOptions));
    },
    filteredSiteTorrents() {
        if (!this.selectedSeries.id || this.allSiteTorrents.length === 0) return [];
        
        const site = this.selectedSeries.site;
        if (site.includes('anilibria') || site.includes('aniliberty')) {
            return this.allSiteTorrents.filter(t => t.quality === this.selectedSeries.quality);
        }
        if (site.includes('astar')) {
            const allChoices = Object.values(this.selectedSeries.qualityByEpisodes);
            return this.allSiteTorrents.filter(torrent => {
                const versions = this.episodeQualityOptions[torrent.episodes] || [];
                if (versions.length <= 1) {
                     return allChoices.includes(torrent.quality);
                }
                const selectedQualityForGroup = this.selectedSeries.qualityByEpisodes[torrent.episodes];
                return torrent.quality === selectedQualityForGroup;
            });
        }
        return this.allSiteTorrents;
    }
  },
  methods: {
    async open(seriesId) {
        this.seriesId = seriesId;
        this.selectedSeries = { id: null, qualityByEpisodes: {} }; 
        this.allSiteTorrents = []; this.qbTorrents = []; this.torrentHistory = []; this.renamingPreviews = {};
        this.episodeQualityOptions = {};
        this.isSeasonless = false;
        this.activeTab = 'status';
        
        if (!this.modal) this.modal = new bootstrap.Modal(this.$refs.statusModal);
        this.modal.show();
        
        const firstTabEl = document.getElementById('status-tab-generic');
        if (firstTabEl) bootstrap.Tab.getOrCreateInstance(firstTabEl).show();
        
        try {
            const response = await fetch(`/api/series/${this.seriesId}`);
            if (!response.ok) throw new Error('Сериал не найден');
            const seriesData = await response.json();
            Object.assign(this.selectedSeries, seriesData);
            
            if (this.selectedSeries.site && this.selectedSeries.site.includes('kinozal')) {
                this.isSeasonless = !seriesData.season;
            }
            if (!this.selectedSeries.qualityByEpisodes) {
                this.selectedSeries.qualityByEpisodes = {};
            }

            if (this.selectedSeries.source_type === 'torrent') {
                this.refreshSiteTorrents(); 
                this.refreshQBTorrents();
            }
            this.loadHistory();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); this.close(); }
    },
    onNamingTabClick() {
        this.activeTab = 'naming';
        this.loadRenamingPreview();
    },
    close() {
        this.modal.hide();
    },
    isObsolete(qbTorrent) {
        if (this.filteredSiteTorrents.length === 0) return true;
        return !this.filteredSiteTorrents.some(t => t.torrent_id === qbTorrent.torrent_id);
    },
    _buildQualityOptions(torrents) {
        const site = this.selectedSeries.site;
        if (site.includes('anilibria') || site.includes('aniliberty')) {
            this.episodeQualityOptions = [...new Set(torrents.filter(t => t.quality).map(t => t.quality))];
            if (!this.selectedSeries.quality || !this.episodeQualityOptions.includes(this.selectedSeries.quality)) {
                 this.selectedSeries.quality = this.episodeQualityOptions.length > 0 ? this.episodeQualityOptions[0] : '';
            }
        } else if (site.includes('astar')) {
            Object.keys(this.episodeQualityOptions).forEach(key => delete this.episodeQualityOptions[key]);
            const episodeVersions = {};
            torrents.forEach(t => {
                if (t.episodes) {
                    if (!episodeVersions[t.episodes]) episodeVersions[t.episodes] = [];
                    if (t.quality) episodeVersions[t.episodes].push(t.quality);
                }
            });
            Object.assign(this.episodeQualityOptions, episodeVersions);
            
            const savedQualities = this.selectedSeries.quality ? this.selectedSeries.quality.split(';') : [];
            let qualityIndex = 0;
            
            this.sortedQualityOptionsKeys.forEach(episodes => {
                if (this.episodeQualityOptions[episodes].length > 1) {
                    this.selectedSeries.qualityByEpisodes[episodes] = savedQualities[qualityIndex] || this.episodeQualityOptions[episodes].find(q => q !== 'old') || this.episodeQualityOptions[episodes][0];
                    qualityIndex++;
                } else { this.selectedSeries.qualityByEpisodes[episodes] = this.episodeQualityOptions[episodes][0]; }
            });
        }
    },
    async refreshSiteTorrents() {
        this.siteTorrentsLoading = true; this.siteDataIsStale = false;
        try {
            const dbTorrentsRes = await fetch(`/api/series/${this.seriesId}/torrents`);
            if(dbTorrentsRes.ok) this.allSiteTorrents = await dbTorrentsRes.json();
            this._buildQualityOptions(this.allSiteTorrents);

            const response = await fetch('/api/parse_url', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: this.selectedSeries.url }) });
            const data = await response.json();
            if (data.success) { this.allSiteTorrents = data.torrents; this._buildQualityOptions(this.allSiteTorrents); } 
            else { this.siteDataIsStale = true; this.$emit('show-toast', `Ошибка парсинга: ${data.error}`, 'danger'); }
        } catch (error) { this.siteDataIsStale = true; this.$emit('show-toast', 'Ошибка сети при обновлении с сайта', 'danger');
        } finally { this.siteTorrentsLoading = false; }
    },
    async refreshQBTorrents() {
        this.qbTorrentsLoading = true;
        try {
            const response = await fetch(`/api/series/${this.seriesId}/qb_info`);
            const data = await response.json();
            if (response.ok) { this.qbTorrents = data; } 
            else { throw new Error(data.error || 'Ошибка загрузки из qBittorrent'); }
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); } 
        finally { this.qbTorrentsLoading = false; }
    },
    async loadHistory() {
        this.historyLoading = true;
        try {
            const response = await fetch(`/api/series/${this.seriesId}/torrents/history`);
            if (!response.ok) throw new Error('Ошибка загрузки истории торрентов');
            this.torrentHistory = await response.json();
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        } finally {
            this.historyLoading = false;
        }
    },
    async loadRenamingPreview() {
        if (this.qbTorrents.length === 0) return;
        for (const torrent of this.qbTorrents) {
            this.renamingPreviews[torrent.qb_hash] = { loading: true, files: [] };
            try {
                const response = await fetch('/api/rename/preview', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ files: torrent.file_paths, series_id: this.seriesId })
                });
                const previewData = await response.json();
                if (!response.ok) throw new Error(previewData.error || 'Ошибка предпросмотра');
                this.renamingPreviews[torrent.qb_hash].files = previewData;
            } catch (error) {
                this.$emit('show-toast', error.message, 'danger');
                this.renamingPreviews[torrent.qb_hash].files = [{ original: 'Ошибка загрузки', renamed: error.message }];
            } finally {
                this.renamingPreviews[torrent.qb_hash].loading = false;
            }
        }
    },
    async executeRename() {
        if (this.qbTorrents.length === 0) {
            this.$emit('show-toast', 'Нет торрентов для переименования.', 'warning');
            return;
        }
        this.isRenaming = true;
        let totalErrors = 0;
        for (const torrent of this.qbTorrents) {
            try {
                const response = await fetch(`/api/series/${this.seriesId}/torrents/${torrent.qb_hash}/rename`, { method: 'POST' });
                const data = await response.json();
                if (!response.ok || !data.success) throw new Error(data.error || `Ошибка торрента ID ${torrent.torrent_id}`);
            } catch (error) { totalErrors++; this.$emit('show-toast', error.message, 'danger'); }
        }
        if (totalErrors > 0) this.$emit('show-toast', `Переименование завершено с ${totalErrors} ошибками.`, 'warning');
        else this.$emit('show-toast', 'Все файлы успешно переименованы!', 'success');
        this.isRenaming = false;
        await this.refreshQBTorrents();
        await this.loadRenamingPreview();
    },
    async updateSeries() {
        try {
            let qualityString = '';
            const site = this.selectedSeries.site;

            if (site.includes('anilibria') || site.includes('aniliberty')) {
                qualityString = this.selectedSeries.quality;
            } else if (site.includes('astar')) {
                const qualitiesToSave = [];
                this.sortedQualityOptionsKeys.forEach(episodes => {
                    if (this.episodeQualityOptions[episodes] && this.episodeQualityOptions[episodes].length > 1) {
                        qualitiesToSave.push(this.selectedSeries.qualityByEpisodes[episodes]);
                    }
                });
                const singleVersionQualities = new Set();
                 this.sortedQualityOptionsKeys.forEach(episodes => {
                    if (this.episodeQualityOptions[episodes] && this.episodeQualityOptions[episodes].length === 1) {
                        singleVersionQualities.add(this.episodeQualityOptions[episodes][0]);
                    }
                });
                qualityString = [...qualitiesToSave, ...Array.from(singleVersionQualities)].join(';');
            }

            const payload = {
                name: this.selectedSeries.name,
                name_en: this.selectedSeries.name_en,
                save_path: this.selectedSeries.save_path,
                season: this.isSeasonless ? '' : this.selectedSeries.season,
                quality: qualityString,
                quality_override: this.selectedSeries.quality_override,
                resolution_override: this.selectedSeries.resolution_override,
            };

            const response = await fetch(`/api/series/${this.seriesId}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            if (response.ok) { this.$emit('show-toast', 'Изменения сохранены', 'success'); this.$emit('series-updated'); } 
            else { throw new Error((await response.json()).error || 'Ошибка сохранения'); }
        } catch (error) { this.$emit('show-toast', `Сетевая ошибка: ${error.message}`, 'danger'); }
    },
    async deleteAllTorrents() {
        if (!confirm(`Вы уверены, что хотите удалить ВСЕ торренты для сериала "${this.selectedSeries.name}" из qBittorrent?`)) return;
        try {
            const response = await fetch(`/api/series/${this.seriesId}/torrents`, { method: 'DELETE' });
            const data = await response.json();
            if (data.success) { this.$emit('show-toast', `Удалено ${data.deleted_count || 0} торрентов.`, 'success'); this.refreshQBTorrents(); } 
            else { throw new Error(data.error || 'Ошибка при удалении'); }
        } catch (error) { this.$emit('show-toast', `Сетевая ошибка: ${error.message}`, 'danger'); }
    },
    translateStatus(state) {
        const statuses = { 'uploading': 'Раздача', 'forcedUP': 'Раздача', 'downloading': 'Загрузка', 'forcedDL': 'Загрузка', 'metaDL': 'Загрузка', 'stalledUP': 'Ожидание', 'stalledDL': 'Ожидание', 'checkingUP': 'Проверка', 'checkingDL': 'Проверка', 'checkingResumeData': 'Проверка', 'pausedUP': 'Пауза', 'pausedDL': 'Пауза', 'queuedUP': 'В очереди', 'queuedDL': 'В очереди', 'allocating': 'Выделение места', 'moving': 'Перемещение', 'error': 'Ошибка', 'missingFiles': 'Нет файлов' };
        return statuses[state] || 'Неизвестно';
    },
    emitToast(message, type) {
        this.$emit('show-toast', message, type);
    }
  }
};