// Файл: static/js/components/settingsTrackers.js

const SettingsTrackersTab = {
  name: 'SettingsTrackersTab',
  template: `
    <div class="settings-tab-content">
        <div class="modern-fieldset">
            <div class="fieldset-header">
                <i class="bi bi-broadcast me-2"></i>
                <h6 class="fieldset-title mb-0">Управление трекерами и зеркалами</h6>
            </div>
            <div class="fieldset-content">
                <p class="text-muted small">
                    Здесь вы можете управлять списком зеркал для каждого поддерживаемого трекера. 
                    Система будет автоматически пробовать подключиться к зеркалам по порядку, пока не найдет рабочее.
                </p>
                
                <div v-if="isLoading" class="text-center p-5">
                    <div class="spinner-border" role="status"></div>
                </div>

                <div v-else class="trackers-list">
                    <div v-for="tracker in trackers" :key="tracker.id" class="modern-fieldset mb-3">
                        <div class="fieldset-header">
                            <span class="fieldset-title">{{ tracker.display_name }}</span>
                            <button class="btn btn-primary btn-sm" @click="saveMirrors(tracker)" :disabled="tracker.isSaving">
                                <span v-if="tracker.isSaving" class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                                <i v-else class="bi bi-save me-2"></i>
                                Сохранить
                            </button>
                        </div>
                        <div class="fieldset-content">
                            <div class="mirrors-container">
                                <transition-group name="list" tag="div" class="d-flex flex-wrap gap-2">
                                    <div v-for="(mirror, index) in tracker.mirrors" :key="mirror" class="mirror-pill">
                                        <span>{{ mirror }}</span>
                                        <button @click="removeMirror(tracker, index)" class="mirror-pill-remove" title="Удалить">&times;</button>
                                    </div>
                                </transition-group>
                            </div>
                            <constructor-group class="mt-3">
                                <div class="constructor-item item-floating-label">
                                    <input 
                                        v-model.trim="tracker.newMirror" 
                                        @keyup.enter="addMirror(tracker)"
                                        type="text" class="item-input" 
                                        :id="'new-mirror-' + tracker.id" 
                                        placeholder=" ">
                                    <label :for="'new-mirror-' + tracker.id">Новое зеркало (домен)...</label>
                                </div>
                                <div class="constructor-item item-button-group">
                                    <button @click="addMirror(tracker)" class="btn-icon btn-add" title="Добавить"><i class="bi bi-plus-lg"></i></button>
                                </div>
                            </constructor-group>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
  `,
  data() {
    return {
      isLoading: false,
      trackers: [],
    };
  },
  emits: ['show-toast'],
  methods: {
    async load() {
        this.isLoading = true;
        try {
            const response = await fetch('/api/trackers');
            if (!response.ok) throw new Error('Ошибка загрузки списка трекеров');
            this.trackers = (await response.json()).map(tracker => ({
                ...tracker,
                newMirror: '',    // Поле для ввода нового зеркала
                isSaving: false, // Флаг сохранения для каждой карточки
            }));
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        } finally {
            this.isLoading = false;
        }
    },
    addMirror(tracker) {
        if (!tracker.newMirror || tracker.mirrors.includes(tracker.newMirror)) {
            tracker.newMirror = '';
            return;
        }
        // Убираем http/https и прочие лишние символы, оставляем только домен
        try {
            const hostname = new URL('https://' + tracker.newMirror.replace(/^(https?:\/\/)?/, '')).hostname;
            tracker.mirrors.push(hostname);
            tracker.newMirror = '';
        } catch(e) {
            this.$emit('show-toast', 'Некорректный формат домена.', 'danger');
        }
    },
    removeMirror(tracker, index) {
        tracker.mirrors.splice(index, 1);
    },
    async saveMirrors(tracker) {
        tracker.isSaving = true;
        try {
            const response = await fetch(`/api/trackers/${tracker.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mirrors: tracker.mirrors })
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Ошибка сохранения');
            
            this.$emit('show-toast', `Зеркала для "${tracker.display_name}" успешно сохранены.`, 'success');
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
            this.load(); // В случае ошибки перезагружаем данные, чтобы отменить изменения
        } finally {
            tracker.isSaving = false;
        }
    }
  },
};