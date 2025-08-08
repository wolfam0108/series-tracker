const SettingsLoggingTab = {
  template: `
    <div class="settings-tab-content h-100" style="overflow-y: auto; padding-top: 1rem;">
        <div class="modern-fieldset mb-4">
            <div class="fieldset-header">
                <h6 class="fieldset-title mb-0">Детализация логов</h6>
            </div>
            <div class="fieldset-content">
                <p class="text-muted small mb-3">
                    Управляйте детализацией логов для разных частей приложения. Включение отладки для группы активирует логирование для всех модулей внутри неё.
                </p>
                <div v-if="isLoading" class="text-center p-5"><div class="spinner-border" role="status"></div></div>
                
                <div class="row" v-else>
                    <div v-for="(modules, groupName) in loggingModuleGroups" :key="groupName" class="col-md-6 mb-4">
                        <div class="modern-fieldset h-100">
                            <div class="fieldset-header d-flex justify-content-between align-items-center">
                                <h6 class="fieldset-title mb-0">{{ groupName }}</h6>
                                <div class="form-check form-switch">
                                    <input class="form-check-input" type="checkbox" role="switch" 
                                           :id="'group-switch-' + groupName" 
                                           :checked="areAllModulesEnabled(groupName)"
                                           @change="saveGroupState(groupName, $event.target.checked)">
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
        </div>

        <div class="modern-fieldset">
            <div class="fieldset-header">
                <h6 class="fieldset-title mb-0">Сохранение файлов отладки</h6>
            </div>
            <div class="fieldset-content">
                 <p class="text-muted small mb-3">
                    Включите опцию, чтобы при сканировании парсер или скрейпер сохранял полученные сырые данные (HTML/JSON) в папку отладки. Это полезно для анализа проблем.
                </p>
                <div v-if="isLoading" class="text-center p-3"><div class="spinner-border spinner-border-sm" role="status"></div></div>
                <div v-else class="row">
                    <div v-for="flag in fileDumpFlags" :key="flag.name" class="col-md-4">
                        <div class="modern-form-check form-switch">
                            <input class="form-check-input" type="checkbox" role="switch" 
                                   :id="'flag-switch-' + flag.name" 
                                   v-model="flag.enabled"
                                   @change="saveFlag(flag.name, flag.enabled)">
                            <label class="modern-form-check-label" :for="'flag-switch-' + flag.name">{{ flag.description }}</label>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
  `,
  data() {
    return {
      isLoading: true,
      loggingModuleGroups: {},
      fileDumpFlags: [],
    };
  },
  emits: ['show-toast'],
  methods: {
    async load() {
        this.isLoading = true;
        try {
            const response = await fetch('/api/settings/debug_flags');
            if (!response.ok) throw new Error('Ошибка загрузки модулей логирования');
            const data = await response.json();
            this.loggingModuleGroups = data.logging_modules;
            this.fileDumpFlags = data.file_dump_flags;
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        } finally {
            this.isLoading = false;
        }
    },
    areAllModulesEnabled(groupName) {
        const modules = this.loggingModuleGroups[groupName];
        if (!modules) return false;
        return modules.every(m => m.enabled);
    },
    async saveGroupState(groupName, isEnabled) {
        const modulesToUpdate = this.loggingModuleGroups[groupName];
        // Временно обновляем UI для мгновенной реакции
        modulesToUpdate.forEach(m => { m.enabled = isEnabled; });
        
        try {
            for (const module of modulesToUpdate) {
                await this.saveFlag(module.name, isEnabled);
            }
            this.$emit('show-toast', `Логирование для группы "${groupName}" ${isEnabled ? 'включено' : 'выключено'}.`, 'info');
        } catch (error) {
            // В случае ошибки откатываем изменения в UI
            this.load();
        }
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
            // Откатываем состояние переключателя в UI в случае ошибки
            const flag = [...Object.values(this.loggingModuleGroups).flat(), ...this.fileDumpFlags].find(f => f.name === moduleName);
            if(flag) flag.enabled = !isEnabled;
        }
    }
  },
  mounted() {
    this.load();
  }
};