const StatusTabNaming = {
  template: `
    <div>
        <div v-if="isLoading" class="text-center p-5"><div class="spinner-border" role="status"></div></div>
        <div v-else-if="!qbTorrents.length" class="text-center text-muted mt-3">Нет торрентов в qBittorrent для переименования.</div>
        <div v-else>
            <div v-for="torrent in qbTorrents" :key="torrent.qb_hash" class="div-table table-naming-preview mb-3 position-relative">
                <transition name="fade"><div v-if="renamingPreviews[torrent.qb_hash] && renamingPreviews[torrent.qb_hash].loading" class="loading-overlay"></div></transition>
                <div class="div-table-row" style="background-color: #e9ecef; font-weight: bold;"><div class="div-table-cell" style="grid-column: 1 / -1;">Торрент ID: {{ torrent.torrent_id }}</div></div>
                <div class="div-table-header"><div class="div-table-cell">Файл на данный момент</div><div class="div-table-cell">Файл после переименования</div></div>
                <div class="div-table-body">
                    <template v-if="renamingPreviews[torrent.qb_hash] && !renamingPreviews[torrent.qb_hash].loading">
                        <div v-for="file in renamingPreviews[torrent.qb_hash].files" :key="file.original" class="div-table-row">
                            <div class="div-table-cell">{{ file.original }}</div><div class="div-table-cell">{{ file.renamed }}</div>
                        </div>
                    </template>
                </div>
            </div>
             <div class="d-flex justify-content-end mt-4">
                <button class="btn btn-success" @click="executeRename" :disabled="isRenaming || qbTorrents.length === 0">
                    <span v-if="isRenaming" class="spinner-border spinner-border-sm me-2"></span>
                    <i v-else class="bi bi-pencil-square me-2"></i>
                    Переименовать все
                </button>
            </div>
        </div>
    </div>
  `,
  props: {
    seriesId: { type: Number, required: true },
    isActive: { type: Boolean, default: false },
  },
  emits: ['show-toast'],
  data() {
    return {
      isLoading: false,
      isRenaming: false,
      qbTorrents: [],
      renamingPreviews: {},
    };
  },
  watch: {
    isActive(newVal) {
      if (newVal) this.load();
    }
  },
  methods: {
    async load() {
        this.isLoading = true;
        try {
            const response = await fetch(`/api/series/${this.seriesId}/qb_info`);
            const data = await response.json();
            if (response.ok) { 
                this.qbTorrents = data;
                if (this.qbTorrents.length > 0) this.loadRenamingPreview();
            } else { throw new Error(data.error || 'Ошибка загрузки торрентов'); }
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); }
        finally { this.isLoading = false; }
    },
    async loadRenamingPreview() {
        for (const torrent of this.qbTorrents) {
            this.renamingPreviews[torrent.qb_hash] = { loading: true, files: [] };
            try {
                const response = await fetch('/api/rename/preview', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ files: torrent.file_paths, series_id: this.seriesId })
                });
                const previewData = await response.json();
                if (!response.ok) throw new Error(previewData.error || 'Ошибка предпросмотра');
                this.renamingPreviews[torrent.qb_hash].files = previewData;
            } catch (error) { this.$emit('show-toast', error.message, 'danger');
            } finally { 
                if (this.renamingPreviews[torrent.qb_hash]) {
                    this.renamingPreviews[torrent.qb_hash].loading = false; 
                }
            }
        }
    },
    async executeRename() {
        this.isRenaming = true; let totalErrors = 0;
        for (const torrent of this.qbTorrents) {
            try {
                const response = await fetch(`/api/series/${this.seriesId}/torrents/${torrent.qb_hash}/rename`, { method: 'POST' });
                const data = await response.json();
                if (!response.ok || !data.success) throw new Error(data.error || `Ошибка торрента ${torrent.torrent_id}`);
            } catch (error) { totalErrors++; this.$emit('show-toast', error.message, 'danger'); }
        }
        if (totalErrors > 0) this.$emit('show-toast', `Переименование завершено с ${totalErrors} ошибками.`, 'warning');
        else this.$emit('show-toast', 'Все файлы успешно переименованы!', 'success');
        this.isRenaming = false;
        await this.load();
    },
  },
  mounted() {
    if (this.isActive) {
        this.load();
    }
  }
};