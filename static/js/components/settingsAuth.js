// static/js/components/settingsAuth.js
const SettingsAuthTab = {
template: `
    <div class="settings-tab-content">
        <div class="modern-fieldset">
            <div class="fieldset-header">
                <i class="bi bi-download me-2"></i>
                <span class="fieldset-title">qBittorrent</span>
            </div>
            <div class="fieldset-content">
                <div class="field-group">
                    <constructor-group>
                        <div class="constructor-item item-label-icon" title="URL"><i class="bi bi-link-45deg"></i></div>
                        <div class="constructor-item item-floating-label">
                            <input type="text" class="item-input" id="qb-url-input" placeholder=" " v-model.trim="credentials.qbittorrent.url">
                            <label for="qb-url-input">URL-адрес</label>
                        </div>
                    </constructor-group>
                </div>
                <div class="field-group">
                    <constructor-group>
                        <div class="constructor-item item-label-icon" title="Логин"><i class="bi bi-person"></i></div>
                        <div class="constructor-item item-floating-label">
                            <input type="text" class="item-input" id="qb-login-input" placeholder=" " v-model.trim="credentials.qbittorrent.username">
                            <label for="qb-login-input">Логин</label>
                        </div>
                        <div class="constructor-item item-label-icon" title="Пароль"><i class="bi bi-shield-lock"></i></div>
                        <div class="constructor-item item-floating-label">
                            <div class="item-input-wrapper">
                                <input :type="qbPasswordVisible ? 'text' : 'password'" class="item-input" id="qb-password-input" placeholder=" " v-model="credentials.qbittorrent.password">
                                <label for="qb-password-input">Пароль</label>
                                <button class="password-toggle-btn" @click="togglePasswordVisibility('qb')" :title="qbPasswordVisible ? 'Скрыть' : 'Показать'">
                                    <i class="bi" :class="qbPasswordVisible ? 'bi-eye-slash' : 'bi-eye'"></i>
                                </button>
                            </div>
                            </div>
                    </constructor-group>
                </div>
            </div>
        </div>
        
        <div class="modern-fieldset">
            <div class="fieldset-header">
                <i class="bi bi-globe me-2"></i>
                <span class="fieldset-title">Kinozal.me</span>
            </div>
            <div class="fieldset-content">
                <div class="field-group">
                     <constructor-group>
                        <div class="constructor-item item-label-icon" title="Логин"><i class="bi bi-person"></i></div>
                        <div class="constructor-item item-floating-label">
                            <input type="text" class="item-input" id="kz-login-input" placeholder=" " v-model.trim="credentials.kinozal.username">
                            <label for="kz-login-input">Логин</label>
                        </div>
                        <div class="constructor-item item-label-icon" title="Пароль"><i class="bi bi-shield-lock"></i></div>
                        <div class="constructor-item item-floating-label">
                            <div class="item-input-wrapper">
                                <input :type="kinozalPasswordVisible ? 'text' : 'password'" class="item-input" id="kz-password-input" placeholder=" " v-model="credentials.kinozal.password">
                                <label for="kz-password-input">Пароль</label>
                                <button class="password-toggle-btn" @click="togglePasswordVisibility('kinozal')" :title="kinozalPasswordVisible ? 'Скрыть' : 'Показать'">
                                    <i class="bi" :class="kinozalPasswordVisible ? 'bi-eye-slash' : 'bi-eye'"></i>
                                </button>
                            </div>
                            </div>
                    </constructor-group>
                </div>
            </div>
        </div>

        <div class="modern-fieldset">
            <div class="fieldset-header">
                <i class="bi bi-youtube me-2"></i> <span class="fieldset-title">VK Video</span>
            </div>
            <div class="fieldset-content">
                <div class="field-group">
                    <constructor-group>
                        <div class="constructor-item item-label-icon" title="Токен"><i class="bi bi-key"></i></div>
                        <div class="constructor-item item-floating-label">
                            <div class="item-input-wrapper">
                                <input :type="vkTokenVisible ? 'text' : 'password'" class="item-input" id="vk-token-input" placeholder=" " v-model="credentials.vk.token">
                                <label for="vk-token-input">Access Token</label>
                                <button class="password-toggle-btn" @click="togglePasswordVisibility('vk')" :title="vkTokenVisible ? 'Скрыть' : 'Показать'">
                                    <i class="bi" :class="vkTokenVisible ? 'bi-eye-slash' : 'bi-eye'"></i>
                                </button>
                            </div>
                            </div>
                    </constructor-group>
                    <small class="form-text text-muted mt-2 d-block">
                        Необходим для поиска видео через официальный API VK.
                    </small>
                </div>
            </div>
        </div>
        
        <div class="modern-fieldset">
            <div class="fieldset-header">
                <i class="bi bi-download me-2"></i>
                <span class="fieldset-title">RuTracker.org</span>
            </div>
            <div class="fieldset-content">
                <div class="field-group">
                     <constructor-group>
                        <div class="constructor-item item-label-icon" title="Логин"><i class="bi bi-person"></i></div>
                        <div class="constructor-item item-floating-label">
                            <input type="text" class="item-input" id="rt-login-input" placeholder=" " v-model.trim="credentials.rutracker.username">
                            <label for="rt-login-input">Логин</label>
                        </div>
                        <div class="constructor-item item-label-icon" title="Пароль"><i class="bi bi-shield-lock"></i></div>
                        <div class="constructor-item item-floating-label">
                            <div class="item-input-wrapper">
                                <input :type="rutrackerPasswordVisible ? 'text' : 'password'" class="item-input" id="rt-password-input" placeholder=" " v-model="credentials.rutracker.password">
                                <label for="rt-password-input">Пароль</label>
                                <button class="password-toggle-btn" @click="togglePasswordVisibility('rutracker')" :title="rutrackerPasswordVisible ? 'Скрыть' : 'Показать'">
                                    <i class="bi" :class="rutrackerPasswordVisible ? 'bi-eye-slash' : 'bi-eye'"></i>
                                </button>
                            </div>
                            </div>
                    </constructor-group>
                </div>
            </div>
        </div>
    </div>
  `,
  data() {
    return {
      isSaving: false,
      credentials: {
        qbittorrent: { url: '', username: '', password: '' },
        kinozal: { username: '', password: '' },
        vk: { token: '' },
        rutracker: { username: '', password: '' }
      },
      qbPasswordVisible: false,
      kinozalPasswordVisible: false,
      vkTokenVisible: false,
      rutrackerPasswordVisible: false,
    };
  },
  emits: ['show-toast', 'saving-state'],
  methods: {
    togglePasswordVisibility(type) {
        if (type === 'qb') this.qbPasswordVisible = !this.qbPasswordVisible;
        else if (type === 'kinozal') this.kinozalPasswordVisible = !this.kinozalPasswordVisible;
        else if (type === 'vk') this.vkTokenVisible = !this.vkTokenVisible;
        else if (type === 'rutracker') this.rutrackerPasswordVisible = !this.rutrackerPasswordVisible;
    },
    async load() {
      try {
        const response = await fetch('/api/auth');
        if (!response.ok) throw new Error('Ошибка загрузки настроек авторизации');
        const data = await response.json();
        if (data.qbittorrent) this.credentials.qbittorrent = { ...this.credentials.qbittorrent, ...data.qbittorrent };
        if (data.kinozal) this.credentials.kinozal = { ...this.credentials.kinozal, ...data.kinozal };
        if (data.vk) this.credentials.vk.token = data.vk.password || '';
        if (data.rutracker) this.credentials.rutracker = { ...this.credentials.rutracker, ...data.rutracker };
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