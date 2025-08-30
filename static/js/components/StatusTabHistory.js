const StatusTabHistory = {
template: `
    <div>
        <div v-if="isLoading">
            <div v-if="sourceType === 'vk_video'" class="div-table table-media-item-history animate-pulse">
                <div class="div-table-header"><div class="div-table-cell" v-for="i in 7" :key="i">&nbsp;</div></div>
                <div class="div-table-body">
                    <div v-for="i in 5" :key="i" class="div-table-row">
                        <div class="div-table-cell" v-for="j in 7" :key="j"><div class="skeleton-line"></div></div>
                    </div>
                </div>
            </div>
            <div v-else class="div-table table-torrents-history animate-pulse">
                <div class="div-table-header"><div class="div-table-cell" v-for="i in 7" :key="i">&nbsp;</div></div>
                <div class="div-table-body">
                    <div v-for="i in 5" :key="i" class="div-table-row">
                        <div class="div-table-cell" v-for="j in 7" :key="j"><div class="skeleton-line"></div></div>
                    </div>
                </div>
            </div>
        </div>

        <div v-else-if="sourceType === 'vk_video'">
            <h6>История медиа-элементов в БД</h6>
            <div class="table-wrapper-scroll-x">
                <div class="div-table table-media-item-history">
                    <div class="div-table-header"><div class="div-table-cell">Unique ID</div><div class="div-table-cell">URL</div><div class="div-table-cell">Эпизоды</div><div class="div-table-cell">Статус</div><div class="div-table-cell">Файл</div><div class="div-table-cell">Главы</div><div class="div-table-cell">Дата</div></div>
                    <div class="div-table-body">
                        <div v-for="item in mediaItemHistory" :key="item.id" class="div-table-row">
                            <div class="div-table-cell">{{ item.unique_id }}</div><div class="div-table-cell"><a :href="item.source_url" target="_blank">{{ item.source_url }}</a></div>
                            <div class="div-table-cell">{{ formatEpisodeInfo(item) }}</div><div class="div-table-cell">{{ item.status }}</div>
                            <div class="div-table-cell">{{ item.final_filename }}</div><div class="div-table-cell">{{ formatChapterStatus(item) }}</div>
                            <div class="div-table-cell">{{ formatDate(item.publication_date) }}</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div v-else>
            <h6>История торрентов в БД</h6>
            <div class="div-table table-torrents-history">
                <div class="div-table-header"><div class="div-table-cell">ID</div><div class="div-table-cell">Ссылка</div><div class="div-table-cell">Дата</div><div class="div-table-cell">Эпизоды</div><div class="div-table-cell">Качество</div><div class="div-table-cell">Активен?</div><div class="div-table-cell">Хеш qBit</div></div>
                <div class="div-table-body">
                    <div v-for="t in torrentHistory" :key="t.id" class="div-table-row">
                        <div class="div-table-cell">{{ t.torrent_id }}</div><div class="div-table-cell">{{ t.link }}</div><div class="div-table-cell">{{ t.date_time }}</div>
                        <div class="div-table-cell">{{ t.episodes }}</div><div class="div-table-cell">{{ t.quality }}</div><div class="div-table-cell">{{ t.is_active ? 'Да' : 'Нет' }}</div>
                        <div class="div-table-cell">{{ t.qb_hash || 'N/A' }}</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
  `,
  props: {
    seriesId: { type: Number, required: true },
    sourceType: { type: String, required: true },
    isActive: { type: Boolean, default: false },
  },
  emits: ['show-toast'],
  data() {
    return {
      isLoading: false,
      torrentHistory: [],
      mediaItemHistory: [],
    };
  },
  watch: {
    isActive(newVal) {
      if (newVal) this.load();
    }
  },
  methods: {
    load() {
        if (this.sourceType === 'vk_video') this.loadMediaItemHistory();
        else this.loadTorrentHistory();
    },
    async loadTorrentHistory() {
        this.isLoading = true;
        try {
            const response = await fetch(`/api/series/${this.seriesId}/torrents/history`);
            if (!response.ok) throw new Error('Ошибка загрузки истории торрентов');
            this.torrentHistory = await response.json();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); } 
        finally { this.isLoading = false; }
    },
    async loadMediaItemHistory() {
        this.isLoading = true;
        try {
            const response = await fetch(`/api/series/${this.seriesId}/media-items`);
            if (!response.ok) throw new Error('Ошибка загрузки истории медиа-элементов');
            this.mediaItemHistory = await response.json();
        } catch (error) { this.$emit('show-toast', error.message, 'danger'); } 
        finally { this.isLoading = false; }
    },
    formatEpisodeInfo(item) {
        let seasonPart = `s${String(item.season || 1).padStart(2, '0')}`;
        let episodePart = item.episode_end ? `e${String(item.episode_start).padStart(2, '0')}-e${String(item.episode_end).padStart(2, '0')}` : `e${String(item.episode_start).padStart(2, '0')}`;
        return `${seasonPart}${episodePart}`;
    },
    formatChapterStatus(item) {
        if (!item.chapters) return 'Нет';
        try {
            const chapters = JSON.parse(item.chapters);
            return chapters.length > 0 ? `Да (${chapters.length})` : 'Ошибка';
        } catch(e) { return 'Ошибка'; }
    },
    formatDate(isoString) {
        if (!isoString) return '-';
        const date = new Date(isoString);
        return date.toLocaleString('ru-RU', { 
            day: '2-digit', 
            month: '2-digit', 
            year: 'numeric', 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    },
  },
  mounted() {
    if (this.isActive) {
        this.load();
    }
  }
};