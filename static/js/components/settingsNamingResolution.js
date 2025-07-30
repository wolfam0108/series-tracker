const SettingsNamingResolutionTab = {
  name: 'SettingsNamingResolutionTab',
  template: `
    <div class="settings-tab-content">
        <div class="modern-fieldset mb-4">
             <div class="fieldset-header">
                <h6 class="fieldset-title mb-0">Стандарты разрешения</h6>
            </div>
            <div class="fieldset-content">
                <p class="text-muted small mb-3">Определите стандартизированные значения (например, '1080p') и поисковые паттерны для них. Используйте '*' для любого текста.</p>
                
                <div class="field-group">
                    <constructor-group>
                        <div class="constructor-item item-label-icon" title="Новый стандарт"><i class="bi bi-plus-circle"></i></div>
                        <div class="constructor-item item-floating-label">
                            <input type="text" class="item-input" id="resolution-standard-new" placeholder=" " v-model="newPattern.standard_value" @keyup.enter="addPattern">
                            <label for="resolution-standard-new">Новый стандарт разрешения, напр: 1080p</label>
                        </div>
                        <div class="constructor-item item-button-group">
                            <button class="btn-icon btn-confirm btn-text-icon" @click="addPattern" :disabled="!newPattern.standard_value">
                                <i class="bi bi-plus-lg"></i>
                                <span>Добавить</span>
                            </button>
                        </div>
                    </constructor-group>
                </div>

                <div v-for="(rp, index) in patterns" :key="rp.id" class="list-card quality-standard-card mb-3">
                    <div class="list-card-header">
                        <div class="standard-title">
                            <div class="form-check form-switch">
                                <input class="form-check-input" type="checkbox" role="switch" v-model="rp.is_active" @change="updatePattern(rp)">
                                <strong class="ms-2">{{ rp.standard_value }}</strong>
                            </div>
                        </div>
                        <div class="standard-controls">
                           <button class="control-btn" @click="movePattern(index, -1)" :disabled="index === 0" title="Поднять приоритет"><i class="bi bi-chevron-up"></i></button>
                           <button class="control-btn" @click="movePattern(index, 1)" :disabled="index === patterns.length - 1" title="Понизить приоритет"><i class="bi bi-chevron-down"></i></button>
                           <button class="control-btn text-danger" @click="deletePattern(rp.id)" title="Удалить стандарт"><i class="bi bi-trash"></i></button>
                        </div>
                    </div>
                    <div class="list-card-body">
                        <div class="search-patterns-list mb-2" v-if="rp.search_patterns.length > 0">
                            <div v-for="sp in rp.search_patterns" :key="sp.id" class="search-pattern-item">
                               <code>{{ sp.pattern }}</code>
                               <button class="pattern-remove-btn" @click="deleteSearchPattern(sp.id)" title="Удалить поисковый паттерн">
                                   <i class="bi bi-x"></i>
                               </button>
                            </div>
                        </div>
                        <constructor-group>
                            <div class="constructor-item item-label-icon" title="Поисковый паттерн"><i class="bi bi-file-earmark-text"></i></div>
                            <div class="constructor-item item-floating-label">
                                <input type="text" class="item-input" placeholder=" " v-model="rp.newSearchPattern" @keyup.enter="addSearchPattern(rp)" :ref="'patternInput' + rp.id">
                                <label>Новый поисковый паттерн...</label>
                            </div>
                            <div class="constructor-item item-button-group">
                                <button class="btn-icon btn-settings" @click="insertSymbol(rp, '*')" title="Вставить '*'">*</button>
                                <button class="btn-icon btn-add btn-text-icon" @click="addSearchPattern(rp)" :disabled="!rp.newSearchPattern">
                                    <i class="bi bi-plus-lg"></i>
                                </button>
                            </div>
                        </constructor-group>
                    </div>
                </div>
                
                <div v-if="!patterns.length" class="empty-state">Стандартов разрешения пока нет.</div>
            </div>
        </div>
        
         <div class="modern-fieldset">
            <div class="fieldset-header">
                <h6 class="fieldset-title mb-0">Тестирование паттернов разрешения</h6>
            </div>
            <div class="fieldset-content">
                <div class="field-group">
                    <constructor-group>
                        <div class="constructor-item item-label-icon" title="Имя файла"><i class="bi bi-file-earmark-text"></i></div>
                        <input type="text" class="constructor-item item-input" v-model="testData.filename" placeholder="Введите имя файла для теста..." @keyup.enter="testPatterns">
                        <div class="constructor-item item-button-group">
                            <button class="btn-icon btn-search btn-text-icon" @click="testPatterns" :disabled="!testData.filename">
                                <i class="bi bi-check-circle"></i>
                                <span>Проверить</span>
                            </button>
                        </div>
                    </constructor-group>
                </div>
                <div v-if="testData.result" class="alert alert-info mt-3"><strong>Результат:</strong> {{ testData.result }}</div>
            </div>
        </div>
    </div>
  `,
  data() {
    return {
      patterns: [],
      newPattern: { standard_value: '' },
      testData: { filename: '', result: null },
    };
  },
  emits: ['show-toast'],
  methods: {
    insertSymbol(resolutionPattern, symbol) {
        const inputEl = this.$refs['patternInput' + resolutionPattern.id][0];
        const start = inputEl.selectionStart;
        const end = inputEl.selectionEnd;
        let currentVal = resolutionPattern.newSearchPattern || '';
        resolutionPattern.newSearchPattern = currentVal.substring(0, start) + symbol + currentVal.substring(end);
        inputEl.focus();
        this.$nextTick(() => { inputEl.selectionStart = inputEl.selectionEnd = start + symbol.length; });
    },
    async loadPatterns() {
        try {
            const response = await fetch('/api/resolution_patterns');
            if (!response.ok) throw new Error('Ошибка загрузки паттернов разрешения');
            this.patterns = await response.json();
            this.patterns.forEach(rp => {
                rp.newSearchPattern = '';
            });
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async addPattern() {
        try {
            const response = await fetch('/api/resolution_patterns', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.newPattern) });
            if (!response.ok) throw new Error((await response.json()).error || 'Ошибка добавления');
            this.newPattern.standard_value = '';
            this.loadPatterns();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async updatePattern(pattern) {
        try {
            await fetch(`/api/resolution_patterns/${pattern.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pattern) });
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async deletePattern(id) {
        if (!confirm('Вы уверены, что хотите удалить этот стандарт и все связанные с ним поисковые паттерны?')) return;
        try {
            await fetch(`/api/resolution_patterns/${id}`, { method: 'DELETE' });
            this.loadPatterns();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async movePattern(index, direction) {
        const otherIndex = index + direction;
        [this.patterns[index], this.patterns[otherIndex]] = [this.patterns[otherIndex], this.patterns[index]];
        const orderedIds = this.patterns.map(p => p.id);
        try {
            await fetch('/api/resolution_patterns/reorder', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(orderedIds) });
        } catch (error) { this.$emit('show-toast', 'Ошибка изменения порядка', 'danger'); }
    },
    async addSearchPattern(resolutionPattern) {
        try {
            const response = await fetch(`/api/resolution_patterns/${resolutionPattern.id}/search_patterns`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pattern: resolutionPattern.newSearchPattern })
            });
            if (!response.ok) throw new Error((await response.json()).error || 'Ошибка добавления');
            resolutionPattern.newSearchPattern = '';
            this.loadPatterns();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async deleteSearchPattern(searchPatternId) {
        if (!confirm('Вы уверены, что хотите удалить этот поисковый паттерн?')) return;
        try {
            await fetch(`/api/resolution_search_patterns/${searchPatternId}`, { method: 'DELETE' });
            this.loadPatterns();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async testPatterns() {
        if (!this.testData.filename) return;
        try {
            const response = await fetch('/api/resolution_patterns/test', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename: this.testData.filename }) });
            const data = await response.json();
            this.testData.result = data.result || "Не найдено";
        } catch (error) { this.$emit('show-toast', 'Ошибка при тестировании', 'danger'); }
    },
  },
  mounted() {
      this.loadPatterns();
  }
};