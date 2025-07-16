const SettingsParserTab = {
  name: 'SettingsParserTab',
  template: `
    <div class="settings-tab-content">
        <div class="modern-fieldset mb-4">
            <div class="fieldset-header">
                <h6 class="fieldset-title mb-0">Управление профилями парсера</h6>
            </div>
            <div class="fieldset-content">
                <p class="text-muted small">Профили позволяют создавать наборы правил для разных типов контента или каналов. Выберите профиль для редактирования или создайте новый.</p>
                <div class="modern-input-group mb-3">
                    <select v-model="selectedProfileId" @change="loadRules" class="modern-select" :disabled="isLoading">
                        <option :value="null" disabled>-- Выберите профиль --</option>
                        <option v-for="profile in profiles" :key="profile.id" :value="profile.id">{{ profile.name }}</option>
                    </select>
                    <input v-model.trim="newProfileName" @keyup.enter="createProfile" type="text" class="modern-input" placeholder="Имя нового профиля...">
                    <button @click="createProfile" class="btn btn-success" :disabled="!newProfileName || isLoading"><i class="bi bi-plus-lg"></i></button>
                    <button @click="deleteProfile" class="btn btn-danger" :disabled="!selectedProfileId || isLoading"><i class="bi bi-trash"></i></button>
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

        <div v-if="selectedProfileId" class="modern-fieldset mb-4">
            <div class="fieldset-header d-flex justify-content-between align-items-center">
                <h6 class="fieldset-title mb-0">Правила для профиля: {{ selectedProfileName }}</h6>
                <button @click="addRule" class="btn btn-primary btn-sm"><i class="bi bi-plus-circle-dotted me-2"></i>Добавить правило</button>
            </div>
            <div class="fieldset-content">
                <div v-if="isLoading" class="text-center p-4"><div class="spinner-border" role="status"></div></div>
                <div v-else-if="rules.length === 0" class="empty-state p-4">Нет правил для этого профиля. Добавьте первое.</div>
                
                <transition-group name="list" tag="div" class="rules-list">
                    <div v-for="(rule, index) in rules" :key="rule.id" class="list-card rule-card">
                        <div class="list-card-header rule-header">
                            <div class="rule-title" @click="toggleRule(rule.id)">
                                <i class="bi rule-toggle-icon" :class="isRuleCollapsed(rule.id) ? 'bi-chevron-right' : 'bi-chevron-down'"></i>
                                <input type="text" v-model="rule.name" @click.stop class="rule-name-input" placeholder="Имя правила...">
                            </div>
                            <div class="rule-controls">
                               <button @click="moveRule(index, -1)" class="control-btn" :disabled="index === 0" title="Поднять приоритет"><i class="bi bi-arrow-up"></i></button>
                               <button @click="moveRule(index, 1)" class="control-btn" :disabled="index === rules.length - 1" title="Понизить приоритет"><i class="bi bi-arrow-down"></i></button>
                               <button @click="saveRule(rule)" class="control-btn text-success" title="Сохранить правило"><i class="bi bi-save"></i></button>
                               <button @click="deleteRule(rule.id)" class="control-btn text-danger" title="Удалить правило"><i class="bi bi-trash"></i></button>
                            </div>
                        </div>
                        <div v-if="!isRuleCollapsed(rule.id)" class="list-card-body rule-body">
                            <div class="rule-block if-block">
                               <div v-for="(cond, c_index) in rule.conditions" :key="c_index">
                                   <div class="condition-group">
                                       <div class="condition-header">
                                           <div class="rule-block-header">
                                               <span>ЕСЛИ</span>
                                               <select v-model="cond.condition_type" class="modern-select rule-select-compact">
                                                   <option value="contains">Содержит</option>
                                                   <option value="not_contains">Не содержит</option>
                                               </select>
                                           </div>
                                           <button @click="removeCondition(rule, c_index)" class="control-btn text-danger" title="Удалить условие"><i class="bi bi-x-lg"></i></button>
                                       </div>
                                       <div class="pattern-constructor">
                                           <div class="pattern-blocks-container"
                                                @dragover.prevent="dragOver($event, cond._blocks)" 
                                                @dragleave.prevent="dragLeave" 
                                                @drop="onDrop($event, cond._blocks, dropIndex)">
                                                <transition-group name="list">
                                                    <template v-for="(block, b_index) in cond._blocks" :key="block.id">
                                                        <div class="drop-placeholder" v-if="dropIndex === b_index"></div>
                                                        <div :class="['pattern-block', 'block-type-' + block.type]" 
                                                            draggable="true" @dragstart="onDragStart($event, cond._blocks, b_index)">
                                                            <span v-if="block.type !== 'text'">{{ getBlockLabel(block, 'if') }}</span>
                                                            <input v-if="block.type === 'text'" v-model="block.value" type="text" class="pattern-block-input" placeholder="Текст...">
                                                            <button @click="removePatternBlock(cond._blocks, b_index)" class="pattern-block-remove" title="Удалить блок">&times;</button>
                                                        </div>
                                                    </template>
                                                </transition-group>
                                                <div class="drop-placeholder" v-if="dropIndex === cond._blocks.length"></div>
                                           </div>
                                           <div class="pattern-palette">
                                                <div v-for="p_block in blockPalette" :key="p_block.type" 
                                                    :class="['palette-btn', 'block-type-' + p_block.type]" 
                                                    :title="p_block.title" 
                                                    draggable="true"
                                                    @dragstart="onDragStart($event, null, -1, p_block.type)"
                                                    @click="addPatternBlock(cond._blocks, p_block.type)">
                                                    {{ p_block.label }}
                                                </div>
                                           </div>
                                       </div>
                                   </div>
                                   <div class="logical-operator-container" v-if="c_index < rule.conditions.length - 1">
                                       <select v-model="cond.logical_operator" class="modern-select rule-select-compact">
                                           <option value="AND">И</option>
                                           <option value="OR">ИЛИ</option>
                                       </select>
                                   </div>
                               </div>
                               <div class="text-end mt-2"><button @click="addCondition(rule)" class="control-btn text-primary" title="Добавить условие"><i class="bi bi-plus-lg"></i></button></div>
                            </div>
                            
                            <div class="rule-block then-block">
                                <div v-for="(action, a_index) in rule.actions" :key="a_index" class="condition-group mb-3">
                                    <div class="condition-header">
                                        <div class="rule-block-header">
                                            <span>ТО</span>
                                            <select v-model="action.action_type" @change="onActionTypeChange(action)" class="modern-select rule-select-compact">
                                               <option value="exclude">Исключить видео</option>
                                               <option value="extract_single">Извлечь номер серии</option>
                                               <option value="extract_range">Извлечь диапазон серий</option>
                                               <option value="extract_season">Установить номер сезона</option>
                                               <option value="assign_voiceover">Назначить озвучку/тег</option>
                                               <option value="assign_episode_number">Назначить номер серии/сезона</option>
                                            </select>
                                        </div>
                                        <button @click="removeAction(rule, a_index)" class="control-btn text-danger" title="Удалить действие"><i class="bi bi-x-lg"></i></button>
                                    </div>
                                    <div class="action-content">
                                       <div v-if="['extract_single', 'extract_range', 'extract_season'].includes(action.action_type)" class="pattern-constructor">
                                           <div class="pattern-blocks-container"
                                                @dragover.prevent="dragOver($event, action._action_blocks)" 
                                                @dragleave.prevent="dragLeave" 
                                                @drop="onDrop($event, action._action_blocks, dropIndex)">
                                                <transition-group name="list">
                                                    <template v-for="(block, b_index) in action._action_blocks" :key="block.id">
                                                        <div class="drop-placeholder" v-if="dropIndex === b_index"></div>
                                                        <div :class="['pattern-block', 'block-type-' + block.type]" 
                                                            draggable="true" @dragstart="onDragStart($event, action._action_blocks, b_index)">
                                                            <span v-if="block.type !== 'text'">{{ getBlockLabel(block, 'then', action._action_blocks) }}</span>
                                                            <input v-if="block.type === 'text'" v-model="block.value" type="text" class="pattern-block-input" placeholder="Текст...">
                                                            <button @click="removePatternBlock(action._action_blocks, b_index)" class="pattern-block-remove" title="Удалить блок">&times;</button>
                                                        </div>
                                                    </template>
                                                </transition-group>
                                                <div class="drop-placeholder" v-if="dropIndex === action._action_blocks.length"></div>
                                           </div>
                                           <div class="pattern-palette">
                                                <div v-for="p_block in blockPalette" :key="p_block.type" 
                                                    :class="['palette-btn', 'block-type-' + p_block.type]" 
                                                    :title="p_block.title" 
                                                    draggable="true"
                                                    @dragstart="onDragStart($event, null, -1, p_block.type)"
                                                    @click="addPatternBlock(action._action_blocks, p_block.type)">
                                                    {{ p_block.label }}
                                                </div>
                                           </div>
                                       </div>
                                       <div v-if="action.action_type === 'assign_voiceover'" class="modern-input-group">
                                           <input type="text" class="modern-input" v-model="action.action_pattern" placeholder="Напр: AniDub">
                                       </div>
                                       <div v-if="action.action_type === 'assign_episode_number'" class="d-flex gap-2">
                                           <input type="number" class="modern-input" :value="getAssignedNumber(action).season" @input="updateAssignedNumber(action, 'season', $event)" placeholder="Сезон">
                                           <input type="number" class="modern-input" :value="getAssignedNumber(action).episode" @input="updateAssignedNumber(action, 'episode', $event)" placeholder="Серия">
                                       </div>
                                    </div>
                                </div>
                                <div class="text-end mt-2"><button @click="addAction(rule)" class="control-btn text-primary" title="Добавить действие"><i class="bi bi-plus-lg"></i></button></div>
                            </div>
                        </div>
                    </div>
                </transition-group>
            </div>
        </div>

        <div v-if="selectedProfileId" class="modern-fieldset">
            <div class="fieldset-header"><h6 class="fieldset-title mb-0">Тестирование профиля: {{ selectedProfileName }}</h6></div>
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
      profiles: [],
      selectedProfileId: null,
      newProfileName: '',
      rules: [],
      isLoading: false,
      isTesting: false,
      testTitles: '',
      testResults: [],
      collapsedRules: {},
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
      draggedItem: null,
      dropIndex: null, // Index for showing the placeholder
    };
  },
  emits: ['show-toast'],
  computed: {
    selectedProfileName() {
        const profile = this.profiles.find(p => p.id === this.selectedProfileId);
        return profile ? profile.name : '';
    },
    scrapedTitlesOnly() {
        return this.scrapedItems.map(item => item.title).join('\n');
    }
  },
  methods: {
    async load() { await this.loadProfiles(); },
    async loadProfiles() {
        this.isLoading = true;
        try {
            const response = await fetch('/api/parser-profiles');
            if (!response.ok) throw new Error('Ошибка загрузки профилей');
            this.profiles = await response.json();
            if (this.profiles.length > 0 && !this.selectedProfileId) {
                this.selectedProfileId = this.profiles[0].id;
            }
            if (this.selectedProfileId) {
                await this.loadRules();
            }
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
            await this.loadRules();
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
            this.rules = [];
            await this.loadProfiles();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
        finally { this.isLoading = false; }
    },
    async loadRules() {
        if (!this.selectedProfileId) return;
        this.isLoading = true; this.rules = []; this.testResults = []; this.collapsedRules = {};
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
                    conditions: rule.conditions.map(c => ({...c, _blocks: this.parsePatternJson(c.pattern)})),
                    actions: actions.map(a => ({...a, _action_blocks: this.parsePatternJson(a.action_pattern)})),
                    collapsed: true,
                }
            });

            this.rules.forEach(rule => this.collapsedRules[rule.id] = true);
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
        finally { this.isLoading = false; }
    },
    addRule() {
        const newRule = {
            id: 'new-' + Date.now(),
            profile_id: this.selectedProfileId, name: 'Новое правило',
            conditions: [{ condition_type: 'contains', _blocks: [{type: 'text', value: '', id: Date.now()}], logical_operator: 'AND' }],
            actions: [{ action_type: 'exclude', action_pattern: '[]', _action_blocks: [] }],
            is_new: true,
        };
        this.rules.push(newRule);
        this.collapsedRules[newRule.id] = false;
    },
    prepareRuleForSave(rule) {
        const payload = JSON.parse(JSON.stringify(rule));
        
        payload.conditions.forEach(cond => {
            cond.pattern = JSON.stringify((cond._blocks || []).map(({ id, ...rest }) => rest)); // Remove internal id
            delete cond._blocks;
        });

        const actionsToSave = (payload.actions || []).map(action => {
            const savedAction = {
                action_type: action.action_type,
                action_pattern: action.action_pattern || ''
            };
            if (['extract_single', 'extract_range', 'extract_season'].includes(action.action_type)) {
                savedAction.action_pattern = JSON.stringify((action._action_blocks || []).map(({ id, ...rest }) => rest)); // Remove internal id
            }
            return savedAction;
        });
        
        payload.action_pattern = JSON.stringify(actionsToSave);

        delete payload.actions;
        delete payload.is_new; 
        delete payload.collapsed;
        return payload;
    },
    async saveRule(rule) {
        const isNew = !!rule.is_new;
        const url = isNew ? `/api/parser-profiles/${this.selectedProfileId}/rules` : `/api/parser-rules/${rule.id}`;
        const method = isNew ? 'POST' : 'PUT';
        try {
            const payload = this.prepareRuleForSave(rule);
            const response = await fetch(url, {
                method: method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Ошибка сохранения правила');
            this.$emit('show-toast', 'Правило сохранено', 'success');
            if (isNew) await this.loadRules();
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
            await this.loadRules();
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
    toggleRule(ruleId) { this.collapsedRules[ruleId] = !this.collapsedRules[ruleId]; },
    isRuleCollapsed(ruleId) { return !!this.collapsedRules[ruleId]; },
    parsePatternJson(jsonString) {
        try {
            if (!jsonString) return [];
            const blocks = JSON.parse(jsonString);
            return Array.isArray(blocks) ? blocks.map(b => ({...b, id: Date.now() + Math.random()})) : [];
        } catch (e) { return []; }
    },
    addPatternBlock(targetBlocks, blockType) { 
        targetBlocks.push({ type: blockType, value: blockType === 'text' ? '' : undefined, id: Date.now() }); 
    },
    removePatternBlock(targetBlocks, blockIndex) { targetBlocks.splice(blockIndex, 1); },
    addCondition(rule) { rule.conditions.push({ condition_type: 'contains', _blocks: [], logical_operator: 'AND' }); },
    removeCondition(rule, index) { rule.conditions.splice(index, 1); },
    addAction(rule) {
        if (!rule.actions) rule.actions = [];
        rule.actions.push({ action_type: 'exclude', action_pattern: '[]', _action_blocks: [] });
    },
    removeAction(rule, index) { rule.actions.splice(index, 1); },
    // Drag and Drop Methods
    onDragStart(event, fromContainer, fromIndex, blockType) {
        event.dataTransfer.effectAllowed = 'move';
        this.draggedItem = { fromContainer, fromIndex, blockType };
    },
    dragOver(event, targetContainer) {
        const containerRect = event.currentTarget.getBoundingClientRect();
        const children = Array.from(event.currentTarget.querySelectorAll('.pattern-block, .drop-placeholder'));
        
        let closest = null;
        let closestDist = Infinity;
        
        children.forEach((child, index) => {
            const childRect = child.getBoundingClientRect();
            const dist = event.clientX - (childRect.left + childRect.width / 2);
            if (dist < 0 && dist > -closestDist) {
                closestDist = -dist;
                closest = { index: index, element: child };
            }
        });

        if (closest) {
            this.dropIndex = closest.index;
        } else {
            this.dropIndex = targetContainer.length;
        }
    },
    dragLeave() {
        this.dropIndex = null;
    },
    onDrop(event, targetContainer, dropIndex) {
        if (!this.draggedItem) return;

        // Item from palette
        if (this.draggedItem.blockType) {
            targetContainer.splice(dropIndex, 0, {
                type: this.draggedItem.blockType,
                value: this.draggedItem.blockType === 'text' ? '' : undefined,
                id: Date.now()
            });
        }
        // Item from another container
        else if (this.draggedItem.fromContainer) {
            const item = this.draggedItem.fromContainer.splice(this.draggedItem.fromIndex, 1)[0];
            targetContainer.splice(dropIndex, 0, item);
        }
        
        this.draggedItem = null;
        this.dropIndex = null;
    },
    // Action Block Methods
    onActionTypeChange(action) {
        if (['extract_single', 'extract_range', 'extract_season'].includes(action.action_type)) {
            action.action_pattern = '[]';
            action._action_blocks = [];
        } else if (action.action_type === 'assign_episode_number') {
            action.action_pattern = JSON.stringify({ season: 1, episode: 1 });
        } else {
             action._action_blocks = [];
             action.action_pattern = '';
        }
    },
    getAssignedNumber(action) {
        try { return JSON.parse(action.action_pattern); } catch (e) { return { season: '', episode: '' }; }
    },
    updateAssignedNumber(action, key, event) {
        const data = this.getAssignedNumber(action);
        data[key] = parseInt(event.target.value, 10) || 0;
        action.action_pattern = JSON.stringify(data);
    },
    getBlockLabel(block, context, container) {
        if (block.type === 'number' && context === 'then') {
            const numberBlocks = container.filter(b => b.type === 'number');
            const captureIndex = numberBlocks.indexOf(block) + 1;
            return `Число #${captureIndex}`;
        }
        return this.blockPalette.find(p => p.type === block.type)?.label || 'Неизвестный';
    },
    // Testing Methods
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
    // Scraper Methods
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