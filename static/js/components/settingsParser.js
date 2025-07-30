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
                
                <div class="field-group">
                    <constructor-group>
                        <template v-if="!editingProfileId">
                            <div class="constructor-item item-label-icon" title="Профиль"><i class="bi bi-person-check-fill"></i></div>
                            <constructor-item-select :options="profileOptions" v-model="selectedProfileId"></constructor-item-select>
                            <div class="constructor-item item-floating-label">
                                <input v-model.trim="newProfileName" @keyup.enter="createProfile" type="text" class="item-input" id="new-profile-name" placeholder=" ">
                                <label for="new-profile-name">Имя нового профиля...</label>
                            </div>
                            <div class="constructor-item item-button-group">
                                <button @click="createProfile" class="btn-icon btn-add" :disabled="!newProfileName || isLoading" title="Создать"><i class="bi bi-plus-lg"></i></button>
                                <button @click="startEditingProfile" class="btn-icon btn-edit" :disabled="!selectedProfileId || isLoading" title="Переименовать"><i class="bi bi-pencil"></i></button>
                                <button @click="deleteProfile" class="btn-icon btn-delete" :disabled="!selectedProfileId || isLoading" title="Удалить"><i class="bi bi-trash"></i></button>
                            </div>
                        </template>
                        <template v-else>
                            <div class="constructor-item item-floating-label">
                                <input v-model.trim="editingProfileName" @keyup.enter="saveProfileName" @keyup.esc="cancelEditing" type="text" class="item-input" placeholder=" " ref="editProfileInput">
                                <label>Новое имя профиля...</label>
                            </div>
                            <div class="constructor-item item-button-group">
                                <button @click="saveProfileName" class="btn-icon btn-confirm" :disabled="!editingProfileName" title="Сохранить"><i class="bi bi-check-lg"></i></button>
                                <button @click="cancelEditing" class="btn-icon btn-cancel" title="Отмена"><i class="bi bi-x-lg"></i></button>
                            </div>
                        </template>
                    </constructor-group>
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
                                       <template v-for="(cond, c_index) in rule.conditions" :key="c_index">
                                            <div class="condition-group">
                                                <constructor-group>
                                                    <div class="constructor-item item-label label-if">ЕСЛИ</div>
                                                    <constructor-item-select :options="[{text: 'Содержит', value: 'contains'}, {text: 'Не содержит', value: 'not_contains'}]" v-model="cond.condition_type"></constructor-item-select>
                                                    <div class="constructor-item item-button-group">
                                                        <button @click="removeCondition(rule, c_index)" class="btn-icon btn-delete" title="Удалить условие" :disabled="rule.conditions.length <= 1"><i class="bi bi-x-lg"></i></button>
                                                    </div>
                                                </constructor-group>
                                                
                                            <constructor-group class="group-auto-height mt-2">
                                                <div class="constructor-item item-pattern-editor">
                                                    <div class="pattern-constructor">
                                                            <draggable :list="cond._blocks" class="pattern-blocks-container" group="blocks" handle=".drag-handle" item-key="id" ghost-class="ghost-block" animation="200">
                                                                <template #item="{ element, index }">
                                                                    <div :class="getBlockClasses(element)">
                                                                        <span class="drag-handle"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16"><path d="M7 2a1 1 0 1 1-2 0 1 1 0 0 1 2 0zm3 0a1 1 0 1 1-2 0 1 1 0 0 1 2 0zM7 5a1 1 0 1 1-2 0 1 1 0 0 1 2 0zm3 0a1 1 0 1 1-2 0 1 1 0 0 1 2 0zM7 8a1 1 0 1 1-2 0 1 1 0 0 1 2 0zm3 0a1 1 0 1 1-2 0 1 1 0 0 1 2 0zm-3 3a1 1 0 1 1-2 0 1 1 0 0 1 2 0zm3 0a1 1 0 1 1-2 0 1 1 0 0 1 2 0z"/></svg></span>
                                                                        <div :contenteditable="isBlockEditable(element)" @blur="isBlockEditable(element) ? updateBlockValue(element, $event.target.innerText) : null" @keydown.enter.prevent class="pattern-block-input">{{ getBlockDisplayText(element) }}</div>
                                                                        <button @click="removePatternBlock(cond._blocks, index)" class="pattern-block-remove" title="Удалить блок">&times;</button>
                                                                    </div>
                                                                </template>
                                                            </draggable>
                                                            <div class="palette-footer">
                                                                <draggable :list="ifBlockPalette" class="pattern-palette" :group="{ name: 'blocks', pull: 'clone', put: false }" :clone="cloneBlock" item-key="type" :sort="false">
                                                                    <template #item="{ element }">
                                                                        <div :class="['palette-btn', 'block-type-' + element.type]" :title="element.title">{{ element.label }}</div>
                                                                    </template>
                                                                </draggable>
                                                            </div>
                                                        </div>
                                                    </div>
                                                    <div class="constructor-item item-button-group">
                                                        <button @click="addCondition(rule, c_index)" class="btn-icon btn-add" title="Добавить условие"><i class="bi bi-plus-lg"></i></button>
                                                    </div>
                                                </constructor-group>
                                            </div>
                                            <div class="logical-operator-container" v-if="c_index < rule.conditions.length - 1">
                                               <select v-model="cond.logical_operator" class="modern-select rule-select-compact"><option value="AND">И</option><option value="OR">ИЛИ</option></select>
                                           </div>
                                       </template>
                                    </div>
                                    <div class="rule-block then-block">
                                        <div v-for="(action, a_index) in rule.actions" :key="a_index" class="condition-group">
                                            <constructor-group>
                                                <div class="constructor-item item-label label-then">ТО</div>
                                                <constructor-item-select :options="[{value: 'exclude', text: 'Исключить видео'}, {value: 'extract_single', text: 'Извлечь номер серии'}, {value: 'extract_range', text: 'Извлечь диапазон серий'}, {value: 'extract_season', text: 'Установить номер сезона'}, {value: 'assign_voiceover', text: 'Назначить озвучку/тег'}, {value: 'assign_episode', text: 'Назначить номер серии'}, {value: 'assign_season', text: 'Назначить номер сезона'}]" v-model="action.action_type" @update:modelValue="onActionTypeChange(action)"></constructor-item-select>
                                                <div class="constructor-item item-button-group">
                                                        <button @click="removeAction(rule, a_index)" class="btn-icon btn-delete" title="Удалить действие" :disabled="rule.actions.length <= 1"><i class="bi bi-x-lg"></i></button>
                                                </div>
                                            </constructor-group>
                                            <div class="action-content mt-2" v-if="action.action_type !== 'exclude'">
                                                <div v-if="['extract_single', 'extract_range', 'extract_season'].includes(action.action_type)">
                                                    <constructor-group class="group-auto-height">
                                                        <div class="constructor-item item-pattern-editor">
                                                            <div class="pattern-constructor">
                                                                <draggable :list="action._action_blocks" class="pattern-blocks-container" group="blocks" handle=".drag-handle" item-key="id" ghost-class="ghost-block" animation="200">
                                                                    <template #item="{ element, index }">
                                                                        <div :class="getBlockClasses(element)">
                                                                            <span class="drag-handle"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16"><path d="M7 2a1 1 0 1 1-2 0 1 1 0 0 1 2 0zm3 0a1 1 0 1 1-2 0 1 1 0 0 1 2 0zM7 5a1 1 0 1 1-2 0 1 1 0 0 1 2 0zm3 0a1 1 0 1 1-2 0 1 1 0 0 1 2 0zM7 8a1 1 0 1 1-2 0 1 1 0 0 1 2 0zm3 0a1 1 0 1 1-2 0 1 1 0 0 1 2 0zm-3 3a1 1 0 1 1-2 0 1 1 0 0 1 2 0zm3 0a1 1 0 1 1-2 0 1 1 0 0 1 2 0z"/></svg></span>
                                                                            <template v-if="['add', 'subtract'].includes(element.type)">
                                                                                <span class="operation-sign">{{ element.type === 'add' ? '+' : '-' }}</span>
                                                                                <div contenteditable="true" @blur="updateBlockValue(element, $event.target.innerText)" @keydown.enter.prevent class="pattern-block-input operation-value">{{ element.value }}</div>
                                                                            </template>
                                                                            <template v-else>
                                                                                <div :contenteditable="isBlockEditable(element)" @blur="isBlockEditable(element) ? updateBlockValue(element, $event.target.innerText) : null" @keydown.enter.prevent class="pattern-block-input">{{ getBlockDisplayText(element, 'then', action._action_blocks) }}</div>
                                                                            </template>
                                                                            <button @click="removePatternBlock(action._action_blocks, index)" class="pattern-block-remove" title="Удалить блок">&times;</button>
                                                                        </div>
                                                                    </template>
                                                                </draggable>
                                                                <div class="palette-footer">
                                                                    <draggable :list="thenBlockPalette" class="pattern-palette" :group="{ name: 'blocks', pull: 'clone', put: false }" :clone="cloneBlock" item-key="type" :sort="false">
                                                                        <template #item="{ element }">
                                                                            <div :class="['palette-btn', 'block-type-' + element.type]" :title="element.title">{{ element.label }}</div>
                                                                        </template>
                                                                    </draggable>
                                                                </div>
                                                            </div>
                                                        </div>
                                                        <div class="constructor-item item-button-group" v-if="a_index === rule.actions.length - 1">
                                                            <button @click="addAction(rule)" class="btn-icon btn-add" title="Добавить действие"><i class="bi bi-plus-lg"></i></button>
                                                        </div>
                                                    </constructor-group>
                                                </div>
                                                <div v-if="['assign_voiceover', 'assign_episode', 'assign_season'].includes(action.action_type)">
                                                     <constructor-group>
                                                        <div class="constructor-item item-floating-label">
                                                            <input :type="action.action_type === 'assign_voiceover' ? 'text' : 'number'" class="item-input" v-model="action.action_pattern" placeholder=" ">
                                                            <label>{{ action.action_type === 'assign_voiceover' ? 'Назначить озвучку/тег' : (action.action_type === 'assign_episode' ? 'Назначить номер серии' : 'Назначить номер сезона') }}</label>
                                                        </div>
                                                        <div class="constructor-item item-button-group" v-if="a_index === rule.actions.length - 1">
                                                            <button @click="addAction(rule)" class="btn-icon btn-add" title="Добавить действие"><i class="bi bi-plus-lg"></i></button>
                                                        </div>
                                                    </constructor-group>
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
                    <div class="modern-fieldset mb-3">
                        <div class="fieldset-content">
                            <div class="mb-3">
                                <label class="modern-label">Режим поиска для теста</label>
                                <div class="btn-group w-100">
                                    <input type="radio" class="btn-check" name="vk_search_mode_test" id="vk_search_test" value="search" v-model="scrapeSearchMode" autocomplete="off">
                                    <label class="btn btn-outline-primary" for="vk_search_test"><i class="bi bi-search me-2"></i>Быстрый поиск</label>
                                    <input type="radio" class="btn-check" name="vk_search_mode_test" id="vk_get_all_test" value="get_all" v-model="scrapeSearchMode" autocomplete="off">
                                    <label class="btn btn-outline-primary" for="vk_get_all_test"><i class="bi bi-card-list me-2"></i>Полное сканирование</label>
                                </div>
                                <small class="form-text text-muted mt-2 d-block">
                                    <b>Быстрый поиск:</b> использует API поиска VK. Быстро, но может пропустить некоторые видео.
                                    <br>
                                    <b>Полное сканирование:</b> загружает список всех видео с канала, затем фильтрует. Медленнее, но надёжнее.
                                </small>
                            </div>
                            <constructor-group>
                                <div class="constructor-item item-label-icon" title="Ссылка на канал VK"><i class="bi bi-youtube"></i></div>
                                <div class="constructor-item item-floating-label">
                                    <input v-model.trim="scrapeChannelUrl" type="text" class="item-input" id="scrape-url" placeholder=" ">
                                    <label for="scrape-url">Ссылка на канал VK</label>
                                </div>
                                <div class="constructor-item item-label-icon" title="Поисковые запросы"><i class="bi bi-search"></i></div>
                                <div class="constructor-item item-floating-label">
                                    <input v-model.trim="scrapeQuery" type="text" class="item-input" id="scrape-query" placeholder=" ">
                                    <label for="scrape-query">Запросы через /</label>
                                </div>
                                <div class="constructor-item item-button-group">
                                    <button @click="scrapeTestTitles" class="btn-icon btn-search btn-text-icon" :disabled="!scrapeChannelUrl || isScraping">
                                        <span v-if="isScraping" class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                                        <i v-else class="bi bi-cloud-download"></i>
                                        <span class="ms-1">Получить с VK</span>
                                    </button>
                                </div>
                            </constructor-group>
                        </div>
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
                            <div class="card-line">
                                <div class="card-title" :title="res.source_data.title">{{ res.source_data.title }}</div>
                                <div v-if="res.source_data.resolution" class="quality-badge">
                                    <span>{{ formatResolution(res.source_data.resolution).text }}</span>
                                </div>
                            </div>
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
        { type: 'add', label: '+', title: 'Сложение' },
        { type: 'subtract', label: '-', title: 'Вычитание' },
        { type: 'whitespace', label: 'Пробел', title: 'Один или несколько пробелов' },
        { type: 'any_text', label: '*', title: 'Любой текст (нежадный поиск)' },
        { type: 'start_of_line', label: 'Начало', title: 'Соответствует началу названия' },
        { type: 'end_of_line', label: 'Конец', title: 'Соответствует концу названия' },
      ],
      scrapeChannelUrl: '',
      scrapeQuery: '',
      isScraping: false,
      scrapedItems: [],
      scrapeSearchMode: 'search',
      // --- ИЗМЕНЕНИЕ: Добавлены состояния для редактирования ---
      editingProfileId: null,
      editingProfileName: '',
    };
  },
  emits: ['show-toast'],
  computed: {
    ifBlockPalette() {
        // Палитра для условий "ЕСЛИ" - без математических операций
        return this.blockPalette.filter(b => !['add', 'subtract'].includes(b.type));
    },
    thenBlockPalette() {
        // Палитра для действий "ТО" - все блоки
        return this.blockPalette;
    },
    scrapedTitlesOnly() {
        return this.scrapedItems.map(item => item.title).join('\n');
    },
    profileOptions() {
        const options = this.profiles.map(p => ({ text: p.name, value: p.id }));
        return [{ text: '-- Выберите профиль --', value: null }, ...options];
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
    // --- ИЗМЕНЕНИЕ: Добавлены новые методы для управления редактированием ---
    startEditingProfile() {
        if (!this.selectedProfileId) return;
        this.editingProfileId = this.selectedProfileId;
        const profile = this.profiles.find(p => p.id === this.editingProfileId);
        this.editingProfileName = profile ? profile.name : '';
        
        this.$nextTick(() => {
            this.$refs.editProfileInput.focus();
        });
    },
    cancelEditing() {
        this.editingProfileId = null;
        this.editingProfileName = '';
    },
    async saveProfileName() {
        if (!this.editingProfileName.trim() || !this.editingProfileId) {
            this.cancelEditing();
            return;
        }
        
        const currentProfile = this.profiles.find(p => p.id === this.editingProfileId);
        if (currentProfile && currentProfile.name === this.editingProfileName.trim()) {
            this.cancelEditing();
            return;
        }

        this.isLoading = true;
        try {
            const response = await fetch(`/api/parser-profiles/${this.editingProfileId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: this.editingProfileName.trim() })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Ошибка переименования');
            
            this.$emit('show-toast', 'Профиль успешно переименован.', 'success');
            const currentId = this.selectedProfileId;
            await this.loadProfiles();
            this.selectedProfileId = currentId;
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        } finally {
            this.isLoading = false;
            this.cancelEditing();
        }
    },
    // ... (остальные методы без изменений)
    formatResolution(resolution) {
        if (!resolution) return { text: 'N/A' };
        if (resolution >= 2160) return { text: `4K ${resolution}` };
        if (resolution >= 1080) return { text: `FHD ${resolution}` };
        if (resolution >= 720) return { text: `HD ${resolution}` };
        if (resolution >= 480) return { text: `SD ${resolution}` };
        return { text: `${resolution}p` };
    },
    emitToast(message, type) { this.$emit('show-toast', message, type); },
    async load() { await this.loadProfiles(); },
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
    cloneBlock(original) {
        const newBlock = { id: Date.now() + Math.random(), type: original.type };
        if (original.type === 'text') {
            newBlock.value = '';
        }
        if (original.type === 'add' || original.type === 'subtract') {
            newBlock.value = '1'; 
        }
        return newBlock;
    },
    removePatternBlock(targetBlocks, blockIndex) { targetBlocks.splice(blockIndex, 1); },
    updateBlockValue(block, newText) {
        if (!block) return;
        let processedText = newText.trim();
        
        // Теперь сюда будет приходить ТОЛЬКО число, парсинг упрощается
        if (block.type === 'add' || block.type === 'subtract') {
            const intValue = parseInt(processedText, 10);
            block.value = isNaN(intValue) ? '0' : String(intValue);
        } else {
            block.value = processedText;
        }
    },
    isBlockEditable(block) {
        return ['text', 'add', 'subtract'].includes(block.type);
    },
    getBlockClasses(block) {
        let classes = ['pattern-block'];
        if (['add', 'subtract'].includes(block.type)) {
            classes.push('block-type-operation');
        } 
        else if (block.type === 'text') { classes.push('block-type-text'); } 
        else { classes.push(`block-type-${block.type}`); }
        return classes.join(' ');
    },
    getBlockDisplayText(element, context = 'if', container = []) {
        // Убираем особую логику для +/-. Теперь для всех редактируемых полей просто возвращаем их значение.
        if (this.isBlockEditable(element)) {
            return element.value;
        }
        
        // Для остальных блоков - как раньше
        if (element.type === 'number' && context === 'then') {
            const numberBlocks = container.filter(b => b.type === 'number');
            const captureIndex = numberBlocks.indexOf(element) + 1;
            return `Число #${captureIndex}`;
        }
        return this.blockPalette.find(p => p.type === element.type)?.label || 'Неизвестный';
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
        // --- ИЗМЕНЕНИЕ: Добавляем отображение значения для блоков операций ---
        if (block.type === 'add') return `+ ${block.value || ''}`;
        if (block.type === 'subtract') return `- ${block.value || ''}`;
        
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
            const videosToTest = this.scrapedItems.length > 0 
                ? this.scrapedItems 
                : this.testTitles.split('\n').filter(t => t.trim() !== '').map(title => ({ title }));

            const response = await fetch('/api/parser-profiles/test', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ profile_id: this.selectedProfileId, videos: videosToTest })
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
    getDisplayableKeys(extractedData) {
        if (!extractedData) return [];
        return Object.keys(extractedData).filter(key => key !== 'end');
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
                body: JSON.stringify({ 
                    channel_url: this.scrapeChannelUrl, 
                    query: this.scrapeQuery,
                    search_mode: this.scrapeSearchMode
                })
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
