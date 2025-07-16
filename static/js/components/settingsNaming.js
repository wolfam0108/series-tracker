const SettingsNamingTab = {
  components: {
    'settings-advanced-naming-tab': SettingsAdvancedNamingTab,
  },
  template: `
    <div class="settings-tab-content">
        <div class="sticky-sub-nav-wrapper">
            <ul class="nav nav-pills sub-nav-pills" id="pills-tab-naming" role="tablist">
                <li class="nav-item" role="presentation">
                    <button class="nav-link modern-tab-link active" id="pills-series-tab" data-bs-toggle="pill" data-bs-target="#pills-series" type="button" role="tab"><i class="bi bi-film me-2"></i>Паттерны серии</button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link modern-tab-link" id="pills-season-tab" data-bs-toggle="pill" data-bs-target="#pills-season" type="button" role="tab"><i class="bi bi-collection-play me-2"></i>Паттерны сезона</button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link modern-tab-link" id="pills-advanced-tab" data-bs-toggle="pill" data-bs-target="#pills-advanced" type="button" role="tab"><i class="bi bi-magic me-2"></i>Продвинутые паттерны</button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link modern-tab-link" id="pills-quality-tab" data-bs-toggle="pill" data-bs-target="#pills-quality" type="button" role="tab"><i class="bi bi-badge-hd me-2"></i>Паттерны качества</button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link modern-tab-link" id="pills-resolution-tab" data-bs-toggle="pill" data-bs-target="#pills-resolution" type="button" role="tab"><i class="bi bi-aspect-ratio me-2"></i>Паттерны разрешения</button>
                </li>
            </ul>
        </div>
        <div class="tab-content naming-content-area" id="pills-tabContent-naming">
            <div class="tab-pane fade show active" id="pills-series" role="tabpanel">
                <div class="modern-fieldset mb-4">
                    <div class="fieldset-header">
                        <h6 class="fieldset-title mb-0">Конструктор паттернов серии</h6>
                    </div>
                    <div class="fieldset-content">
                        <p class="text-muted small mb-3">Правила для поиска номеров эпизодов. Используйте 'X' для номера и '*' для любого текста. Обрабатываются по приоритету сверху вниз.</p>
                        
                        <div class="modern-input-group mb-3">
                            <input v-model.trim="newSeriesPattern.name" type="text" class="modern-input" placeholder="Имя паттерна" style="flex: 0.5;">
                            <div class="modern-input-group-divider"></div>
                            <input v-model.trim="newSeriesPattern.pattern" type="text" class="modern-input" placeholder="* sXXeXX *" ref="seriesPatternInput">
                            <button class="modern-symbol-btn" @click="insertSymbol('seriesPatternInput', newSeriesPattern, 'X', 'pattern')" title="Вставить плейсхолдер для номера"><i class="bi bi-x-lg"></i></button>
                            <button class="modern-symbol-btn" @click="insertSymbol('seriesPatternInput', newSeriesPattern, '*', 'pattern')" title="Вставить 'любой текст'"><i class="bi bi-asterisk"></i></button>
                            <button class="btn btn-primary" @click="addSeriesPattern" :disabled="!newSeriesPattern.pattern || !newSeriesPattern.name">
                                <i class="bi bi-plus-lg"></i> Добавить
                            </button>
                        </div>

                        <div class="patterns-list">
                           <transition-group name="list" tag="div">
                               <div v-for="(p, index) in seriesPatterns" :key="p.id" class="pattern-item" :data-id="p.id">
                                   <div class="pattern-content">
                                       <div class="pattern-info">
                                           <strong class="pattern-name" :title="p.name">{{ p.name }}</strong>
                                           <span class="pattern-value" :title="p.pattern">{{ p.pattern }}</span>
                                       </div>
                                       <div class="pattern-controls">
                                           <button class="control-btn" @click="moveSeriesPattern(index, -1)" :disabled="index === 0" title="Поднять приоритет">
                                               <i class="bi bi-chevron-up"></i>
                                           </button>
                                           <button class="control-btn" @click="moveSeriesPattern(index, 1)" :disabled="index === seriesPatterns.length - 1" title="Понизить приоритет">
                                               <i class="bi bi-chevron-down"></i>
                                           </button>
                                           <div class="form-check form-switch mx-2">
                                              <input class="form-check-input" type="checkbox" role="switch" v-model="p.is_active" @change="updateSeriesPattern(p)" title="Включить/выключить паттерн">
                                           </div>
                                           <button class="control-btn text-danger" @click="deleteSeriesPattern(p.id)" title="Удалить">
                                               <i class="bi bi-trash"></i>
                                           </button>
                                       </div>
                                   </div>
                               </div>
                           </transition-group>
                           <div v-if="!seriesPatterns.length" class="empty-state">Паттернов пока нет.</div>
                        </div>
                    </div>
                </div>
                
                <div class="modern-fieldset">
                    <div class="fieldset-header">
                        <h6 class="fieldset-title mb-0">Тестирование паттернов серии</h6>
                    </div>
                    <div class="fieldset-content">
                        <div class="modern-input-group">
                            <input type="text" class="modern-input" placeholder="Введите имя файла для теста" v-model="testAllSeries.filename">
                            <button class="btn btn-success" @click="testAllSeriesPatterns">
                                <i class="bi bi-check-circle me-2"></i>Проверить
                            </button>
                        </div>
                        <div v-if="testAllSeries.result" class="alert mt-3" :class="testAllSeries.result.includes('Успех') ? 'alert-success' : 'alert-warning'">
                            <strong>Результат:</strong> {{ testAllSeries.result }}
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="tab-pane fade" id="pills-season" role="tabpanel">
                 <div class="modern-fieldset mb-4">
                    <div class="fieldset-header">
                        <h6 class="fieldset-title mb-0">Конструктор паттернов сезона</h6>
                    </div>
                    <div class="fieldset-content">
                         <p class="text-muted small mb-3">Правила для поиска номеров сезонов в именах файлов.</p>
                         
                        <div class="modern-input-group mb-3">
                            <input v-model.trim="newSeasonPattern.name" type="text" class="modern-input" placeholder="Имя паттерна" style="flex: 0.5;">
                            <div class="modern-input-group-divider"></div>
                            <input v-model.trim="newSeasonPattern.pattern" type="text" class="modern-input" placeholder="* сезон X *" ref="seasonPatternInput">
                            <button class="modern-symbol-btn" @click="insertSymbol('seasonPatternInput', newSeasonPattern, 'X', 'pattern')" title="Вставить плейсхолдер для номера"><i class="bi bi-x-lg"></i></button>
                            <button class="modern-symbol-btn" @click="insertSymbol('seasonPatternInput', newSeasonPattern, '*', 'pattern')" title="Вставить 'любой текст'"><i class="bi bi-asterisk"></i></button>
                            <button class="btn btn-primary" @click="addSeasonPattern" :disabled="!newSeasonPattern.pattern || !newSeasonPattern.name">
                                <i class="bi bi-plus-lg"></i> Добавить
                            </button>
                        </div>

                        <div class="patterns-list">
                           <transition-group name="list" tag="div">
                               <div v-for="(p, index) in seasonPatterns" :key="p.id" class="pattern-item" :data-id="p.id">
                                   <div class="pattern-content">
                                       <div class="pattern-info">
                                           <strong class="pattern-name" :title="p.name">{{ p.name }}</strong>
                                           <span class="pattern-value" :title="p.pattern">{{ p.pattern }}</span>
                                       </div>
                                       <div class="pattern-controls">
                                           <button class="control-btn" @click="moveSeasonPattern(index, -1)" :disabled="index === 0" title="Поднять приоритет">
                                               <i class="bi bi-chevron-up"></i>
                                           </button>
                                           <button class="control-btn" @click="moveSeasonPattern(index, 1)" :disabled="index === seasonPatterns.length - 1" title="Понизить приоритет">
                                               <i class="bi bi-chevron-down"></i>
                                           </button>
                                           <div class="form-check form-switch mx-2">
                                               <input class="form-check-input" type="checkbox" role="switch" v-model="p.is_active" @change="updateSeasonPattern(p)" title="Включить/выключить паттерн">
                                           </div>
                                           <button class="control-btn text-danger" @click="deleteSeasonPattern(p.id)" title="Удалить">
                                               <i class="bi bi-trash"></i>
                                           </button>
                                       </div>
                                   </div>
                               </div>
                           </transition-group>
                           <div v-if="!seasonPatterns.length" class="empty-state">Паттернов пока нет.</div>
                        </div>
                    </div>
                </div>
                
                <div class="modern-fieldset">
                    <div class="fieldset-header">
                        <h6 class="fieldset-title mb-0">Тестирование паттернов сезона</h6>
                    </div>
                    <div class="fieldset-content">
                        <div class="modern-input-group">
                            <input type="text" class="modern-input" placeholder="Введите имя файла для теста" v-model="testSeason.filename">
                            <button class="btn btn-success" @click="testAllSeasonPatterns">
                                <i class="bi bi-check-circle me-2"></i>Проверить
                            </button>
                        </div>
                        <div v-if="testSeason.result" class="alert mt-3" :class="testSeason.result.includes('Успех') ? 'alert-success' : 'alert-warning'">
                            <strong>Результат:</strong> {{ testSeason.result }}
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="tab-pane fade" id="pills-advanced" role="tabpanel">
                <settings-advanced-naming-tab ref="advancedNamingTab" @show-toast="emitToast"></settings-advanced-naming-tab>
            </div>
            
            <div class="tab-pane fade" id="pills-quality" role="tabpanel">
                <div class="modern-fieldset mb-4">
                     <div class="fieldset-header">
                        <h6 class="fieldset-title mb-0">Стандарты качества</h6>
                    </div>
                    <div class="fieldset-content">
                        <p class="text-muted small mb-3">Определите стандартизированные значения (например, '1080p WEB-DL') и поисковые паттерны для них.</p>
                        
                        <div class="modern-input-group mb-4">
                            <input type="text" class="modern-input" v-model="newQualityPattern.standard_value" placeholder="Новый стандарт качества, например: 1080p WEB-DL">
                            <button class="btn btn-success" @click="addQualityPattern" :disabled="!newQualityPattern.standard_value">
                                <i class="bi bi-plus-circle me-2"></i>Добавить стандарт
                            </button>
                        </div>

                        <div v-for="(qp, index) in qualityPatterns" :key="qp.id" class="list-card quality-standard-card mb-3">
                            <div class="list-card-header">
                                <div class="standard-title">
                                    <div class="form-check form-switch">
                                        <input class="form-check-input" type="checkbox" v-model="qp.is_active" @change="updateQualityPattern(qp)">
                                        <strong class="ms-2">{{ qp.standard_value }}</strong>
                                    </div>
                                </div>
                                <div class="standard-controls">
                                   <button class="control-btn" @click="moveQualityPattern(index, -1)" :disabled="index === 0" title="Поднять приоритет">
                                       <i class="bi bi-chevron-up"></i>
                                   </button>
                                   <button class="control-btn" @click="moveQualityPattern(index, 1)" :disabled="index === qualityPatterns.length - 1" title="Понизить приоритет">
                                       <i class="bi bi-chevron-down"></i>
                                   </button>
                                   <button class="control-btn text-danger" @click="deleteQualityPattern(qp.id)" title="Удалить стандарт">
                                       <i class="bi bi-trash"></i>
                                   </button>
                                </div>
                            </div>
                            <div class="list-card-body">
                                <div class="search-patterns-list mb-2">
                                    <div v-for="sp in qp.search_patterns" :key="sp.id" class="search-pattern-item">
                                       <code>{{ sp.pattern }}</code>
                                       <button class="pattern-remove-btn" @click="deleteQualitySearchPattern(sp.id)">
                                           <i class="bi bi-x"></i>
                                       </button>
                                    </div>
                                </div>
                                <div class="modern-input-group">
                                    <input type="text" class="modern-input" v-model="qp.newSearchPattern" placeholder="Новый поисковый паттерн..." :ref="'qualityPatternInput' + qp.id">
                                    <button class="modern-symbol-btn" @click="insertSymbol('qualityPatternInput' + qp.id, qp, '*', 'newSearchPattern')" title="Вставить 'любой текст'"><i class="bi bi-asterisk"></i></button>
                                    <button class="btn btn-primary" @click="addQualitySearchPattern(qp)" :disabled="!qp.newSearchPattern">
                                        <i class="bi bi-plus-lg"></i> Добавить
                                    </button>
                                </div>
                            </div>
                        </div>
                        
                        <div v-if="!qualityPatterns.length" class="empty-state">Стандартов качества пока нет.</div>
                    </div>
                </div>
                
                 <div class="modern-fieldset">
                    <div class="fieldset-header">
                        <h6 class="fieldset-title mb-0">Тестирование паттернов качества</h6>
                    </div>
                    <div class="fieldset-content">
                        <div class="modern-input-group">
                            <input type="text" class="modern-input" v-model="testQuality.filename" placeholder="Введите имя файла для теста">
                             <button class="btn btn-success" @click="testQualityPatterns">
                                <i class="bi bi-check-circle me-2"></i>Проверить
                            </button>
                        </div>
                        <div v-if="testQuality.result" class="alert alert-info mt-3"><strong>Результат:</strong> {{ testQuality.result }}</div>
                    </div>
                </div>
            </div>

            <div class="tab-pane fade" id="pills-resolution" role="tabpanel">
                 <div class="modern-fieldset mb-4">
                     <div class="fieldset-header">
                        <h6 class="fieldset-title mb-0">Стандарты разрешения</h6>
                    </div>
                    <div class="fieldset-content">
                        <p class="text-muted small mb-3">Определите стандартизированные значения (например, '1080p') и поисковые паттерны для них.</p>
                        
                        <div class="modern-input-group mb-4">
                            <input type="text" class="modern-input" v-model="newResolutionPattern.standard_value" placeholder="Новый стандарт разрешения, например: 1080p">
                            <button class="btn btn-success" @click="addResolutionPattern" :disabled="!newResolutionPattern.standard_value">
                                <i class="bi bi-plus-circle me-2"></i>Добавить стандарт
                            </button>
                        </div>

                        <div v-for="(rp, index) in resolutionPatterns" :key="rp.id" class="list-card quality-standard-card mb-3">
                            <div class="list-card-header">
                                <div class="standard-title">
                                    <div class="form-check form-switch">
                                        <input class="form-check-input" type="checkbox" v-model="rp.is_active" @change="updateResolutionPattern(rp)">
                                        <strong class="ms-2">{{ rp.standard_value }}</strong>
                                    </div>
                                </div>
                                <div class="standard-controls">
                                   <button class="control-btn" @click="moveResolutionPattern(index, -1)" :disabled="index === 0" title="Поднять приоритет">
                                       <i class="bi bi-chevron-up"></i>
                                   </button>
                                   <button class="control-btn" @click="moveResolutionPattern(index, 1)" :disabled="index === resolutionPatterns.length - 1" title="Понизить приоритет">
                                       <i class="bi bi-chevron-down"></i>
                                   </button>
                                   <button class="control-btn text-danger" @click="deleteResolutionPattern(rp.id)" title="Удалить стандарт">
                                       <i class="bi bi-trash"></i>
                                   </button>
                                </div>
                            </div>
                            <div class="list-card-body">
                                <div class="search-patterns-list mb-2">
                                    <div v-for="sp in rp.search_patterns" :key="sp.id" class="search-pattern-item">
                                       <code>{{ sp.pattern }}</code>
                                       <button class="pattern-remove-btn" @click="deleteResolutionSearchPattern(sp.id)">
                                           <i class="bi bi-x"></i>
                                       </button>
                                    </div>
                                </div>
                                <div class="modern-input-group">
                                    <input type="text" class="modern-input" v-model="rp.newSearchPattern" placeholder="Новый поисковый паттерн..." :ref="'resolutionPatternInput' + rp.id">
                                    <button class="modern-symbol-btn" @click="insertSymbol('resolutionPatternInput' + rp.id, rp, '*', 'newSearchPattern')" title="Вставить 'любой текст'"><i class="bi bi-asterisk"></i></button>
                                    <button class="btn btn-primary" @click="addResolutionSearchPattern(rp)" :disabled="!rp.newSearchPattern">
                                        <i class="bi bi-plus-lg"></i> Добавить
                                    </button>
                                </div>
                            </div>
                        </div>
                        
                        <div v-if="!resolutionPatterns.length" class="empty-state">Стандартов разрешения пока нет.</div>
                    </div>
                </div>
                
                 <div class="modern-fieldset">
                    <div class="fieldset-header">
                        <h6 class="fieldset-title mb-0">Тестирование паттернов разрешения</h6>
                    </div>
                    <div class="fieldset-content">
                        <div class="modern-input-group">
                            <input type="text" class="modern-input" v-model="testResolution.filename" placeholder="Введите имя файла для теста">
                            <button class="btn btn-success" @click="testResolutionPatterns">
                                <i class="bi bi-check-circle me-2"></i>Проверить
                            </button>
                        </div>
                        <div v-if="testResolution.result" class="alert alert-info mt-3"><strong>Результат:</strong> {{ testResolution.result }}</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
  `,
  data() {
    return {
      seriesPatterns: [], newSeriesPattern: { name: '', pattern: '' },
      seasonPatterns: [], newSeasonPattern: { name: '', pattern: '' },
      testAllSeries: { filename: '', result: '' },
      testSeason: { filename: '', result: '' },
      qualityPatterns: [], newQualityPattern: { standard_value: '' },
      testQuality: { filename: '', result: null },
      resolutionPatterns: [], newResolutionPattern: { standard_value: '' },
      testResolution: { filename: '', result: null },
    };
  },
  emits: ['show-toast'],
  methods: {
    emitToast(message, type) {
        this.$emit('show-toast', message, type);
    },
    load() {
      this.loadSeriesPatterns();
      this.loadSeasonPatterns();
      this.loadQualityPatterns();
      this.loadResolutionPatterns();
    },
    insertSymbol(refName, contextObject, symbol, propertyName) {
        const ref = this.$refs[refName];
        const inputEl = Array.isArray(ref) ? ref[0] : ref;
        if (!inputEl) {
            console.error("Элемент ввода не найден для ref:", refName);
            return;
        }
        const start = inputEl.selectionStart;
        const end = inputEl.selectionEnd;
        let text = contextObject[propertyName];
        contextObject[propertyName] = text.substring(0, start) + symbol + text.substring(end);
        inputEl.focus();
        this.$nextTick(() => { 
            inputEl.selectionStart = inputEl.selectionEnd = start + symbol.length; 
        });
    },
    async loadSeriesPatterns() {
        try {
            const response = await fetch('/api/patterns');
            if (!response.ok) throw new Error('Ошибка загрузки паттернов серии');
            this.seriesPatterns = await response.json();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async addSeriesPattern() {
        try {
            const response = await fetch('/api/patterns', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.newSeriesPattern) });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Ошибка добавления паттерна серии');
            }
            this.newSeriesPattern = { name: '', pattern: '' };
            this.loadSeriesPatterns();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async updateSeriesPattern(pattern) {
        try {
            const response = await fetch(`/api/patterns/${pattern.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pattern) });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Ошибка обновления паттерна серии');
            }
            this.$emit('show-toast', 'Паттерн серии обновлен.', 'success');
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async deleteSeriesPattern(id) {
        if (!confirm('Вы уверены, что хотите удалить этот паттерн серии?')) return;
        try {
            await fetch(`/api/patterns/${id}`, { method: 'DELETE' });
            this.loadSeriesPatterns();
        } catch (error) { this.$emit('show-toast', 'Ошибка удаления паттерна серии', 'danger'); }
    },
    async moveSeriesPattern(index, direction) {
        const otherIndex = index + direction;
        [this.seriesPatterns[index], this.seriesPatterns[otherIndex]] = [this.seriesPatterns[otherIndex], this.seriesPatterns[index]];
        const orderedIds = this.seriesPatterns.map(p => p.id);
        try {
            await fetch('/api/patterns/reorder', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(orderedIds) });
        } catch (error) { this.$emit('show-toast', 'Ошибка изменения порядка паттернов серии', 'danger'); }
    },
    async testAllSeriesPatterns() {
        if (!this.testAllSeries.filename) {
            this.testAllSeries.result = 'Введите имя файла для теста.';
            return;
        }
        try {
            const response = await fetch('/api/patterns/test-all', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename: this.testAllSeries.filename }) });
            const data = await response.json();
            this.testAllSeries.result = data.result;
        }
        catch (error) {
            this.$emit('show-toast', 'Ошибка при тестировании всех паттернов серии', 'danger');
        }
    },
    async loadSeasonPatterns() {
        try {
            const response = await fetch('/api/season_patterns');
            if (!response.ok) throw new Error('Ошибка загрузки паттернов сезона');
            this.seasonPatterns = await response.json();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async addSeasonPattern() {
        try {
            const response = await fetch('/api/season_patterns', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.newSeasonPattern) });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Ошибка добавления паттерна сезона');
            }
            this.newSeasonPattern = { name: '', pattern: '' };
            this.loadSeasonPatterns();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async updateSeasonPattern(pattern) {
        try {
            const response = await fetch(`/api/season_patterns/${pattern.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pattern) });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Ошибка обновления паттерна сезона');
            }
            this.$emit('show-toast', 'Паттерн сезона обновлен.', 'success');
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async deleteSeasonPattern(id) {
        if (!confirm('Вы уверены, что хотите удалить этот паттерн сезона?')) return;
        try {
            await fetch(`/api/season_patterns/${id}`, { method: 'DELETE' });
            this.loadSeasonPatterns();
        } catch (error) { this.$emit('show-toast', 'Ошибка удаления паттерна сезона', 'danger'); }
    },
    async moveSeasonPattern(index, direction) {
        const otherIndex = index + direction;
        [this.seasonPatterns[index], this.seasonPatterns[otherIndex]] = [this.seasonPatterns[otherIndex], this.seasonPatterns[index]];
        const orderedIds = this.seasonPatterns.map(p => p.id);
        try {
            await fetch('/api/season_patterns/reorder', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(orderedIds) });
        } catch (error) { this.$emit('show-toast', 'Ошибка изменения порядка паттернов сезона', 'danger'); }
    },
    async testAllSeasonPatterns() {
        if (!this.testSeason.filename) {
            this.testSeason.result = 'Введите имя файла для теста.';
            return;
        }
        try {
            const response = await fetch('/api/season_patterns/test-all', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename: this.testSeason.filename }) });
            const data = await response.json();
            this.testSeason.result = data.result;
        }
        catch (error) {
            this.$emit('show-toast', 'Ошибка при тестировании всех паттернов сезона', 'danger');
        }
    },
    async loadQualityPatterns() {
        try {
            const response = await fetch('/api/quality_patterns');
            if (!response.ok) throw new Error('Ошибка загрузки паттернов качества');
            this.qualityPatterns = await response.json();
            this.qualityPatterns.forEach(qp => {
                qp.newSearchPattern = '';
            });
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async addQualityPattern() {
        try {
            const response = await fetch('/api/quality_patterns', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.newQualityPattern) });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Ошибка добавления паттерна качества');
            }
            this.newQualityPattern.standard_value = '';
            this.loadQualityPatterns();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async updateQualityPattern(pattern) {
        try {
            const response = await fetch(`/api/quality_patterns/${pattern.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pattern) });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Ошибка обновления паттерна качества');
            }
            this.$emit('show-toast', 'Паттерн качества обновлен.', 'success');
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async deleteQualityPattern(id) {
        if (!confirm('Вы уверены, что хотите удалить этот паттерн качества и все связанные с ним поисковые паттерны?')) return;
        try {
            await fetch(`/api/quality_patterns/${id}`, { method: 'DELETE' });
            this.loadQualityPatterns();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async moveQualityPattern(index, direction) {
        const otherIndex = index + direction;
        [this.qualityPatterns[index], this.qualityPatterns[otherIndex]] = [this.qualityPatterns[otherIndex], this.qualityPatterns[index]];
        const orderedIds = this.qualityPatterns.map(p => p.id);
        try {
            await fetch('/api/quality_patterns/reorder', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(orderedIds) });
        } catch (error) { this.$emit('show-toast', 'Ошибка изменения порядка паттернов качества', 'danger'); }
    },
    async addQualitySearchPattern(qualityPattern) {
        try {
            const response = await fetch(`/api/quality_patterns/${qualityPattern.id}/search_patterns`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pattern: qualityPattern.newSearchPattern })
            });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Ошибка добавления поискового паттерна качества');
            }
            qualityPattern.newSearchPattern = '';
            this.loadQualityPatterns();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async deleteQualitySearchPattern(searchPatternId) {
        if (!confirm('Вы уверены, что хотите удалить этот поисковый паттерн качества?')) return;
        try {
            await fetch(`/api/quality_search_patterns/${searchPatternId}`, { method: 'DELETE' });
            this.loadQualityPatterns();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async testQualityPatterns() {
        if (!this.testQuality.filename) {
            this.testQuality.result = 'Введите имя файла для теста.';
            return;
        }
        try {
            const response = await fetch('/api/quality_patterns/test', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename: this.testQuality.filename }) });
            const data = await response.json();
            this.testQuality.result = data.result;
        } catch (error) { this.$emit('show-toast', 'Ошибка при тестировании паттернов качества', 'danger'); }
    },
    async loadResolutionPatterns() {
        try {
            const response = await fetch('/api/resolution_patterns');
            if (!response.ok) throw new Error('Ошибка загрузки паттернов разрешения');
            this.resolutionPatterns = await response.json();
            this.resolutionPatterns.forEach(rp => {
                rp.newSearchPattern = '';
            });
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async addResolutionPattern() {
        try {
            const response = await fetch('/api/resolution_patterns', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(this.newResolutionPattern) });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Ошибка добавления паттерна разрешения');
            }
            this.newResolutionPattern.standard_value = '';
            this.loadResolutionPatterns();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async updateResolutionPattern(pattern) {
        try {
            const response = await fetch(`/api/resolution_patterns/${pattern.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(pattern) });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Ошибка обновления паттерна разрешения');
            }
            this.$emit('show-toast', 'Паттерн разрешения обновлен.', 'success');
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async deleteResolutionPattern(id) {
        if (!confirm('Вы уверены, что хотите удалить этот паттерн разрешения и все связанные с ним поисковые паттерны?')) return;
        try {
            await fetch(`/api/resolution_patterns/${id}`, { method: 'DELETE' });
            this.loadResolutionPatterns();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async moveResolutionPattern(index, direction) {
        const otherIndex = index + direction;
        [this.resolutionPatterns[index], this.resolutionPatterns[otherIndex]] = [this.resolutionPatterns[otherIndex], this.resolutionPatterns[index]];
        const orderedIds = this.resolutionPatterns.map(p => p.id);
        try {
            await fetch('/api/resolution_patterns/reorder', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(orderedIds) });
        } catch (error) { this.$emit('show-toast', 'Ошибка изменения порядка паттернов разрешения', 'danger'); }
    },
    async addResolutionSearchPattern(resolutionPattern) {
        try {
            const response = await fetch(`/api/resolution_patterns/${resolutionPattern.id}/search_patterns`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pattern: resolutionPattern.newSearchPattern })
            });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Ошибка добавления поискового паттерна разрешения');
            }
            resolutionPattern.newSearchPattern = '';
            this.loadResolutionPatterns();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async deleteResolutionSearchPattern(searchPatternId) {
        if (!confirm('Вы уверены, что хотите удалить этот поисковый паттерн разрешения?')) return;
        try {
            await fetch(`/api/resolution_search_patterns/${searchPatternId}`, { method: 'DELETE' });
            this.loadResolutionPatterns();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async testResolutionPatterns() {
        if (!this.testResolution.filename) {
            this.testResolution.result = 'Введите имя файла для теста.';
            return;
        }
        try {
            const response = await fetch('/api/resolution_patterns/test', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filename: this.testResolution.filename }) });
            const data = await response.json();
            this.testResolution.result = data.result;
        } catch (error) { this.$emit('show-toast', 'Ошибка при тестировании паттернов разрешения', 'danger'); }
    },
  }
};