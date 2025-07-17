const ParserRuleEditor = {
  name: 'ParserRuleEditor',
  // Локальная регистрация удалена, так как компонент теперь глобальный
  props: {
    profileId: { type: Number, required: true },
    profileName: { type: String, required: true },
  },
  template: `
    <div>
        <div class="modern-fieldset mb-4">
            <div class="fieldset-header d-flex justify-content-between align-items-center">
                <h6 class="fieldset-title mb-0">Правила для профиля: {{ profileName }}</h6>
                <button @click="addRule" class="btn btn-primary btn-sm"><i class="bi bi-plus-circle-dotted me-2"></i>Добавить правило</button>
            </div>
            <div class="fieldset-content">
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
        <div class="modern-fieldset mb-4">
            <div class="fieldset-header">
                <h6 class="fieldset-title mb-0">Получение тестовых данных с VK</h6>
            </div>
            <div class="fieldset-content">
                <p class="text-muted small">Вставьте ссылку на канал и название для поиска, чтобы получить "сырой" список названий для дальнейшей настройки правил.</p>
                <div class="modern-input-group mb-3">
                    <input v-model.trim="scrapeChannelUrl" type="text" class="modern-input" placeholder="Ссылка на канал, например, https://vkvideo.ru/@anidubonline" style="flex-grow: 2;">
                    <div class="modern-input-group-divider"></div>
                    <input v-model.trim="scrapeQuery" type="text" class="modern-input" placeholder="Название для поиска, например, Противостояние святого">
                    <button @click="scrapeTestTitles" class="btn btn-primary" :disabled="!scrapeChannelUrl || !scrapeQuery || isScraping">
                        <span v-if="isScraping" class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                        <i v-else class="bi bi-cloud-download"></i>
                        <span class="ms-2">Получить</span>
                    </button>
                </div>
                <div v-if="scrapedItems.length > 0">
                    <textarea class="modern-input" rows="8" readonly>{{ scrapedTitlesOnly }}</textarea>
                </div>
            </div>
        </div>
        <div class="modern-fieldset">
            <div class="fieldset-header"><h6 class="fieldset-title mb-0">Тестирование профиля: {{ profileName }}</h6></div>
            <div class="fieldset-content">
                <p class="text-muted small">Вставьте "сырые" названия видео (каждое с новой строки) для проверки работы правил.</p>
                <div class="row">
                    <div class="col-md-6">
                        <textarea v-model="testTitles" class="modern-input" rows="10" placeholder="Название видео 1\nНазвание видео 2"></textarea>
                    </div>
                    <div class="col-md-6">
                        <div v-if="isTesting" class="text-center p-5"><div class="spinner-border" role="status"></div><p>Тестирование...</p></div>
                        <div v-else class="test-results">
                            <div v-for="(res, index) in testResults" :key="index" class="test-result-item" :class="getResultClass(res)">
                                <div class="test-result-title" :title="res.title">{{ res.title }}</div>
                                <div class="test-result-rule">{{ res.matched_rule_name }}</div>
                                <div class="test-result-data">{{ formatResultData(res.result) }}</div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="text-end mt-3">
                    <button @click="runTest" class="btn btn-success" :disabled="!testTitles || isTesting">
                        <i class="bi bi-play-circle me-2"></i>Запустить тест
                    </button>
                </div>
            </div>
        </div>
    </div>
  `,
  data() {
    return {
      rules: [],
      isLoading: false,
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
  emits: ['show-toast', 'reload-rules'],
  computed: {
    scrapedTitlesOnly() {
        return this.scrapedItems.map(item => item.title).join('\n');
    }
  },
  watch: {
    profileId: {
        immediate: true,
        handler(newId) {
            if (newId) {
                this.loadRules();
            }
        }
    }
  },
  methods: {
    async loadRules() {
        if (!this.profileId) return;
        this.isLoading = true; this.rules = []; this.testResults = []; this.openRuleId = null;
        try {
            const response = await fetch(`/api/parser-profiles/${this.profileId}/rules`);
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
    addRule() {
        const newRule = {
            id: 'new-' + Date.now(),
            profile_id: this.profileId, name: 'Новое правило',
            conditions: [{ condition_type: 'contains', _blocks: [{type: 'text', value: '', id: Date.now()}], logical_operator: 'AND' }],
            actions: [{ action_type: 'exclude', action_pattern: '[]', _action_blocks: [] }],
            is_new: true,
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
            const savedAction = {
                action_type: action.action_type,
                action_pattern: action.action_pattern ?? ''
            };
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
        const url = isNew ? `/api/parser-profiles/${this.profileId}/rules` : `/api/parser-rules/${rule.id}`;
        const method = isNew ? 'POST' : 'PUT';
        try {
            const payload = this.prepareRuleForSave(rule);
            const response = await fetch(url, {
                method: method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
            });
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
            await fetch('/api/parser-rules/reorder', {
                method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(orderedIds)
            });
        } catch (error) { this.$emit('show-toast', 'Ошибка изменения порядка', 'danger'); this.loadRules(); }
    },
    toggleRule(ruleId) { 
        this.openRuleId = this.openRuleId === ruleId ? null : ruleId;
    },
    parsePatternJson(jsonString) {
        try {
            if (!jsonString) return [];
            const blocks = JSON.parse(jsonString);
            return Array.isArray(blocks) ? blocks.map(b => ({...b, id: Date.now() + Math.random()})) : [];
        } catch (e) { return []; }
    },
    cloneBlock(original) {
        return {
            id: Date.now() + Math.random(),
            type: original.type,
            value: original.type === 'text' ? '' : undefined,
        };
    },
    removePatternBlock(targetBlocks, blockIndex) {
        targetBlocks.splice(blockIndex, 1);
    },
    updateBlockValue(block, newText) {
        if (block) {
            block.value = newText.trim();
        }
    },
    getBlockClasses(block) {
        let classes = 'pattern-block';
        if (block.type === 'text') {
            classes += ' text-input-container';
        } else {
            classes += ` block-type-${block.type}`;
        }
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
        if (!this.testTitles || !this.profileId) return;
        this.isTesting = true; this.testResults = [];
        try {
            const titles = this.testTitles.split('\n').filter(t => t.trim() !== '');
            const response = await fetch('/api/parser-profiles/test', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ profile_id: this.profileId, titles: titles })
            });
            if (!response.ok) throw new Error('Ошибка тестирования');
            this.testResults = await response.json();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
        finally { this.isTesting = false; }
    },
    getResultClass(result) {
        if (!result.result) return 'result-no-match';
        if (result.result.action === 'exclude') return 'result-exclude';
        if (result.result.error) return 'result-error';
        return 'result-success';
    },
    formatResultData(result) {
        if (!result) return '-';
        if (result.action === 'exclude') return 'Исключено';
        if (result.error) return `Ошибка: ${Array.isArray(result.error) ? result.error.join(', ') : result.error}`;
        if (result.extracted && Object.keys(result.extracted).length > 0) {
            return Object.entries(result.extracted)
                .map(([key, value]) => `${key}: ${value}`)
                .join('; ');
        }
        return 'Совпадение';
    },
    async scrapeTestTitles() {
        if (!this.scrapeChannelUrl || !this.scrapeQuery) return;
        this.isScraping = true; this.scrapedItems = [];
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