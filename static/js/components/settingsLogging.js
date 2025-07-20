const SettingsLoggingTab = {
  template: `
    <div class="settings-tab-content">
        <p class="text-muted small mb-3">
            Управляйте детализацией логов для разных частей приложения. Включение отладки для группы активирует логирование для всех модулей внутри неё.
        </p>
        <div v-if="isLoading" class="text-center p-5"><div class="spinner-border" role="status"></div></div>
        
        <div class="row" v-else>
            <div v-for="(modules, groupName) in moduleGroups" :key="groupName" class="col-md-6 mb-4">
                <div class="modern-fieldset h-100">
                    <div class="fieldset-header d-flex justify-content-between align-items-center">
                        <h6 class="fieldset-title mb-0">{{ groupName }}</h6>
                        <div class="form-check form-switch">
                            <input class="form-check-input" type="checkbox" role="switch" 
                                   :id="'group-switch-' + groupName" 
                                   v-model="groupStates[groupName].allEnabled"
                                   @change="saveGroupState(groupName, groupStates[groupName].allEnabled)">
                            <label class="form-check-label" :for="'group-switch-' + groupName"></label>
                        </div>
                    </div>
                    <div class="fieldset-content">
                        <ul class="list-unstyled mb-0">
                            <li v-for="module in modules" :key="module.name" class="mb-2">
                                <strong>{{ module.name }}:</strong>
                                <span class="text-muted">{{ module.description }}</span>
                            </li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    </div>
  `,
  data() {
    return {
      isLoading: true,
      moduleGroups: {},
    };
  },
  computed: {
    groupStates() {
        const states = {};
        for (const groupName in this.moduleGroups) {
            const modules = this.moduleGroups[groupName];
            const allEnabled = modules.every(m => m.enabled);
            states[groupName] = { allEnabled };
        }
        return states;
    }
  },
  emits: ['show-toast'],
  methods: {
    async load() {
        this.isLoading = true;
        try {
            const response = await fetch('/api/settings/debug_flags');
            if (!response.ok) throw new Error('Ошибка загрузки модулей логирования');
            this.moduleGroups = await response.json();
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        } finally {
            this.isLoading = false;
        }
    },
    async saveGroupState(groupName, isEnabled) {
        const modulesToUpdate = this.moduleGroups[groupName];
        for (const module of modulesToUpdate) {
            module.enabled = isEnabled;
            await this.saveFlag(module.name, isEnabled);
        }
        this.$emit('show-toast', `Логирование для группы "${groupName}" ${isEnabled ? 'включено' : 'выключено'}.`, 'info');
    },
    async saveFlag(moduleName, isEnabled) {
        try {
            const response = await fetch('/api/settings/debug_flags', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ module: moduleName, enabled: isEnabled })
            });
            if (!response.ok) throw new Error(`Ошибка сохранения флага для ${moduleName}`);
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
            const module = Object.values(this.moduleGroups).flat().find(m => m.name === moduleName);
            if(module) module.enabled = !isEnabled;
        }
    }
  },
  mounted() {
    this.load();
  }
};