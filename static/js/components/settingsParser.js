const SettingsParserTab = {
  name: 'SettingsParserTab',
  components: {
    'draggable': vuedraggable,
  },
  template: `
    <div class="accordion" id="parserEditorAccordion">
        <div class="accordion-item">
            <h2 class="accordion-header" id="headingProfiles">
                <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#collapseProfiles" aria-expanded="true" aria-controls="collapseProfiles">
                    Шаг 1: Управление профилями парсера
                </button>
            </h2>
            <div id="collapseProfiles" class="accordion-collapse collapse show" aria-labelledby="headingProfiles" data-bs-parent="#parserEditorAccordion">
                <div class="accordion-body">
                    <p class="text-muted small">Выберите профиль для редактирования или создайте новый. Правила и тестирование появятся ниже после выбора профиля.</p>
                    <div class="modern-input-group">
                        <select v-model="selectedProfileId" class="modern-select" :disabled="isLoading">
                            <option :value="null" disabled>-- Выберите профиль --</option>
                            <option v-for="profile in profiles" :key="profile.id" :value="profile.id">{{ profile.name }}</option>
                        </select>
                        <input v-model.trim="newProfileName" @keyup.enter="createProfile" type="text" class="modern-input" placeholder="Имя нового профиля...">
                        <button @click="createProfile" class="btn btn-success" :disabled="!newProfileName || isLoading"><i class="bi bi-plus-lg"></i></button>
                        <button @click="deleteProfile" class="btn btn-danger" :disabled="!selectedProfileId || isLoading"><i class="bi bi-trash"></i></button>
                    </div>
                </div>
            </div>
        </div>

        <template v-if="selectedProfileId">
            <div class="accordion-item">
                <h2 class="accordion-header" id="headingRules">
                    <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapseRules" aria-expanded="false" aria-controls="collapseRules">
                        Шаг 2: Правила для профиля '{{ selectedProfileName }}'
                    </button>
                </h2>
                <div id="collapseRules" class="accordion-collapse collapse" aria-labelledby="headingRules" data-bs-parent="#parserEditorAccordion">
                    <div class="accordion-body">
                        <div class="d-flex justify-content-end mb-3">
                             <button @click="addRule" class="btn btn-primary btn-sm"><i class="bi bi-plus-circle-dotted me-2"></i>Добавить правило</button>
                        </div>
                        <div v-if="isLoading" class="text-center p-4"><div class="spinner-border" role="status"></div></div>
                        <div v-else-if="rules.length === 0" class="empty-state p-4">Нет правил для этого профиля. Добавьте первое.</div>
                        <div v-else class="rules-list">
                            <transition-group name="list" tag="div">
                                <div v-for="(rule, index) in rules" :key="rule.id" class="list-card rule-card mb-3">
                                    <div class="list-card-header rule-header">
                                        <div class="rule-title" @click="toggleRule(rule.id)">
                                            <i class="bi rule-toggle-icon" :class="openRuleId === rule.id ? 'bi-chevron-down' : 'bi-chevron-right'"></i>
                                            <input type="text" v-model="rule.name" @click.stop class="rule-name-input" placeholder="Имя правила...">
                                        </div>
                                        <div class="rule-controls">
                                           <button @click="moveRule(index, -1)" class="control-btn" :disabled="index === 0" title="Поднять приоритет"><i class="bi bi-arrow-up"></i></button>
                                           <button @click="moveRule(index, 1)" class="control-btn" :disabled="index === rules.length - 1" title="Понизить приоритет"><i class="bi bi-arrow-down"></i></button>
                                           <div class="form-check form-switch mx-2" title="Разрешить обработку следующими правилами после этого">
                                               <input class="form-check-input" type="checkbox" role="switch" v-model="rule.continue_after_match" @change="saveRule(rule)">
                                           </div>
                                           <button @click="saveRule(rule)" class="control-btn text-success" title="Сохранить правило"><i class="bi bi-save"></i></button>
                                           <button @click="deleteRule(rule.id)" class="control-btn text-danger" title="Удалить правило"><i class="bi bi-trash"></i></button>
                                        </div>
                                    </div>
                                    <div v-if="openRuleId === rule.id" class="list-card-body rule-body">
                                        <div class="rule-block if-block">
                                           <div v-for="(cond, c_index) in rule.conditions" :key="c_index">
                                               <div class="condition-group">
                                                    <div class="modern-input-group condition-header-group">
                                                        <span class="input-group-text">ЕСЛИ</span>
                                                        <select v-model="cond.condition_type" class="modern-select">
                                                            <option value="contains">Содержит</option>
                                                            <option value="not_contains">Не содержит</option>
                                                        </select>
                                                        <button @click="removeCondition(rule, c_index)" class="btn btn-danger" title="Удалить условие" :disabled="rule.conditions.length <= 1"><i class="bi bi-x-lg"></i></button>
                                                    </div>
                                                    <div class="modern-input-group">
                                                        <div class="pattern-constructor">
                                                            <draggable
                                                                :list="cond._blocks"
                                                                class="pattern-blocks-container"
                                                                group="blocks"
                                                                handle=".drag-handle"
                                                                item-key="id"
                                                                ghost-class="ghost-block"
                                                                animation="200">
                                                                <template #item="{ element, index }">
                                                                    <div :class="getBlockClasses(element)">
                                                                        <span class="drag-handle">
                                                                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16"><path d="M7 2a1 1 0 1 1-2 0 1 1 0 0 1 2 0zm3 0a1 1 0 1 1-2 0 1 1 0 0 1 2 0zM7 5a1 1 0 1 1-2 0 1 1 0 0 1 2 0zm3 0a1 1 0 1 1-2 0 1 1 0 0 1 2 0zM7 8a1 1 0 1 1-2 0 1 1 0 0 1 2 0zm3 0a1 1 0 1 1-2 0 1 1 0 0 1 2 0zm-3 3a1 1 0 1 1-2 0 1 1 0 0 1 2 0zm3 0a1 1 0 1 1-2 0 1 1 0 0 1 2 0z"/></svg>
                                                                        </span>
                                                                        <div :contenteditable="element.type === 'text'"
                                                                            @blur="element.type === 'text' ? updateBlockValue(cond._blocks[index], $event.target.innerText) : null"
                                                                            @keydown.enter.prevent
                                                                            class="pattern-block-input"
                                                                            :class="{'focus:ring-2 focus:ring-blue-400 rounded-sm': element.type === 'text'}">{{ element.type === 'text' ? element.value : getBlockLabel(element, 'if') }}</div>
                                                                        <button @click="removePatternBlock(cond._blocks, index)" class="pattern-block-remove" title="Удалить блок">&times;</button>
                                                                    </div>
                                                                </template>
                                                            </draggable>
                                                            <div class="palette-footer">
                                                                <draggable
                                                                    :list="blockPalette"
                                                                    class="pattern-palette"
                                                                    :group="{ name: 'blocks', pull: 'clone', put: false }"
                                                                    :clone="cloneBlock"
                                                                    item-key="type"
                                                                    :sort="false">
                                                                    <template #item="{ element }">
                                                                        <div :class="['palette-btn', 'block-type-' + element.type]" :title="element.title">
                                                                            {{ element.label }}
                                                                        </div>
                                                                    </template>
                                                                </draggable>
                                                            </div>
                                                        </div>
                                                        <button @click="addCondition(rule, c_index)" class="btn btn-primary" title="Добавить условие"><i class="bi bi-plus-lg"></i></button>
                                                    </div>
                                               </div>
                                               <div class="logical-operator-container" v-if="c_index < rule.conditions.length - 1">
                                                   <select v-model="cond.logical_operator" class="modern-select rule-select-compact">
                                                       <option value="AND">И</option>
                                                       <option value="OR">ИЛИ</option>
                                                   </select>
                                               </div>
                                           </div>
                                        </div>
                                        <div class="rule-block then-block">
                                            <div v-for="(action, a_index) in rule.actions" :key="a_index" class="condition-group">
                                                <div class="modern-input-group condition-header-group" :class="{'mb-0': action.action_type === 'exclude'}">
                                                    <span class="input-group-text">ТО</span>
                                                    <select v-model="action.action_type" @change="onActionTypeChange(action)" class="modern-select">
                                                        <option value="exclude">Исключить видео</option>
                                                        <option value="extract_single">Извлечь номер серии</option>
                                                        <option value="extract_range">Извлечь диапазон серий</option>
                                                        <option value="extract_season">Установить номер сезона</option>
                                                        <option value="assign_voiceover">Назначить озвучку/тег</option>
                                                        <option value="assign_episode">Назначить номер серии</option>
                                                        <option value="assign_season">Назначить номер сезона</option>
                                                    </select>
                                                    <button @click="removeAction(rule, a_index)" class="btn btn-danger" title="Удалить действие" :disabled="rule.actions.length <= 1"><i class="bi bi-x-lg"></i></button>
                                                </div>
                                                <div class="action-content" v-if="action.action_type !== 'exclude'">
                                                    <div v-if="['extract_single', 'extract_range', 'extract_season'].includes(action.action_type)" class="modern-input-group">
                                                        <div class="pattern-constructor">
                                                            <draggable
                                                                :list="action._action_blocks"
                                                                class="pattern-blocks-container"
                                                                group="blocks"
                                                                handle=".drag-handle"
                                                                item-key="id"
                                                                ghost-class="ghost-block"
                                                                animation="200">
                                                                <template #item="{ element, index }">
                                                                    <div :class="getBlockClasses(element)">
                                                                        <span class="drag-handle">
                                                                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16"><path d="M7 2a1 1 0 1 1-2 0 1 1 0 0 1 2 0zm3 0a1 1 0 1 1-2 0 1 1 0 0 1 2 0zM7 5a1 1 0 1 1-2 0 1 1 0 0 1 2 0zm3 0a1 1 0 1 1-2 0 1 1 0 0 1 2 0zM7 8a1 1 0 1 1-2 0 1 1 0 0 1 2 0zm3 0a1 1 0 1 1-2 0 1 1 0 0 1 2 0zm-3 3a1 1 0 1 1-2 0 1 1 0 0 1 2 0zm3 0a1 1 0 1 1-2 0 1 1 0 0 1 2 0z"/></svg>
                                                                        </span>
                                                                        <div :contenteditable="element.type === 'text'"
                                                                            @blur="element.type === 'text' ? updateBlockValue(action._action_blocks[index], $event.target.innerText) : null"
                                                                            @keydown.enter.prevent
                                                                            class="pattern-block-input"
                                                                            :class="{'focus:ring-2 focus:ring-blue-400 rounded-sm': element.type === 'text'}">{{ element.type === 'text' ? element.value : getBlockLabel(element, 'then', action._action_blocks) }}</div>
                                                                        <button @click="removePatternBlock(action._action_blocks, index)" class="pattern-block-remove" title="Удалить блок">&times;</button>
                                                                    </div>
                                                                </template>
                                                            </draggable>
                                                            <div class="palette-footer">
                                                                 <draggable
                                                                    :list="blockPalette"
                                                                    class="pattern-palette"
                                                                    :group="{ name: 'blocks', pull: 'clone', put: false }"
                                                                    :clone="cloneBlock"
                                                                    item-key="type"
                                                                    :sort="false">
                                                                    <template #item="{ element }">
                                                                        <div :class="['palette-btn', 'block-type-' + element.type]" :title="element.title">
                                                                            {{ element.label }}
                                                                        </div>
                                                                    </template>
                                                                </draggable>
                                                            </div>
                                                        </div>
                                                        <button v-if="a_index === rule.actions.length - 1" @click="addAction(rule)" class="btn btn-primary" title="Добавить действие"><i class="bi bi-plus-lg"></i></button>
                                                    </div>
                                                    <div v-if="action.action_type === 'assign_voiceover'" class="modern-input-group">
                                                        <input type="text" class="modern-input" v-model="action.action_pattern" placeholder="Напр: AniDub">
                                                        <button v-if="a_index === rule.actions.length - 1" @click="addAction(rule)" class="btn btn-primary" title="Добавить действие"><i class="bi bi-plus-lg"></i></button>
                                                    </div>
                                                    <div v-if="action.action_type === 'assign_episode'" class="modern-input-group">
                                                        <input type="number" class="modern-input" v-model="action.action_pattern" placeholder="Номер серии">
                                                        <button v-if="a_index === rule.actions.length - 1" @click="addAction(rule)" class="btn btn-primary" title="Добавить действие"><i class="bi bi-plus-lg"></i></button>
                                                    </div>
                                                    <div v-if="action.action_type === 'assign_season'" class="modern-input-group">
                                                        <input type="number" class="modern-input" v-model="action.action_pattern" placeholder="Номер сезона">
                                                        <button v-if="a_index === rule.actions.length - 1" @click="addAction(rule)" class="btn btn-primary" title="Добавить действие"><i class="bi bi-plus-lg"></i></button>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </transition-group>
                        </div>
                    </div>
                </div>
            </div>

            <div class="accordion-item">
                <h2 class="accordion-header" id="headingTest">
                    <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapseTest" aria-expanded="false" aria-controls="collapseTest">
                        Шаг 3: Тестирование профиля
                    </button>
                </h2>
                <div id="collapseTest" class="accordion-collapse collapse" aria-labelledby="headingTest" data-bs-parent="#parserEditorAccordion">
                    <div class="accordion-body">
                        <p class="text-muted small">Вставьте "сырые" названия видео в поле ниже или получите их с VK, а затем запустите тест.</p>
                        <div class="modern-input-group mb-3">
                            <input v-model.trim="scrapeChannelUrl" type="text" class="modern-input" placeholder="Ссылка на канал VK, например, https://vkvideo.ru/@anidubonline" style="flex-grow: 2;">
                            <div class="modern-input-group-divider"></div>
                            <input v-model.trim="scrapeQuery" type="text" class="modern-input" placeholder="Название для поиска">
                            <button @click="scrapeTestTitles" class="btn btn-primary" :disabled="!scrapeChannelUrl || isScraping">
                                <span v-if="isScraping" class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                                <i v-else class="bi bi-cloud-download"></i>
                                <span class="ms-2">Получить с VK</span>
                            </button>
                        </div>
                        <textarea v-model="testTitles" class="modern-input mb-3" rows="8" placeholder="Название видео 1\nНазвание видео 2"></textarea>
                        <div class="text-end">
                            <button @click="runTest" class="btn btn-success" :disabled="!testTitles || isTesting">
                                <span v-if="isTesting" class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                                <i v-else class="bi bi-play-circle me-2"></i>
                                {{ isTesting ? 'Тестирование...' : 'Запустить тест' }}
                            </button>
                        </div>
                        <div v-if="isTesting" class="text-center p-5"><div class="spinner-border" role="status"></div></div>
                        
                        <transition-group v-else name="list" tag="div" class="test-results-container mt-3">
                            <div v-for="(res, index) in testResults" :key="index" class="test-result-card-compact" :class="getResultClass(res)">
                                <div class="card-title" :title="res.source_data.title">{{ res.source_data.title }}</div>
                                
                                <div v-if="!res.match_events || res.match_events.length === 0" class="card-line">
                                    <span>Правила не применились</span>
                                </div>
                                
                                <div v-else class="card-details">
                                    
                                    <template v-for="(event, event_index) in res.match_events" :key="event_index">
                                        <div v-if="event.action === 'exclude'" class="card-line">
                                            <span><i class="bi bi-x-circle-fill text-danger me-2"></i>Видео исключено</span>
                                            <span class="card-rule-name">{{ event.rule_name }}</span>
                                        </div>
                                        <div v-else v-for="key in getDisplayableKeys(event.extracted)" :key="key" class="card-line">
                                            <span>
                                                {{ formatExtractedKey(key) }}: <strong>{{ formatExtractedValue(key, event.extracted) }}</strong>
                                            </span>
                                            <span class="card-rule-name">{{ event.rule_name }}</span>
                                        </div>
                                    </template>

                                </div>
                            </div>
                        </transition-group>

                    </div>
                </div>
            </div>
        </template>
    </div>
  `,
  data() {
    return {
      profiles: [],
      selectedProfileId: null,
      newProfileName: '',
      isLoading: false,
      rules: [],
      isTesting: false,
      testTitles: '',
      testResults: [],
      openRuleId: null,
      blockPalette: [
        { type: 'text', label: 'Текст', title: 'Точный текст' },
        { type: 'number', label: 'Число', title: 'Любое число (1, 2, 10, 155...)' },
        { type: 'whitespace', label: 'Пробел', title: 'Один или несколько пробелов' },
        { type: 'any_text', label: '*', title: 'Любой текст (нежадный поиск)' },
        { type: 'start_of_line', label: 'Начало', title: 'Соответствует началу названия' },
        { type: 'end_of_line', label: 'Конец', title: 'Соответствует концу названия' },
      ],
      scrapeChannelUrl: '',
      scrapeQuery: '',
      isScraping: false,
      scrapedItems: [],
    };
  },
  emits: ['show-toast'],
  computed: {
    scrapedTitlesOnly() {
        return this.scrapedItems.map(item => item.title).join('\n');
    },
    selectedProfileName() {
        const profile = this.profiles.find(p => p.id === this.selectedProfileId);
        return profile ? profile.name : '';
    },
  },
  watch: {
    selectedProfileId(newId) {
        if (newId) {
            this.loadRules();
        } else {
            this.rules = [];
        }
        this.testResults = [];
    }
  },
  methods: {
    emitToast(message, type) {
      this.$emit('show-toast', message, type);
    },
    async load() {
      await this.loadProfiles();
    },
    async loadProfiles() {
        this.isLoading = true;
        try {
            const response = await fetch('/api/parser-profiles');
            if (!response.ok) throw new Error('Ошибка загрузки профилей');
            this.profiles = await response.json();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); } 
        finally { this.isLoading = false; }
    },
    async createProfile() {
        if (!this.newProfileName) return;
        this.isLoading = true;
        try {
            const response = await fetch('/api/parser-profiles', {
                method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ name: this.newProfileName })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Ошибка создания профиля');
            this.newProfileName = '';
            await this.loadProfiles();
            this.selectedProfileId = data.id;
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
        finally { this.isLoading = false; }
    },
    async deleteProfile() {
        if (!this.selectedProfileId || !confirm(`Вы уверены, что хотите удалить профиль "${this.selectedProfileName}" и все его правила?`)) return;
        this.isLoading = true;
        try {
            const response = await fetch(`/api/parser-profiles/${this.selectedProfileId}`, { method: 'DELETE' });
            if (!response.ok) throw new Error((await response.json()).error || 'Ошибка удаления профиля');
            this.selectedProfileId = null;
            await this.loadProfiles();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
        finally { this.isLoading = false; }
    },
    async loadRules() {
        if (!this.selectedProfileId) return;
        this.isLoading = true; this.rules = []; this.testResults = []; this.openRuleId = null;
        try {
            const response = await fetch(`/api/parser-profiles/${this.selectedProfileId}/rules`);
            if (!response.ok) throw new Error('Ошибка загрузки правил');
            const rawRules = await response.json();
            this.rules = rawRules.map(rule => {
                let actions = [];
                try {
                    actions = JSON.parse(rule.action_pattern || '[]');
                    if (!Array.isArray(actions)) actions = [];
                } catch(e) { actions = []; }
                return {
                    ...rule,
                    id: rule.id,
                    conditions: rule.conditions.map(c => ({...c, _blocks: this.parsePatternJson(c.pattern)})),
                    actions: actions.map(a => ({...a, _action_blocks: this.parsePatternJson(a.action_pattern)}))
                }
            });
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
        finally { this.isLoading = false; }
    },

    getDisplayableKeys(extractedData) {
        if (!extractedData) return [];
        // Просто отфильтровываем ключ 'end' из массива ключей
        return Object.keys(extractedData).filter(key => key !== 'end');
    },

    addRule() {
        const newRule = {
            id: 'new-' + Date.now(),
            profile_id: this.selectedProfileId, name: 'Новое правило',
            conditions: [{ condition_type: 'contains', _blocks: [{type: 'text', value: '', id: Date.now()}], logical_operator: 'AND' }],
            actions: [{ action_type: 'exclude', action_pattern: '[]', _action_blocks: [] }],
            is_new: true,
            continue_after_match: false,
        };
        this.rules.push(newRule);
        this.openRuleId = newRule.id;
    },
    prepareRuleForSave(rule) {
        const payload = JSON.parse(JSON.stringify(rule));
        payload.conditions.forEach(cond => {
            cond.pattern = JSON.stringify((cond._blocks || []).map(({ id, ...rest }) => rest));
            delete cond._blocks;
        });
        const actionsToSave = (payload.actions || []).map(action => {
            const savedAction = { action_type: action.action_type, action_pattern: action.action_pattern ?? '' };
            if (['extract_single', 'extract_range', 'extract_season'].includes(action.action_type)) {
                savedAction.action_pattern = JSON.stringify((action._action_blocks || []).map(({ id, ...rest }) => rest));
            }
            return savedAction;
        });
        payload.action_pattern = JSON.stringify(actionsToSave);
        delete payload.actions;
        delete payload.is_new; 
        return payload;
    },
    async saveRule(rule) {
        const isNew = !!rule.is_new;
        const url = isNew ? `/api/parser-profiles/${this.selectedProfileId}/rules` : `/api/parser-rules/${rule.id}`;
        const method = isNew ? 'POST' : 'PUT';
        try {
            const payload = this.prepareRuleForSave(rule);
            const response = await fetch(url, { method: method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Ошибка сохранения правила');
            this.$emit('show-toast', 'Правило сохранено', 'success');
            if (isNew) {
                await this.loadRules();
                this.openRuleId = data.id;
            }
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async deleteRule(ruleId) {
        if (typeof ruleId === 'string' && ruleId.startsWith('new-')) {
            this.rules = this.rules.filter(r => r.id !== ruleId);
            return;
        }
        if (!confirm('Удалить это правило?')) return;
        try {
            const response = await fetch(`/api/parser-rules/${ruleId}`, { method: 'DELETE' });
            if (!response.ok) throw new Error('Ошибка удаления правила');
            this.loadRules();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
    },
    async moveRule(index, direction) {
        const otherIndex = index + direction;
        [this.rules[index], this.rules[otherIndex]] = [this.rules[otherIndex], this.rules[index]];
        const orderedIds = this.rules.filter(r => !r.is_new).map(r => r.id);
        if (orderedIds.length < 2) return;
        try {
            await fetch('/api/parser-rules/reorder', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(orderedIds) });
        } catch (error) { this.$emit('show-toast', 'Ошибка изменения порядка', 'danger'); this.loadRules(); }
    },
    toggleRule(ruleId) { this.openRuleId = this.openRuleId === ruleId ? null : ruleId; },
    parsePatternJson(jsonString) {
        try {
            if (!jsonString) return [];
            const blocks = JSON.parse(jsonString);
            return Array.isArray(blocks) ? blocks.map(b => ({...b, id: Date.now() + Math.random()})) : [];
        } catch (e) { return []; }
    },
    cloneBlock(original) { return { id: Date.now() + Math.random(), type: original.type, value: original.type === 'text' ? '' : undefined }; },
    removePatternBlock(targetBlocks, blockIndex) { targetBlocks.splice(blockIndex, 1); },
    updateBlockValue(block, newText) { if (block) { block.value = newText.trim(); } },
    getBlockClasses(block) {
        let classes = 'pattern-block';
        if (block.type === 'text') { classes += ' block-type-text'; } 
        else { classes += ` block-type-${block.type}`; }
        return classes;
    },
    addCondition(rule, index) {
        const newCondition = { condition_type: 'contains', _blocks: [], logical_operator: 'AND' };
        rule.conditions.splice(index + 1, 0, newCondition);
    },
    removeCondition(rule, index) { rule.conditions.splice(index, 1); },
    addAction(rule) {
        if (!rule.actions) rule.actions = [];
        rule.actions.push({ action_type: 'exclude', action_pattern: '[]', _action_blocks: [] });
    },
    removeAction(rule, index) { rule.actions.splice(index, 1); },
    onActionTypeChange(action) {
        if (['extract_single', 'extract_range', 'extract_season'].includes(action.action_type)) {
            action.action_pattern = '[]';
            action._action_blocks = [];
        } else if (action.action_type === 'assign_episode' || action.action_type === 'assign_season') {
            action.action_pattern = '1';
        } else {
             action._action_blocks = [];
             action.action_pattern = '';
        }
    },
    getBlockLabel(block, context, container) {
        if (block.type === 'number' && context === 'then') {
            const numberBlocks = container.filter(b => b.type === 'number');
            const captureIndex = numberBlocks.indexOf(block) + 1;
            return `Число #${captureIndex}`;
        }
        return this.blockPalette.find(p => p.type === block.type)?.label || 'Неизвестный';
    },
    async runTest() {
        if (!this.testTitles || !this.selectedProfileId) return;
        this.isTesting = true; this.testResults = [];
        try {
            const titles = this.testTitles.split('\n').filter(t => t.trim() !== '');
            const response = await fetch('/api/parser-profiles/test', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ profile_id: this.selectedProfileId, titles: titles })
            });
            if (!response.ok) throw new Error('Ошибка тестирования');
            this.testResults = await response.json();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
        finally { this.isTesting = false; }
    },
    getResultClass(res) {
        if (!res.match_events || res.match_events.length === 0) {
            return 'no-match';
        }
        const lastEvent = res.match_events[res.match_events.length - 1];
        if (lastEvent.action === 'exclude') {
            return 'excluded';
        }
        if (res.final_result && res.final_result.error) {
            return 'error';
        }
        return 'success';
    },
    formatExtractedKey(key) {
        const keyMap = {
            'season': 'Сезон', 'episode': 'Серия',
            'start': 'Компиляция', 'voiceover': 'Озвучка',
        };
        return keyMap[key] || `'${key}'`;
    },
    formatExtractedValue(key, extractedData) {
        if (key === 'end') return null; 
        if (key === 'start') {
            return `${extractedData.start}-${extractedData.end}`;
        }
        const value = extractedData[key];
        return (value !== null && value !== undefined) ? value : '';
    },
    async scrapeTestTitles() {
        if (!this.scrapeChannelUrl) return;
        this.isScraping = true;
        this.$emit('show-toast', 'Запущен сбор названий через VK API...', 'info');
        try {
            const response = await fetch('/api/parser-profiles/scrape-titles', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ channel_url: this.scrapeChannelUrl, query: this.scrapeQuery })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Ошибка сбора названий');
            this.scrapedItems = data;
            this.testTitles = this.scrapedTitlesOnly;
            this.$emit('show-toast', `Собрано ${data.length} записей.`, 'success');
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        } finally { this.isScraping = false; }
    },
  }
};