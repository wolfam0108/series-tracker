const SettingsNamingTab = {
  components: {
    'settings-naming-series-tab': SettingsNamingSeriesTab,
    'settings-naming-season-tab': SettingsNamingSeasonTab,
    'settings-advanced-naming-tab': SettingsAdvancedNamingTab,
    'settings-naming-quality-tab': SettingsNamingQualityTab,
    'settings-naming-resolution-tab': SettingsNamingResolutionTab,
  },
  template: `
    <div class="settings-tab-content">
        <div class="sticky-sub-nav-wrapper">
            <ul class="nav nav-pills sub-nav-pills" id="pills-tab-naming" role="tablist">
                <li class="nav-item" role="presentation">
                    <button class="nav-link modern-tab-link active" data-bs-toggle="pill" data-bs-target="#pills-series" type="button" role="tab"><i class="bi bi-film me-2"></i>Паттерны серии</button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link modern-tab-link" data-bs-toggle="pill" data-bs-target="#pills-season" type="button" role="tab"><i class="bi bi-collection-play me-2"></i>Паттерны сезона</button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link modern-tab-link" data-bs-toggle="pill" data-bs-target="#pills-advanced" type="button" role="tab"><i class="bi bi-magic me-2"></i>Продвинутые паттерны</button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link modern-tab-link" data-bs-toggle="pill" data-bs-target="#pills-quality" type="button" role="tab"><i class="bi bi-badge-hd me-2"></i>Паттерны качества</button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link modern-tab-link" data-bs-toggle="pill" data-bs-target="#pills-resolution" type="button" role="tab"><i class="bi bi-aspect-ratio me-2"></i>Паттерны разрешения</button>
                </li>
            </ul>
        </div>
        <div class="tab-content naming-content-area" id="pills-tabContent-naming">
            <div class="tab-pane fade show active" id="pills-series" role="tabpanel">
                <settings-naming-series-tab @show-toast="emitToast"></settings-naming-series-tab>
            </div>
            <div class="tab-pane fade" id="pills-season" role="tabpanel">
                <settings-naming-season-tab @show-toast="emitToast"></settings-naming-season-tab>
            </div>
            <div class="tab-pane fade" id="pills-advanced" role="tabpanel">
                <settings-advanced-naming-tab @show-toast="emitToast"></settings-advanced-naming-tab>
            </div>
            <div class="tab-pane fade" id="pills-quality" role="tabpanel">
                <settings-naming-quality-tab @show-toast="emitToast"></settings-naming-quality-tab>
            </div>
            <div class="tab-pane fade" id="pills-resolution" role="tabpanel">
                <settings-naming-resolution-tab @show-toast="emitToast"></settings-naming-resolution-tab>
            </div>
        </div>
    </div>
  `,
  emits: ['show-toast'],
  methods: {
    emitToast(message, type) {
        this.$emit('show-toast', message, type);
    },
  }
};