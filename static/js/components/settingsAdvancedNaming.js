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
                
                <div class="p-3 border rounded bg-light mb-3">
                    <div class="row g-2">
                        <div class="col-md-6">
                            <label class="modern-label">Имя правила</label>
                            <input v-model.trim="newPattern.name" type="text" class="modern-input" placeholder="Напр: Исправить нумерацию частей фильма">
                        </div>
                         <div class="col-md-6">
                            <label class="modern-label">1. Поиск файла (фильтр, поддерживает *)</label>
                             <div class="modern-input-group">
                                <input v-model.trim="newPattern.file_filter" type="text" class="modern-input" placeholder="*S01E155*" ref="newFileFilterInput">
                                <button @click="insertSymbol('newFileFilterInput', newPattern, '*', 'file_filter')" class="modern-symbol-btn" title="Любой текст">*</button>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <label class="modern-label">2. Область поиска паттерна (с X для числа)</label>
                            <div class="modern-input-group">
                                <input v-model.trim="newPattern.pattern_search" type="text" class="modern-input" placeholder="*-PX" ref="newPatternSearchInput">
                                <button @click="insertSymbol('newPatternSearchInput', newPattern, 'X', 'pattern_search')" class="modern-symbol-btn" title="Захватить число">X</button>
                                <button @click="insertSymbol('newPatternSearchInput', newPattern, '*', 'pattern_search')" class="modern-symbol-btn" title="Любой текст">*</button>
                            </div>
                        </div>
                        <div class="col-md-6">
                             <label class="modern-label">3. Заменяемая область (с Y для символа)</label>
                            <div class="modern-input-group">
                                <input v-model.trim="newPattern.area_to_replace" type="text" class="modern-input" placeholder="S01E155 или S02SYY" ref="newAreaToReplaceInput">
                                <button @click="insertSymbol('newAreaToReplaceInput', newPattern, 'Y', 'area_to_replace')" class="modern-symbol-btn" title="Любой одиночный символ">Y</button>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <label class="modern-label">4. Замена (шаблон с X для вставки)</label>
                            <div class="modern-input-group">
                                <input v-model.trim="newPattern.replacement_template" type="text" class="modern-input" placeholder="s00eXX" ref="newReplacementInput">
                                <button @click="insertSymbol('newReplacementInput', newPattern, 'X', 'replacement_template')" class="modern-symbol-btn" title="Вставить число">X</button>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <label class="modern-label">5. Арифметика (+/- число, необязательно)</label>
                            <div class="modern-input-group">
                                <input v-model="newPattern.arithmetic_op" type="text" class="modern-input" placeholder="Напр: +155 или -1" ref="newArithmeticOpInput">
                                <button @click="insertSymbol('newArithmeticOpInput', newPattern, '+', 'arithmetic_op')" class="modern-symbol-btn" title="Сложение">+</button>
                                <button @click="insertSymbol('newArithmeticOpInput', newPattern, '-', 'arithmetic_op')" class="modern-symbol-btn" title="Вычитание">-</button>
                            </div>
                        </div>
                         </div>
                     <div class="d-flex justify-content-end mt-2 gap-2">
                        <button class="modern-btn btn-secondary" @click="clearForm" v-if="newPattern.id">
                            <i class="bi bi-x-lg"></i> Очистить форму
                        </button>
                        <button class="modern-btn btn-primary" @click="savePattern" :disabled="!isNewPatternValid.isValid">
                            <i class="bi bi-save"></i> {{ newPattern.id ? 'Сохранить изменения' : 'Добавить новое правило' }}
                        </button>
                    </div>
                    <div v-if="!isNewPatternValid.isValid && formTouched" class="alert alert-warning p-2 mt-2 small">
                        {{ isNewPatternValid.message }}
                    </div>
                </div>

                <div class="patterns-list">
                   <transition-group name="list" tag="div">
                       <div v-for="(p, index) in patterns" :key="p.id" 
                            class="pattern-item" 
                            :class="{'editing': newPattern.id === p.id}"
                            :data-id="p.id" 
                            @click="selectPatternForEditing(p)"
                            role="button"
                            title="Нажмите, чтобы редактировать">
                           <div class="pattern-content">
                               <div class="pattern-info" style="display: grid; grid-template-columns: 1fr 2fr; gap: 1rem; align-items: start; width:100%">
                                   <div class="pattern-name">
                                       <strong>{{ p.name }}</strong>
                                       <small v-if="p.arithmetic_op" class="d-block text-muted">
                                            Операция: {{ p.arithmetic_op > 0 ? '+' : '' }}{{ p.arithmetic_op }}
                                       </small>
                                   </div>
                                   <div style="font-family: var(--bs-font-monospace); font-size: 0.9em; word-break: break-all;">
                                       <div><span class="text-muted">1. Фильтр:</span> {{ p.file_filter }}</div>
                                       <div><span class="text-muted">2. Поиск X:</span> {{ p.pattern_search }}</div>
                                       <div><span class="text-muted">3. Заменяем:</span> {{ p.area_to_replace }}</div>
                                       <div><span class="text-muted">4. Вставляем:</span> {{ p.replacement_template }}</div>
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
                <div class="modern-input-group">
                    <input type="text" class="modern-input" placeholder="Введите имя файла для теста" v-model="testData.filename">
                    <button class="modern-btn btn-success" @click="testAllPatterns" :disabled="!testData.filename">
                        <i class="bi bi-check-circle me-2"></i>Проверить все
                    </button>
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
  watch: {
    newPattern: {
        handler() {
            this.formTouched = true;
        },
        deep: true
    }
  },
  computed: {
    isNewPatternValid() {
        const { name, file_filter, pattern_search, area_to_replace, replacement_template } = this.newPattern;
        if (!name || !file_filter || !pattern_search || !area_to_replace || !replacement_template) {
            return { isValid: false, message: 'Все обязательные поля должны быть заполнены.' };
        }
        
        const pattern_x_count = (pattern_search.match(/X/g) || []).length;
        const replacement_x_count = (replacement_template.match(/X/g) || []).length;

        if (pattern_x_count === 0) {
            return { isValid: false, message: "В 'Области поиска паттерна' должна быть хотя бы одна буква 'X' для извлечения числа." };
        }

        if (pattern_x_count !== replacement_x_count) {
            return { isValid: false, message: `Количество 'X' в 'Области поиска' (${pattern_x_count}) не совпадает с количеством в 'Замене' (${replacement_x_count}).` };
        }

        return { isValid: true, message: '' };
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
        // Обеспечиваем, чтобы null не отображался как "null" в поле ввода
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
        if (!this.isNewPatternValid.isValid) return;

        const isUpdating = !!this.newPattern.id;
        const url = isUpdating ? `/api/advanced_patterns/${this.newPattern.id}` : '/api/advanced_patterns';
        const method = isUpdating ? 'PUT' : 'POST';

        try {
            const payload = { ...this.newPattern };
            const op_val = parseInt(payload.arithmetic_op, 10);
            payload.arithmetic_op = isNaN(op_val) ? null : op_val;

            const response = await fetch(url, { 
                method: method, 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify(payload) 
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Ошибка сохранения');
            }
            
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

            const response = await fetch(`/api/advanced_patterns/${pattern.id}`, { 
                method: 'PUT', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify(payload) 
            });
            if (!response.ok) throw new Error('Ошибка обновления статуса');
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
            this.load();
        }
    },
    async deletePattern(id) {
        if (!confirm('Вы уверены?')) return;
        try {
            const response = await fetch(`/api/advanced_patterns/${id}`, { method: 'DELETE' });
            if (!response.ok) throw new Error('Ошибка удаления');
            
            if(this.newPattern.id === id) {
                this.clearForm();
            }
            await this.load();

        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        }
    },
    async movePattern(index, direction) {
        const otherIndex = index + direction;
        [this.patterns[index], this.patterns[otherIndex]] = [this.patterns[otherIndex], this.patterns[index]];
        const orderedIds = this.patterns.map(p => p.id);
        try {
            const response = await fetch('/api/advanced_patterns/reorder', { 
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify(orderedIds) 
            });
            if (!response.ok) throw new Error('Ошибка изменения порядка');
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
            await this.load();
        }
    },
    async testAllPatterns() {
        this.testData.result = '';
        if (!this.testData.filename) {
            this.$emit('show-toast', 'Введите имя файла для теста', 'warning');
            return;
        }
        try {
            const payload = {
                filename: this.testData.filename,
            };
            const response = await fetch('/api/advanced_patterns/test-all', { 
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify(payload) 
            });
            if (!response.ok) throw new Error('Ошибка при тестировании');
            const data = await response.json();
            this.testData.result = data.result;
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        }
    },
    insertSymbol(refName, contextObject, symbol, propertyName) {
        const inputEl = this.$refs[refName];
        if (!inputEl) {
            console.error("Элемент ввода не найден для ref:", refName);
            return;
        }
        const start = inputEl.selectionStart;
        const end = inputEl.selectionEnd;
        let text = contextObject[propertyName] || '';
        contextObject[propertyName] = text.substring(0, start) + symbol + text.substring(end);
        inputEl.focus();
        this.$nextTick(() => { 
            inputEl.selectionStart = inputEl.selectionEnd = start + symbol.length; 
        });
    }
  },
  mounted() {
      this.load();
  }
};