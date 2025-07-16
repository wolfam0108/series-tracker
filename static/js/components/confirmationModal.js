const ConfirmationModal = {
  template: `
    <div class="modal fade" ref="confirmationModal" tabindex="-1" aria-labelledby="confirmationModalLabel" aria-hidden="true">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content modern-modal">
          <div class="modal-header modern-header">
            <h5 class="modal-title" id="confirmationModalLabel">
              <i class="bi bi-exclamation-triangle-fill me-2 text-warning"></i>
              {{ title }}
            </h5>
            <button type="button" class="btn-close modern-close" @click="cancel" aria-label="Close"></button>
          </div>
          <div class="modal-body modern-body">
            <p v-html="message"></p>
            <div v-if="checkbox.visible" class="modern-form-check form-switch mt-3">
              <input class="form-check-input" type="checkbox" role="switch" id="confirmationCheckbox" v-model="checkbox.checked">
              <label class="modern-form-check-label" for="confirmationCheckbox">{{ checkbox.text }}</label>
            </div>
            </div>
          <div class="modal-footer modern-footer">
            <button type="button" class="btn btn-secondary" @click="cancel">
              <i class="bi bi-x-lg me-2"></i>Отмена
            </button>
            <button type="button" class="btn btn-danger" @click="confirm">
              <i class="bi bi-check-lg me-2"></i>Подтвердить
            </button>
          </div>
        </div>
      </div>
    </div>
  `,
  data() {
    return {
      modal: null,
      title: 'Подтверждение',
      message: 'Вы уверены?',
      checkbox: {
        visible: false,
        text: '',
        checked: false,
      },
      resolvePromise: null,
      rejectPromise: null,
    };
  },
  methods: {
    open(title, message, checkboxConfig = null) {
      this.title = title || 'Подтверждение';
      this.message = message || 'Вы уверены?';
      
      if (checkboxConfig) {
        this.checkbox.visible = true;
        this.checkbox.text = checkboxConfig.text || '';
        this.checkbox.checked = checkboxConfig.checked || false;
      } else {
        this.checkbox.visible = false;
      }
      
      if (!this.modal) {
        this.modal = new bootstrap.Modal(this.$refs.confirmationModal);
      }
      this.modal.show();
      return new Promise((resolve, reject) => {
        this.resolvePromise = resolve;
        this.rejectPromise = reject;
      });
    },
    confirm() {
      if (this.resolvePromise) {
        this.resolvePromise({ confirmed: true, checkboxState: this.checkbox.checked });
      }
      this.close();
    },
    cancel() {
      if (this.rejectPromise) {
        this.rejectPromise(false);
      }
      this.close();
    },
    close() {
      this.modal.hide();
      this.resolvePromise = null;
      this.rejectPromise = null;
    }
  }
};