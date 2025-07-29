const SettingsAdvancedNamingTab = {
  name: 'SettingsAdvancedNamingTab',
  template: `
    <div class="settings-tab-content">
        <div class="modern-fieldset mb-4">
            <div class="fieldset-header">
                <h6 class="fieldset-title mb-0">Конструктор Продвинутых Паттернов</h6>
            </div>
            <div class="fieldset-content">
                <p class="text-muted small mb-3">
                    Создайте новое правило или нажмите на существующее в списке ниже, чтобы загрузить его для редактирования.
                    Используйте <b>X</b> для захвата числа, <b>*</b> для любого текста и <b>Y</b> для любого одиночного символа.
                </p>
                
                <!-- ИЗМЕНЕНИЕ: Восстановлена сеточная структура и тип полей -->
                <div class="row g-3">
                    <!-- СТРОКА 1 -->
                    <div class="col-md-6">
                        <div class="field-group">
                            <label class="modern-label">Имя правила</label>
                            <constructor-group :class="validationClasses.name">
                                <div class="constructor-item item-label item-label-icon" title="Имя правила"><i class="bi bi-tag-fill"></i></div>
                                <input type="text" class="constructor-item item-input" placeholder="Напр: Исправить нумерацию" v-model.trim="newPattern.name">
                            </constructor-group>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="field-group">
                            <label class="modern-label">1. Поиск файла (фильтр, поддерживает *)</label>
                            <constructor-group :class="validationClasses.file_filter">
                                <div class="constructor-item item-label item-label-icon" title="Фильтр файла"><i class="bi bi-files"></i></div>
                                <input type="text" class="constructor-item item-input" placeholder="*S01E155*" v-model.trim="newPattern.file_filter" ref="fileFilterInput">
                                <div class="constructor-item item-button-group">
                                    <button class="btn-icon btn-settings" @click="insertSymbol('file_filter', '*')" title="Вставить '*'">*</button>
                                </div>
                            </constructor-group>
                        </div>
                    </div>

                    <!-- СТРОКА 2 -->
                    <div class="col-md-6">
                        <div class="field-group">
                            <label class="modern-label">2. Область поиска паттерна (с X для числа)</label>
                            <constructor-group :class="validationClasses.pattern_search">
                                <div class="constructor-item item-label item-label-icon" title="Область поиска"><i class="bi bi-search"></i></div>
                                <input type="text" class="constructor-item item-input" placeholder="*-PX" v-model.trim="newPattern.pattern_search" ref="patternSearchInput">
                                <div class="constructor-item item-button-group">
                                    <button class="btn-icon btn-settings" @click="insertSymbol('pattern_search', 'X')" title="Вставить 'X'">X</button>
                                    <button class="btn-icon btn-settings" @click="insertSymbol('pattern_search', '*')" title="Вставить '*'">*</button>
                                </div>
                            </constructor-group>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="field-group">
                            <label class="modern-label">3. Заменяемая область (с Y для символа)</label>
                             <constructor-group :class="validationClasses.area_to_replace">
                                <div class="constructor-item item-label item-label-icon" title="Заменяемая область"><i class="bi bi-back"></i></div>
                                <input type="text" class="constructor-item item-input" placeholder="S01E155 или S02SYY" v-model.trim="newPattern.area_to_replace" ref="areaToReplaceInput">
                                <div class="constructor-item item-button-group">
                                    <button class="btn-icon btn-settings" @click="insertSymbol('area_to_replace', 'Y')" title="Вставить 'Y'">Y</button>
                                </div>
                            </constructor-group>
                        </div>
                    </div>

                    <!-- СТРОКА 3 -->
                    <div class="col-md-6">
                        <div class="field-group">
                            <label class="modern-label">4. Замена (шаблон с X для вставки)</label>
                             <constructor-group :class="validationClasses.replacement_template">
                                <div class="constructor-item item-label item-label-icon" title="Шаблон замены"><i class="bi bi-pencil-square"></i></div>
                                <input type="text" class="constructor-item item-input" placeholder="s00eXX" v-model.trim="newPattern.replacement_template" ref="replacementTemplateInput">
                                <div class="constructor-item item-button-group">
                                    <button class="btn-icon btn-settings" @click="insertSymbol('replacement_template', 'X')" title="Вставить 'X'">X</button>
                                </div>
                            </constructor-group>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="field-group">
                            <label class="modern-label">5. Арифметика (+/- число, необязательно)</label>
                            <constructor-group>
                                <div class="constructor-item item-label item-label-icon" title="Арифметическая операция"><i class="bi bi-calculator"></i></div>
                                <input type="text" class="constructor-item item-input" placeholder="Напр: +155 или -1" v-model="newPattern.arithmetic_op" ref="arithmeticOpInput">
                                <div class="constructor-item item-button-group">
                                    <button class="btn-icon btn-settings" @click="insertSymbol('arithmetic_op', '+')" title="Вставить '+'">+</button>
                                    <button class="btn-icon btn-settings" @click="insertSymbol('arithmetic_op', '-')" title="Вставить '-'">-</button>
                                </div>
                            </constructor-group>
                        </div>
                    </div>
                </div>
                
                 <div class="d-flex justify-content-end mt-2 gap-2">
                    <button class="btn btn-secondary" @click="clearForm" v-if="newPattern.id">
                        <i class="bi bi-x-lg"></i> Очистить форму
                    </button>
                    <button class="btn btn-primary" @click="savePattern">
                        <i class="bi bi-save"></i> {{ newPattern.id ? 'Сохранить изменения' : 'Добавить новое правило' }}
                    </button>
                </div>
                <div v-if="!isNewPatternValid.isValid && formTouched" class="alert alert-warning p-2 mt-2 small">
                    {{ isNewPatternValid.message }}
                </div>
                
                <div class="patterns-list mt-4">
                   <transition-group name="list" tag="div">
                       <div v-for="(p, index) in patterns" :key="p.id" 
                            class="list-card pattern-item" 
                            :class="{'editing': newPattern.id === p.id}"
                            :data-id="p.id" 
                            @click="selectPatternForEditing(p)"
                            role="button"
                            title="Нажмите, чтобы редактировать">
                           <div class="list-card-header pattern-content">
                               <div class="pattern-info" style="display: grid; grid-template-columns: 1fr 2fr; gap: 1rem; align-items: start; width:100%">
                                   <div class="pattern-name">
                                       <strong>{{ p.name }}</strong>
                                   </div>
                               </div>
                               <div class="pattern-controls">
                                   <button class="control-btn" @click.stop="movePattern(index, -1)" :disabled="index === 0" title="Поднять приоритет"><i class="bi bi-chevron-up"></i></button>
                                   <button class="control-btn" @click.stop="movePattern(index, 1)" :disabled="index === patterns.length - 1" title="Понизить приоритет"><i class="bi bi-chevron-down"></i></button>
                                   <div class="form-check form-switch mx-2">
                                       <input class="form-check-input" type="checkbox" role="switch" v-model="p.is_active" @click.stop @change="updatePattern(p)">
                                   </div>
                                   <button class="control-btn text-danger" @click.stop="deletePattern(p.id)" title="Удалить"><i class="bi bi-trash"></i></button>
                               </div>
                           </div>
                           <div class="list-card-body">
                                <small v-if="p.arithmetic_op" class="d-block text-muted mb-2">
                                     Операция: {{ p.arithmetic_op > 0 ? '+' : '' }}{{ p.arithmetic_op }}
                                </small>
                                <div style="font-family: var(--bs-font-monospace); font-size: 0.9em; word-break: break-all;">
                                   <div><span class="text-muted">1. Фильтр:</span> {{ p.file_filter }}</div>
                                   <div><span class="text-muted">2. Поиск X:</span> {{ p.pattern_search }}</div>
                                   <div><span class="text-muted">3. Заменяем:</span> {{ p.area_to_replace }}</div>
                                   <div><span class="text-muted">4. Вставляем:</span> {{ p.replacement_template }}</div>
                               </div>
                           </div>
                       </div>
                   </transition-group>
                   <div v-if="!patterns.length" class="empty-state">Продвинутых паттернов пока нет.</div>
                </div>
            </div>
        </div>
        
        <div class="modern-fieldset">
            <div class="fieldset-header">
                <h6 class="fieldset-title mb-0">Тестирование Продвинутых Паттернов</h6>
            </div>
            <div class="fieldset-content">
                <p class="text-muted small mb-3">Проверяет введенное имя файла по всем <b>активным</b> правилам из списка выше.</p>
                <div class="field-group">
                    <constructor-group>
                        <div class="constructor-item item-label item-label-icon" title="Имя файла"><i class="bi bi-file-earmark-text"></i></div>
                        <input type="text" class="constructor-item item-input" placeholder="Введите имя файла для теста" v-model="testData.filename">
                        <div class="constructor-item item-button-group">
                            <button class="btn-icon btn-search btn-text-icon" @click="testAllPatterns" :disabled="!testData.filename">
                                <i class="bi bi-check-circle me-2"></i>Проверить все
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
      newPattern: this.getEmptyPattern(),
      formTouched: false,
      testData: {
        filename: 'Perfect.World.ONA.S01E155.FILM.Ashes.Of.Perfect.Fire-P1.(2024).WEB-DL.2160p.mkv',
        result: ''
      }
    };
  },
  emits: ['show-toast'],
  computed: {
    isNewPatternValid() {
        const { name, file_filter, pattern_search, area_to_replace, replacement_template } = this.newPattern;
        if (!name || !file_filter || !pattern_search || !area_to_replace || !replacement_template) {
            return { isValid: false, message: 'Все обязательные поля, кроме арифметики, должны быть заполнены.' };
        }
        
        const pattern_x_count = (pattern_search.match(/X/g) || []).length;
        if (pattern_x_count === 0) {
            return { isValid: false, message: "В 'Области поиска паттерна' должна быть хотя бы одна буква 'X' для извлечения числа." };
        }

        const replacement_x_count = (replacement_template.match(/X/g) || []).length;
        if (pattern_x_count !== replacement_x_count) {
            return { isValid: false, message: `Количество 'X' в 'Области поиска' (${pattern_x_count}) не совпадает с количеством в 'Замене' (${replacement_x_count}).` };
        }

        return { isValid: true, message: '' };
    },
    validationClasses() {
        if (!this.formTouched) return {};
        const { name, file_filter, pattern_search, area_to_replace, replacement_template } = this.newPattern;
        const isValid = (field) => field && field.length > 0;
        return {
            name: { 'is-valid': isValid(name), 'is-invalid': !isValid(name) },
            file_filter: { 'is-valid': isValid(file_filter), 'is-invalid': !isValid(file_filter) },
            pattern_search: { 'is-valid': isValid(pattern_search), 'is-invalid': !isValid(pattern_search) },
            area_to_replace: { 'is-valid': isValid(area_to_replace), 'is-invalid': !isValid(area_to_replace) },
            replacement_template: { 'is-valid': isValid(replacement_template), 'is-invalid': !isValid(replacement_template) },
        }
    }
  },
  methods: {
    getEmptyPattern() {
        return { id: null, name: '', file_filter: '', pattern_search: '', area_to_replace: '', replacement_template: '', arithmetic_op: '', is_active: true };
    },
    clearForm() {
        this.newPattern = this.getEmptyPattern();
        this.formTouched = false;
        this.testData.result = '';
    },
    selectPatternForEditing(pattern) {
        this.newPattern = JSON.parse(JSON.stringify(pattern));
        this.formTouched = false;
        if (this.newPattern.arithmetic_op === null) {
            this.newPattern.arithmetic_op = '';
        }
    },
    async load() {
      try {
        const response = await fetch('/api/advanced_patterns');
        if (!response.ok) throw new Error('Ошибка загрузки продвинутых паттернов');
        this.patterns = await response.json();
      } catch (error) {
        this.$emit('show-toast', error.message, 'danger');
      }
    },
    async savePattern() {
        this.formTouched = true;
        if (!this.isNewPatternValid.isValid) {
            this.$emit('show-toast', this.isNewPatternValid.message, 'warning');
            return;
        };

        const isUpdating = !!this.newPattern.id;
        const url = isUpdating ? `/api/advanced_patterns/${this.newPattern.id}` : '/api/advanced_patterns';
        const method = isUpdating ? 'PUT' : 'POST';

        try {
            const payload = { ...this.newPattern };
            const op_val = parseInt(payload.arithmetic_op, 10);
            payload.arithmetic_op = isNaN(op_val) ? null : op_val;

            const response = await fetch(url, { method: method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            if (!response.ok) throw new Error((await response.json()).error || 'Ошибка сохранения');
            
            this.clearForm();
            await this.load();
            this.$emit('show-toast', isUpdating ? 'Паттерн обновлен.' : 'Паттерн добавлен.', 'success');
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        }
    },
    async updatePattern(pattern) {
        try {
            const payload = { ...pattern };
            const op_val = parseInt(payload.arithmetic_op, 10);
            payload.arithmetic_op = isNaN(op_val) ? null : op_val;

            const response = await fetch(`/api/advanced_patterns/${pattern.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            if (!response.ok) throw new Error('Ошибка обновления статуса');
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
            this.load();
        }
    },
    async deletePattern(id) {
        if (!confirm('Вы уверены?')) return;
        try {
            await fetch(`/api/advanced_patterns/${id}`, { method: 'DELETE' });
            if(this.newPattern.id === id) { this.clearForm(); }
            await this.load();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async movePattern(index, direction) {
        const otherIndex = index + direction;
        [this.patterns[index], this.patterns[otherIndex]] = [this.patterns[otherIndex], this.patterns[index]];
        const orderedIds = this.patterns.map(p => p.id);
        try {
            await fetch('/api/advanced_patterns/reorder', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(orderedIds) });
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); await this.load(); }
    },
    async testAllPatterns() {
        this.testData.result = '';
        if (!this.testData.filename) return;
        try {
            const response = await fetch('/api/advanced_patterns/test-all', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename: this.testData.filename }) });
            if (!response.ok) throw new Error('Ошибка при тестировании');
            this.testData.result = (await response.json()).result;
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    insertSymbol(fieldKey, symbol) {
        const refNameMap = {
            file_filter: 'fileFilterInput',
            pattern_search: 'patternSearchInput',
            area_to_replace: 'areaToReplaceInput',
            replacement_template: 'replacementTemplateInput',
            arithmetic_op: 'arithmeticOpInput'
        };
        const refName = refNameMap[fieldKey];
        if (!refName) return;

        const inputEl = this.$refs[refName];
        if (!inputEl) return;

        const start = inputEl.selectionStart;
        const end = inputEl.selectionEnd;
        let text = this.newPattern[fieldKey] || '';
        this.newPattern[fieldKey] = text.substring(0, start) + symbol + text.substring(end);
        
        inputEl.focus();
        this.$nextTick(() => { inputEl.selectionStart = inputEl.selectionEnd = start + symbol.length; });
    }
  },
  mounted() {
      this.load();
  }
};