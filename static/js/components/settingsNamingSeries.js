// static/js/components/settingsNamingSeries.js
const SettingsNamingSeriesTab = {
  name: 'SettingsNamingSeriesTab',
template: `
    <div class="settings-tab-content">
        <div class="modern-fieldset mb-4">
            <div class="fieldset-header">
                <h6 class="fieldset-title mb-0">Конструктор паттернов серии</h6>
            </div>
            <div class="fieldset-content">
                <p class="text-muted small mb-3">
                    Правила для поиска номеров эпизодов. 
                    Используйте 'X' для номера и '*' для любого текста. Обрабатываются по 
                    приоритету сверху вниз.
                </p>
                
                <div class="field-group">
                    <constructor-group>
                        <div class="constructor-item item-label-icon" title="Имя паттерна"><i class="bi bi-tag-fill"></i></div>
                        <div class="constructor-item item-floating-label">
                            <input type="text" class="item-input" id="series-pattern-name" placeholder=" " v-model.trim="newPattern.name">
                            <label for="series-pattern-name">Имя паттерна</label>
                        </div>
                        <div class="constructor-item item-label-icon" title="Паттерн"><i class="bi bi-diagram-3"></i></div>
                        <div class="constructor-item item-floating-label">
                            <input type="text" class="item-input" id="series-pattern-value" placeholder=" " v-model.trim="newPattern.pattern" ref="patternInput" @keyup.enter="addPattern">
                            <label for="series-pattern-value">Паттерн, напр: * sXXeXX *</label>
                        </div>
                        <div class="constructor-item item-button-group">
                            <button class="btn-icon btn-settings" @click="insertSymbol('X')" title="Вставить 'X'">X</button>
                            <button class="btn-icon btn-settings" @click="insertSymbol('*')" title="Вставить '*'">*</button>
                            <button class="btn-icon btn-confirm btn-text-icon" @click="addPattern" :disabled="!newPattern.pattern || !newPattern.name">
                                <i class="bi bi-plus-lg"></i>
                                <span>Добавить</span>
                            </button>
                        </div>
                    </constructor-group>
                </div>

                <div class="patterns-list">
                   <transition-group name="list" tag="div">
                       <div v-for="(p, index) in patterns" :key="p.id" class="pattern-item" :data-id="p.id">
                           <div class="pattern-content">
                               <div class="pattern-info">
                                   <strong class="pattern-name" :title="p.name">{{ p.name }}</strong>
                                   <span class="pattern-value" :title="p.pattern">{{ p.pattern }}</span>
                               </div>
                               <div class="pattern-controls">
                                   <button class="control-btn" @click="movePattern(index, -1)" :disabled="index === 0" title="Поднять приоритет"><i class="bi bi-chevron-up"></i></button>
                                   <button class="control-btn" @click="movePattern(index, 1)" :disabled="index === patterns.length - 1" title="Понизить приоритет"><i class="bi bi-chevron-down"></i></button>
                                   <div class="form-check form-switch mx-2">
                                      <input class="form-check-input" type="checkbox" role="switch" v-model="p.is_active" @change="updatePattern(p)" title="Включить/выключить паттерн">
                                   </div>
                                   <button class="control-btn text-danger" @click="deletePattern(p.id)" title="Удалить"><i class="bi bi-trash"></i></button>
                               </div>
                           </div>
                       </div>
                   </transition-group>
                   <div v-if="!patterns.length" class="empty-state">Паттернов пока нет.</div>
                </div>
            </div>
        </div>
        <div class="modern-fieldset">
            <div class="fieldset-header">
                <h6 class="fieldset-title mb-0">Тестирование паттернов серии</h6>
            </div>
            <div class="fieldset-content">
                <div class="field-group">
                    <constructor-group>
                        <div class="constructor-item item-label-icon" title="Имя файла"><i class="bi bi-file-earmark-text"></i></div>
                        <input type="text" class="constructor-item item-input" placeholder="Введите имя файла для теста..." v-model="testData.filename" @keyup.enter="testPatterns">
                        <div class="constructor-item item-button-group">
                            <button class="btn-icon btn-search btn-text-icon" @click="testPatterns" :disabled="!testData.filename">
                                <i class="bi bi-check-circle"></i>
                                <span>Проверить</span>
                            </button>
                        </div>
                    </constructor-group>
                </div>
                <div v-if="testData.result" class="alert mt-3" :class="testData.result.includes('Успех') ? 'alert-success' : 'alert-warning'">
                    <strong>Результат:</strong> {{ testData.result }}
                </div>
            </div>
        </div>
    </div>
  `,
  data() {
    return {
      patterns: [],
      newPattern: { name: '', pattern: '' },
      testData: { filename: '', result: '' },
    };
  },
  emits: ['show-toast'],
  methods: {
    insertSymbol(symbol) {
        const inputEl = this.$refs.patternInput;
        const start = inputEl.selectionStart;
        const end = inputEl.selectionEnd;
        let currentVal = this.newPattern.pattern || '';
        this.newPattern.pattern = currentVal.substring(0, start) + symbol + currentVal.substring(end);
        inputEl.focus();
        this.$nextTick(() => { inputEl.selectionStart = inputEl.selectionEnd = start + symbol.length; });
    },
    async loadPatterns() {
        try {
            const response = await fetch('/api/patterns');
            if (!response.ok) throw new Error('Ошибка загрузки паттернов');
            this.patterns = await response.json();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async addPattern() {
        try {
            const response = await fetch('/api/patterns', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.newPattern) });
            if (!response.ok) throw new Error((await response.json()).error || 'Ошибка добавления');
            this.newPattern = { name: '', pattern: '' };
            this.loadPatterns();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async updatePattern(pattern) {
        try {
            await fetch(`/api/patterns/${pattern.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pattern) });
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async deletePattern(id) {
        if (!confirm('Вы уверены?')) return;
        try {
            await fetch(`/api/patterns/${id}`, { method: 'DELETE' });
            this.loadPatterns();
        } catch (error) { this.$emit('show-toast', 'Ошибка удаления', 'danger'); }
    },
    async movePattern(index, direction) {
        const otherIndex = index + direction;
        [this.patterns[index], this.patterns[otherIndex]] = [this.patterns[otherIndex], this.patterns[index]];
        const orderedIds = this.patterns.map(p => p.id);
        try {
            await fetch('/api/patterns/reorder', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(orderedIds) });
        } catch (error) { this.$emit('show-toast', 'Ошибка изменения порядка', 'danger'); }
    },
    async testPatterns() {
        if (!this.testData.filename) return;
        try {
            const response = await fetch('/api/patterns/test-all', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename: this.testData.filename }) });
            this.testData.result = (await response.json()).result;
        }
        catch (error) { this.$emit('show-toast', 'Ошибка при тестировании', 'danger'); }
    },
  },
  mounted() {
      this.loadPatterns();
  }
};