// static/js/components/logsModal.js

const LogsModal = {
  components: {
    'logs-viewer-tab': LogsViewerTab,
    'settings-logging-tab': SettingsLoggingTab,
  },
  template: `
    <div class="modal fade" ref="logsModal" tabindex="-1" aria-labelledby="logsModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-xl">
            <div class="modal-content modern-modal" style="height: 90vh; display: flex; flex-direction: column;">
                <div class="modal-header modern-header">
                    <h5 class="modal-title" id="logsModalLabel"><i class="bi bi-journal-text me-2"></i>Просмотр логов</h5>
                    <ul class="nav modern-nav-tabs" role="tablist">
                        <li class="nav-item" role="presentation">
                            <button class="nav-link modern-tab-link active" data-bs-toggle="tab" data-bs-target="#viewer-tab-pane" type="button" role="tab" @click="setActiveTab('viewer')">
                                <i class="bi bi-card-list me-2"></i>Просмотр
                            </button>
                        </li>
                        <li class="nav-item" role="presentation">
                            <button class="nav-link modern-tab-link" data-bs-toggle="tab" data-bs-target="#settings-tab-pane" type="button" role="tab" @click="setActiveTab('settings')">
                                <i class="bi bi-toggles2 me-2"></i>Настройка
                            </button>
                        </li>
                    </ul>
                    <button type="button" class="btn-close modern-close" @click="close" aria-label="Close"></button>
                </div>

                <div class="modal-body modern-body flex-grow-1" style="overflow: hidden;">
                    <div class="tab-content h-100">
                        <div class="tab-pane fade show active h-100" id="viewer-tab-pane" role="tabpanel">
                            <logs-viewer-tab v-if="activeTab === 'viewer'" ref="viewerTab" @show-toast="emitToast"></logs-viewer-tab>
                        </div>
                        <div class="tab-pane fade h-100" id="settings-tab-pane" role="tabpanel">
                            <settings-logging-tab v-if="activeTab === 'settings'" ref="settingsTab" @show-toast="emitToast"></settings-logging-tab>
                        </div>
                    </div>
                </div>
                <div class="modal-footer modern-footer">
                    <button type="button" class="btn btn-secondary" @click="close">
                        <i class="bi bi-x-lg me-2"></i>Закрыть
                    </button>
                </div>
            </div>
        </div>
    </div>
  `,
  data() {
    return {
      modal: null,
      activeTab: 'viewer',
    };
  },
  emits: ['show-toast'],
  methods: {
    open() {
      if (!this.modal) {
        this.modal = new bootstrap.Modal(this.$refs.logsModal);
      }
      this.modal.show();
      // ---> ИЗМЕНЕНО: Явный вызов загрузки для вкладки по умолчанию <---
      this.setActiveTab('viewer');
      this.$nextTick(() => {
        const firstTab = this.$refs.logsModal.querySelector('[data-bs-target="#viewer-tab-pane"]');
        if (firstTab) {
            bootstrap.Tab.getOrCreateInstance(firstTab).show();
        }
      });
    },
    close() {
      this.modal.hide();
    },
    setActiveTab(tabName) {
        this.activeTab = tabName;
        // ---> ИЗМЕНЕНО: Явный вызов загрузки для активной вкладки <---
        this.$nextTick(() => {
            const tabRef = this.$refs[`${tabName}Tab`];
            if (tabRef && typeof tabRef.load === 'function') {
                tabRef.load();
            }
        });
    },
    emitToast(message, type) {
        this.$emit('show-toast', message, type);
    },
  }
};