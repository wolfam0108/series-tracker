const SettingsAuthTab = {
  template: `
    <div class="settings-tab-content">
      <form @submit.prevent="saveAuthSettings">
        <div class="modern-fieldset">
            <div class="fieldset-header">
                <i class="bi bi-download me-2"></i>
                <span class="fieldset-title">qBittorrent</span>
            </div>
            <div class="fieldset-content">
                <div class="modern-form-group">
                    <label for="qbUrl" class="modern-label">URL-адрес</label>
                    <div class="modern-input-group">
                        <span class="input-group-text"><i class="bi bi-link-45deg"></i></span>
                        <input v-model.trim="credentials.qbittorrent.url" 
                               type="text" 
                               class="modern-input" 
                               id="qbUrl" 
                               placeholder="https://qb.example.com"
                               autocomplete="off">
                    </div>
                </div>
                <div class="modern-form-group">
                    <label for="qbUsername" class="modern-label">Учетные данные</label>
                    <div class="modern-input-group">
                        <span class="input-group-text"><i class="bi bi-person"></i></span>
                        <input v-model.trim="credentials.qbittorrent.username" 
                               type="text" 
                               class="modern-input" 
                               id="qbUsername" 
                               placeholder="Логин"
                               autocomplete="username">
                        <div class="modern-input-group-divider"></div>
                        <span class="input-group-text"><i class="bi bi-shield-lock"></i></span>
                        <input v-model="credentials.qbittorrent.password" 
                               :type="qbPasswordVisible ? 'text' : 'password'" 
                               class="modern-input" 
                               id="qbPassword" 
                               placeholder="Пароль"
                               autocomplete="current-password">
                        <button class="btn bg-transparent border-0 text-secondary" 
                                style="margin-left: -40px; z-index: 100;"
                                type="button" 
                                @click="togglePasswordVisibility('qb')"
                                :title="qbPasswordVisible ? 'Скрыть пароль' : 'Показать пароль'">
                            <i class="bi" :class="qbPasswordVisible ? 'bi-eye-slash' : 'bi-eye'"></i>
                        </button>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="modern-fieldset">
            <div class="fieldset-header">
                <i class="bi bi-globe me-2"></i>
                <span class="fieldset-title">Kinozal.me</span>
            </div>
            <div class="fieldset-content">
                <div class="modern-form-group">
                    <label for="kinozalUsername" class="modern-label">Учетные данные</label>
                     <div class="modern-input-group">
                        <span class="input-group-text"><i class="bi bi-person"></i></span>
                        <input v-model.trim="credentials.kinozal.username" 
                               type="text" 
                               class="modern-input" 
                               id="kinozalUsername" 
                               placeholder="Логин"
                               autocomplete="username">
                        <div class="modern-input-group-divider"></div>
                        <span class="input-group-text"><i class="bi bi-shield-lock"></i></span>
                        <input v-model="credentials.kinozal.password" 
                               :type="kinozalPasswordVisible ? 'text' : 'password'" 
                               class="modern-input" 
                               id="kinozalPassword" 
                               placeholder="Пароль"
                               autocomplete="current-password">
                        <button class="btn bg-transparent border-0 text-secondary" 
                                style="margin-left: -40px; z-index: 100;"
                                type="button" 
                                @click="togglePasswordVisibility('kinozal')"
                                :title="kinozalPasswordVisible ? 'Скрыть пароль' : 'Показать пароль'">
                            <i class="bi" :class="kinozalPasswordVisible ? 'bi-eye-slash' : 'bi-eye'"></i>
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <div class="modern-fieldset">
            <div class="fieldset-header">
                <i class="bi bi-youtube me-2"></i> <span class="fieldset-title">VK Video</span>
            </div>
            <div class="fieldset-content">
                <div class="modern-form-group">
                    <label for="vkToken" class="modern-label">Access Token</label>
                     <div class="modern-input-group">
                        <span class="input-group-text"><i class="bi bi-key"></i></span>
                        <input v-model="credentials.vk.token" 
                               :type="vkTokenVisible ? 'text' : 'password'" 
                               class="modern-input" 
                               id="vkToken" 
                               placeholder="vk1.a.******************"
                               autocomplete="off">
                        <button class="btn bg-transparent border-0 text-secondary" 
                                style="margin-left: -40px; z-index: 100;"
                                type="button" 
                                @click="togglePasswordVisibility('vk')"
                                :title="vkTokenVisible ? 'Скрыть токен' : 'Показать токен'">
                            <i class="bi" :class="vkTokenVisible ? 'bi-eye-slash' : 'bi-eye'"></i>
                        </button>
                    </div>
                    <small class="form-text text-muted">Необходим для поиска видео через официальный API VK. Получить токен можно <a href="https://dev.vk.com/ru/api/access-token/getting-started" target="_blank">здесь</a>.</small>
                </div>
            </div>
        </div>

      </form>
    </div>
  `,
  data() {
    return {
      isSaving: false,
      credentials: { 
        qbittorrent: { url: '', username: '', password: '' }, 
        kinozal: { username: '', password: '' },
        vk: { token: '' } // Добавлено
      },
      qbPasswordVisible: false, 
      kinozalPasswordVisible: false,
      vkTokenVisible: false, // Добавлено
    };
  },
  emits: ['show-toast', 'saving-state'],
  methods: {
    togglePasswordVisibility(type) {
        if (type === 'qb') this.qbPasswordVisible = !this.qbPasswordVisible;
        else if (type === 'kinozal') this.kinozalPasswordVisible = !this.kinozalPasswordVisible;
        else if (type === 'vk') this.vkTokenVisible = !this.vkTokenVisible; // Добавлено
    },
    async load() {
      try {
        const response = await fetch('/api/auth');
        if (!response.ok) throw new Error('Ошибка загрузки настроек авторизации');
        const data = await response.json();
        if (data.qbittorrent) this.credentials.qbittorrent = { ...this.credentials.qbittorrent, ...data.qbittorrent };
        if (data.kinozal) this.credentials.kinozal = { ...this.credentials.kinozal, ...data.kinozal };
        if (data.vk) this.credentials.vk.token = data.vk.password || ''; // API отдает токен в поле password
      } catch (error) { 
        this.$emit('show-toast', error.message, 'danger'); 
      }
    },
    async save() {
      this.isSaving = true;
      this.$emit('saving-state', true);
      try {
        const response = await fetch('/api/auth', { 
          method: 'POST', 
          headers: { 'Content-Type': 'application/json' }, 
          body: JSON.stringify(this.credentials) 
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || 'Ошибка сохранения настроек');
        this.$emit('show-toast', 'Настройки авторизации сохранены.', 'success');
      } catch (error) { 
        this.$emit('show-toast', error.message, 'danger');
      } finally { 
        this.isSaving = false;
        this.$emit('saving-state', false);
      }
    },
  }
};