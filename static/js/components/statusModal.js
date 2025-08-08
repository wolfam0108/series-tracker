const StatusModal = {
  components: {
      'series-composition-manager': SeriesCompositionManager,
      'chapter-manager': ChapterManager,
      'status-tab-properties': StatusTabProperties,
      'status-tab-history': StatusTabHistory,
      'status-tab-torrent-composition': StatusTabTorrentComposition,
  },
  template: `
    <div class="modal fade" ref="statusModal" tabindex="-1" aria-labelledby="statusModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-xl" :class="{'modal-fullscreen': isFullscreen}">
            <div class="modal-content modern-modal" style="max-height: 90vh; display: flex; flex-direction: column;">
                <div class="modal-header modern-header">
                    <h5 class="modal-title" id="statusModalLabel"><i class="bi bi-info-circle me-2"></i>Статус</h5>
                    
                    <ul class="nav modern-nav-tabs" id="statusTab" role="tablist">
                        <li class="nav-item" role="presentation">
                            <button class="nav-link modern-tab-link active" data-bs-toggle="tab" data-bs-target="#pane-properties" type="button" role="tab" @click="setActiveTab('properties')"><i class="bi bi-info-circle me-2"></i>Свойства</button>
                        </li>
                        <li v-if="series.source_type === 'vk_video'" class="nav-item" role="presentation">
                            <button class="nav-link modern-tab-link" data-bs-toggle="tab" data-bs-target="#pane-composition" type="button" role="tab" @click="setActiveTab('composition')"><i class="bi bi-diagram-3 me-2"></i>Композиция</button>
                        </li>
                        <li v-if="series.source_type === 'vk_video'" class="nav-item" role="presentation">
                            <button class="nav-link modern-tab-link" data-bs-toggle="tab" data-bs-target="#pane-slicing" type="button" role="tab" @click="setActiveTab('slicing')"><i class="bi bi-scissors me-2"></i>Нарезка</button>
                        </li>
                        <li v-if="series.source_type === 'torrent'" class="nav-item" role="presentation">
                            <button class="nav-link modern-tab-link" data-bs-toggle="tab" data-bs-target="#pane-torrent-composition" type="button" role="tab" @click="setActiveTab('torrent-composition')"><i class="bi bi-diagram-3 me-2"></i>Композиция</button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link modern-tab-link" data-bs-toggle="tab" data-bs-target="#pane-history" type="button" role="tab" @click="setActiveTab('history')"><i class="bi bi-clock-history me-2"></i>История</button>
                        </li>
                    </ul>
                    
                    <button type="button" class="btn-close modern-close" @click="close" aria-label="Close"></button>
                </div>
                <div class="modal-body modern-body" style="overflow-y: auto; flex-grow: 1;">
                    <div v-if="!series.id" class="text-center p-5"><div class="spinner-border" role="status"></div></div>
                    <div v-else class="tab-content modern-tab-content" id="statusTabContent">
                        
                    <div class="tab-pane fade show active" id="pane-properties" role="tabpanel">
                            <status-tab-properties 
                                ref="propertiesTab" 
                                v-if="seriesId" 
                                :series-id="seriesId" 
                                :is-active="activeTab === 'properties'" 
                                @show-toast="emitToast" 
                                @series-updated="emitSeriesUpdated"
                                @saving-state="onSavingStateChange" 
                            />
                        </div>

                        <div class="tab-pane fade" id="pane-composition" role="tabpanel">
                            <series-composition-manager ref="compositionTab" v-if="seriesId" :series-id="seriesId" :series="series" :is-active="activeTab === 'composition'" @show-toast="emitToast" />
                        </div>

                        <div class="tab-pane fade" id="pane-slicing" role="tabpanel">
                            <chapter-manager v-if="seriesId" :series-id="seriesId" :is-active="activeTab === 'slicing'" @show-toast="emitToast" />
                        </div>

                        <div class="tab-pane fade" id="pane-torrent-composition" role="tabpanel">
                             <status-tab-torrent-composition v-if="seriesId" :series-id="seriesId" :is-active="activeTab === 'torrent-composition'" @show-toast="emitToast" />
                        </div>
                        
                        <div class="tab-pane fade" id="pane-history" role="tabpanel">
                             <status-tab-history v-if="seriesId" :series-id="seriesId" :source-type="series.source_type" :is-active="activeTab === 'history'" @show-toast="emitToast" />
                        </div>
                    </div>
                </div>
                <div class="modal-footer modern-footer">
                    <button v-if="activeTab === 'properties'" class="btn btn-primary" @click="saveProperties" :disabled="isSaving">
                        <span v-if="isSaving" class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                        <i v-else class="bi bi-check-lg me-2"></i>
                        {{ isSaving ? 'Сохранение...' : 'Сохранить' }}
                    </button>
                    <button class="btn btn-secondary" @click="close"><i class="bi bi-x-lg me-2"></i>Закрыть</button>
                </div>
            </div>
        </div>
    </div>
  `,
  data() {
    return { 
        modal: null, 
        seriesId: null, 
        series: {},
        activeTab: 'properties',
        isFullscreen: false,
        isSaving: false,
    };
  },
  emits: ['series-updated', 'show-toast'],
  methods: {
    setActiveTab(tabName) {
        this.activeTab = tabName;
        this.isFullscreen = (tabName === 'history');

        // Используем $nextTick, чтобы убедиться, что компонент видим перед вызовом
        this.$nextTick(() => {
            // Даем явную команду на обновление при каждом переключении на вкладку
            if (tabName === 'composition' && this.$refs.compositionTab) {
                this.$refs.compositionTab.initialize();
            }
        });
    },
    async open(seriesId) {
        this.seriesId = seriesId;
        this.series = {}; 
        this.activeTab = 'properties';
        this.isFullscreen = false;
        
        if (!this.modal) this.modal = new bootstrap.Modal(this.$refs.statusModal);
        this.modal.show();
        
        const firstTabEl = this.$refs.statusModal.querySelector('.modern-tab-link');
        if (firstTabEl) bootstrap.Tab.getOrCreateInstance(firstTabEl).show();
        
        try {
            const response = await fetch(`/api/series/${this.seriesId}`);
            if (!response.ok) throw new Error('Сериал не найден');
            this.series = await response.json();
        } catch (error) { 
            this.emitToast(error.message, 'danger'); 
            this.close(); 
        }
    },
    close() {
        this.modal.hide();
    },
    onRenamingComplete() {
        // Вызываем метод дочернего компонента, если он активен
        if (this.activeTab === 'composition' && this.$refs.compositionTab) {
            this.$refs.compositionTab.onRenamingComplete();
        }
    },    
    // --- НОВЫЙ МЕТОД: Вызывает метод сохранения в дочернем компоненте ---
    saveProperties() {
        if (this.$refs.propertiesTab) {
            this.$refs.propertiesTab.updateSeries();
        }
    },
    emitToast(message, type) {
        this.$emit('show-toast', message, type);
    },
    emitSeriesUpdated() {
        this.$emit('series-updated');
    },
        onSavingStateChange(savingStatus) {
        this.isSaving = savingStatus;
    },

    saveProperties() {
        if (this.$refs.propertiesTab) {
            this.$refs.propertiesTab.updateSeries();
        }
    }
  }
};
