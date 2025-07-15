const SettingsModal = {
  components: {
    'settings-auth-tab': SettingsAuthTab,
    'settings-naming-tab': SettingsNamingTab,
    'settings-agents-tab': SettingsAgentsTab,
    'settings-debug-tab': SettingsDebugTab,
    // --- ИЗМЕНЕНИЕ: Добавляем новый компонент ---
    'settings-parser-tab': SettingsParserTab,
  },
  props: {
    series: { type: Array, required: true },
    agentQueue: { type: Array, required: true }
  },
  template: `
    <div class="modal fade" ref="settingsModal" tabindex="-1" aria-labelledby="settingsModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-xl">
            <div class="modal-content modern-modal" style="max-height: 90vh; display: flex; flex-direction: column;">
                <div class="modal-header modern-header">
                    <h5 class="modal-title" id="settingsModalLabel">
                        <i class="bi bi-gear me-2"></i>
                        Настройки
                    </h5>
                    
                    <ul class="nav modern-nav-tabs" id="settingsTab" role="tablist">
                        <li class="nav-item" role="presentation">
                            <button class="nav-link modern-tab-link active" 
                                    id="auth-tab" data-bs-toggle="tab" data-bs-target="#auth-tab-pane" 
                                    type="button" role="tab" @click="setActiveTab('auth')">
                                <i class="bi bi-key me-2"></i>Авторизация
                            </button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link modern-tab-link" 
                                    id="naming-tab" data-bs-toggle="tab" data-bs-target="#naming-tab-pane" 
                                    type="button" role="tab" @click="setActiveTab('naming')">
                                <i class="bi bi-tag me-2"></i>Нейминг
                            </button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link modern-tab-link" 
                                    id="parser-tab" data-bs-toggle="tab" data-bs-target="#parser-tab-pane" 
                                    type="button" role="tab" @click="setActiveTab('parser')">
                                <i class="bi bi-funnel me-2"></i>Парсеры
                            </button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link modern-tab-link" 
                                    id="agents-tab" data-bs-toggle="tab" data-bs-target="#agents-tab-pane" 
                                    type="button" role="tab" @click="setActiveTab('agents')">
                                <i class="bi bi-motherboard me-2"></i>Агенты
                            </button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link modern-tab-link" 
                                    id="debug-tab" data-bs-toggle="tab" data-bs-target="#debug-tab-pane" 
                                    type="button" role="tab" @click="setActiveTab('debug')">
                                <i class="bi bi-bug me-2"></i>Отладка
                            </button>
                        </li>
                    </ul>

                    <button type="button" class="btn-close modern-close" @click="close" aria-label="Close"></button>
                </div>
                <div class="modal-body modern-body" style="overflow-y: auto; flex-grow: 1;">
                    <div class="tab-content modern-tab-content" id="settingsTabContent">
                        <div class="tab-pane fade show active" id="auth-tab-pane" role="tabpanel">
                            <settings-auth-tab ref="authTab" @show-toast="emitToast" @saving-state="onSavingStateChange"></settings-auth-tab>
                        </div>
                        <div class="tab-pane fade" id="naming-tab-pane" role="tabpanel">
                           <settings-naming-tab ref="namingTab" @show-toast="emitToast"></settings-naming-tab>
                        </div>
                        <div class="tab-pane fade" id="parser-tab-pane" role="tabpanel">
                           <settings-parser-tab ref="parserTab" @show-toast="emitToast"></settings-parser-tab>
                        </div>
                        <div class="tab-pane fade" id="agents-tab-pane" role="tabpanel">
                           <settings-agents-tab ref="agentsTab" :series="series" :agentQueue="agentQueue"></settings-agents-tab>
                        </div>
                        <div class="tab-pane fade" id="debug-tab-pane" role="tabpanel">
                           <settings-debug-tab ref="debugTab" @show-toast="emitToast" @reload-series="emitReload"></settings-debug-tab>
                        </div>
                    </div>
                </div>
                <div class="modal-footer modern-footer">
                     <button type="button" 
                             class="modern-btn btn-primary" 
                             @click="saveCurrentTab" 
                             :disabled="isSaving" 
                             v-if="activeTab === 'auth'">
                        <span v-if="isSaving" class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                        <i v-else class="bi bi-check-lg me-2"></i>
                        {{ isSaving ? 'Сохранение...' : 'Сохранить' }}
                    </button>
                    <button type="button" class="modern-btn btn-secondary" @click="close">
                        <i class="bi bi-x-lg me-2"></i>
                        Закрыть
                    </button>
                </div>
            </div>
        </div>
    </div>
  `,
  data() {
    return {
      modal: null,
      isSaving: false,
      activeTab: 'auth',
    };
  },
  emits: ['show-toast', 'reload-series'],
  methods: {
    open() {
      if (!this.modal) this.modal = new bootstrap.Modal(this.$refs.settingsModal);
      this.modal.show();
      this.setActiveTab('auth');
      const firstTabEl = document.getElementById('auth-tab');
      if (firstTabEl) bootstrap.Tab.getOrCreateInstance(firstTabEl).show();
    },
    close() { 
      if (this.$refs.debugTab) {
        this.$refs.debugTab.unload();
      }
      this.modal.hide(); 
    },
    setActiveTab(tabName) {
        this.activeTab = tabName;
        // Загружаем данные для активной вкладки
        if (this.$refs[`${tabName}Tab`]) {
            this.$refs[`${tabName}Tab`].load();
        }
        // Выгружаем данные для неактивной вкладки отладки
        if(tabName !== 'debug' && this.$refs.debugTab) {
            this.$refs.debugTab.unload();
        }
    },
    saveCurrentTab() {
      if (this.activeTab === 'auth') {
        this.$refs.authTab.save();
      }
      // В будущем здесь будет сохранение и для других вкладок
    },
    emitToast(message, type) {
      this.$emit('show-toast', message, type);
    },
    emitReload() {
      this.$emit('reload-series');
    },
    onSavingStateChange(isSaving) {
      this.isSaving = isSaving;
    }
  }
};