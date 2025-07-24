const StatusTabQbit = {
  components: { 'file-tree': FileTree },
template: `
    <div>
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h6>Торренты из qBittorrent</h6>
            <button v-if="qbTorrents.length > 0 && !isLoading" class="btn btn-danger btn-sm" @click="deleteAllTorrents"><i class="bi bi-trash me-2"></i>Удалить все из qBit</button>
        </div>
        <div class="position-relative">
            <div v-if="isLoading" class="div-table table-qbit-info animate-pulse">
                <div class="div-table-header">
                    <div class="div-table-cell" v-for="i in 4" :key="i">&nbsp;</div>
                </div>
                <div class="div-table-body">
                    <div v-for="i in 2" :key="i" class="div-table-row">
                        <div class="div-table-cell"><div class="skeleton-line short"></div></div>
                        <div class="div-table-cell"><div class="skeleton-line"></div></div>
                        <div class="div-table-cell"><div class="skeleton-line short"></div></div>
                        <div class="div-table-cell"><div class="skeleton-line long"></div></div>
                    </div>
                </div>
            </div>

            <div v-else class="div-table table-qbit-info">
                <div class="div-table-header"><div class="div-table-cell">ID</div><div class="div-table-cell">Статус</div><div class="div-table-cell">Устарел?</div><div class="div-table-cell">Список файлов</div></div>
                <div class="div-table-body">
                    <transition-group name="list" tag="div">
                        <div v-for="t in qbTorrents" :key="t.torrent_id" class="div-table-row">
                            <div class="div-table-cell">{{ t.torrent_id }}</div><div class="div-table-cell">{{ translateStatus(t.state) }}</div><div class="div-table-cell">{{ t.is_obsolete ? 'Да' : 'Нет' }}</div><div class="div-table-cell"><file-tree :files="t.file_paths || []"></file-tree></div>
                        </div>
                    </transition-group>
                </div>
            </div>
        </div>
        <p v-if="!isLoading && qbTorrents.length === 0" class="mt-3 text-center text-muted">Торренты в qBittorrent не найдены.</p>
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
      qbTorrents: [],
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
            if (response.ok) { this.qbTorrents = data; } 
            else { throw new Error(data.error || 'Ошибка загрузки из qBittorrent'); }
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); } 
        finally { this.isLoading = false; }
    },
    async deleteAllTorrents() {
        if (!confirm('Вы уверены, что хотите удалить ВСЕ торренты для этого сериала из qBittorrent?')) return;
        try {
            const response = await fetch(`/api/series/${this.seriesId}/torrents`, { method: 'DELETE' });
            const data = await response.json();
            if (data.success) { this.$emit('show-toast', `Удалено ${data.deleted_count || 0} торрентов.`, 'success'); this.load(); } 
            else { throw new Error(data.error || 'Ошибка при удалении'); }
        } catch (error) { this.$emit('show-toast', `Сетевая ошибка: ${error.message}`, 'danger'); }
    },
    translateStatus(state) {
        const statuses = { 'uploading': 'Раздача', 'forcedUP': 'Раздача', 'downloading': 'Загрузка', 'forcedDL': 'Загрузка', 'metaDL': 'Загрузка', 'stalledUP': 'Ожидание', 'stalledDL': 'Ожидание', 'checkingUP': 'Проверка', 'checkingDL': 'Проверка', 'checkingResumeData': 'Проверка', 'pausedUP': 'Пауза', 'pausedDL': 'Пауза', 'queuedUP': 'В очереди', 'queuedDL': 'В очереди', 'allocating': 'Выделение места', 'moving': 'Перемещение', 'error': 'Ошибка', 'missingFiles': 'Нет файлов' };
        return statuses[state] || 'Неизвестно';
    }
  },
  mounted() {
    if (this.isActive) {
        this.load();
    }
  }
};