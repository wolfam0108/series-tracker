const SettingsParserTab = {
  name: 'SettingsParserTab',
  components: {
    'parser-rule-editor': ParserRuleEditor,
  },
  template: `
    <div class="settings-tab-content">
        <div class="modern-fieldset mb-4">
            <div class="fieldset-header">
                <h6 class="fieldset-title mb-0">Управление профилями парсера</h6>
            </div>
            <div class="fieldset-content">
                <p class="text-muted small">Профили позволяют создавать наборы правил для разных типов контента или каналов. Выберите профиль для редактирования или создайте новый.</p>
                <div class="modern-input-group mb-3">
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

        <parser-rule-editor
            v-if="selectedProfileId"
            :key="selectedProfileId"
            :profile-id="selectedProfileId"
            :profile-name="selectedProfileName"
            @show-toast="emitToast"
            @reload-rules="handleRulesUpdate"
        ></parser-rule-editor>

    </div>
  `,
  data() {
    return {
      profiles: [],
      selectedProfileId: null,
      newProfileName: '',
      isLoading: false,
    };
  },
  emits: ['show-toast'],
  computed: {
    selectedProfileName() {
        const profile = this.profiles.find(p => p.id === this.selectedProfileId);
        return profile ? profile.name : '';
    },
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
            if (this.profiles.length > 0 && !this.selectedProfileId) {
                this.selectedProfileId = this.profiles[0].id;
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
    handleRulesUpdate() {
        // В дочернем компоненте теперь есть своя логика загрузки,
        // но родитель может принудительно перезагрузить профили, если потребуется
        this.loadProfiles();
    }
  }
};