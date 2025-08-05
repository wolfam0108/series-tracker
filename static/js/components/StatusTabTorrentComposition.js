const StatusTabTorrentComposition = {
  name: 'StatusTabTorrentComposition',
  props: {
    seriesId: { type: Number, required: true },
    isActive: { type: Boolean, default: false },
  },
  emits: ['show-toast'],
  template: `
<div class="composition-manager">
    <div class="modern-fieldset mb-4">
        <div class="fieldset-header">
            <h6 class="fieldset-title mb-0">Управление файлами</h6>
            <button class="btn btn-primary" @click="reprocessAllFiles" :disabled="isLoading || isReprocessing || !torrentFiles.length">
                <span v-if="isReprocessing" class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                <i v-else class="bi bi-arrow-clockwise me-2"></i>
                {{ isReprocessing ? 'Обработка...' : 'Переприменить правила' }}
            </button>
        </div>
    </div>

    <div v-if="isLoading" class="text-center p-5">
        <div class="spinner-border" role="status"></div>
    </div>
    <div v-else-if="!torrentFiles.length" class="empty-state">
        Нет обработанных файлов для отображения. 
        <br>
        Если вы только что добавили сериал, запустите сканирование.
    </div>
    <div v-else class="season-groups-container">
        <div v-for="seasonNumber in sortedSeasons" :key="seasonNumber" class="season-group">
            <h5 class="season-header">
                <span>{{ getSeasonTitle(seasonNumber) }}</span>
            </h5>
            <div class="composition-cards-container">
                <div v-for="file in groupedFiles[seasonNumber]" :key="file.id" 
                    class="card-final card-torrent"
                    :class="getCardColorClass(file)">
                    
                    <div class="info-column">
                        <div class="card-title-block">
                            <span class="card-title" :title="series.name + ' ' + formatSXXEXX(file.extracted_metadata)">{{ series.name }} {{ formatSXXEXX(file.extracted_metadata) }}</span>
                            <div v-if="file.extracted_metadata && file.extracted_metadata.resolution" class="quality-badge">
                                <span>{{ file.extracted_metadata.resolution }}</span>
                            </div>
                        </div>

                        <div class="path-line">
                            <span class="path-pill">
                                <span class="path-pill-label">Полученное:</span>
                                <span class="path-pill-value" :title="file.original_path">{{ getBaseName(file.original_path) }}</span>
                            </span>
                        </div>

                        <div class="path-line">
                            <span class="path-pill" :class="{ 'is-missing': !file.is_file_present }">
                                <span class="path-pill-label">Фактическое:</span>
                                <span class="path-pill-value" v-if="file.is_file_present" :title="file.renamed_path_preview">{{ getBaseName(file.renamed_path_preview) }}</span>
                                <span class="path-pill-value" v-else><i class="bi bi-x-circle-fill me-1"></i>Файл не найден</span>
                            </span>
                        </div>

                        <div class="path-line" v-if="file.is_mismatch">
                            <span class="path-pill is-mismatch">
                                <span class="path-pill-label">Будет:</span>
                                <span class="path-pill-value" :title="file.renamed_path_preview">{{ getBaseName(file.renamed_path_preview) }}</span>
                            </span>
                        </div>
                    </div>

                    <div class="pills-column">
                        <div class="pill"><i class="bi bi-check2-square"></i><span>Статус: <strong>{{ file.status }}</strong></span></div>
                        <div class="pill"><i class="bi bi-tags"></i><span>Тег: <strong>{{ file.extracted_metadata.voiceover || 'N/A' }}</strong></span></div>
                        <div class="pill"><i class="bi bi-badge-hd"></i><span>Качество: <strong>{{ file.extracted_metadata.quality || 'N/A' }}</strong></span></div>
                        <div class="pill"><i class="bi bi-fingerprint"></i><span>ID: <strong>{{ file.id }} / {{ file.qb_hash.substring(0, 8) }}</strong></span></div>
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
      isReprocessing: false,
      series: {},
      torrentFiles: [],
    };
  },
  watch: {
    isActive(newVal) {
      if (newVal) {
        this.load();
      }
    }
  },
  computed: {
    getBaseName() {
        return (path) => {
            if (!path) return '';
            return path.split(/[\\/]/).pop();
        }
    },
        getActualPath() {
        return (file) => file.renamed_path || file.original_path;
    },
    groupedFiles() {
      if (!this.torrentFiles.length) return {};

      const groups = this.torrentFiles.reduce((acc, file) => {
        const metadata = file.extracted_metadata || {};
        const season = metadata.season ?? 'N/A';
        if (!acc[season]) acc[season] = [];
        acc[season].push(file);
        return acc;
      }, {});

      for (const season in groups) {
        groups[season].sort((a, b) => {
          const epA = a.extracted_metadata?.episode ?? a.extracted_metadata?.start ?? 0;
          const epB = b.extracted_metadata?.episode ?? b.extracted_metadata?.start ?? 0;
          return epA - epB;
        });
      }

      return groups;
    },
    sortedSeasons() {
      const seasonNumbers = Object.keys(this.groupedFiles);
      return seasonNumbers.sort((a, b) => {
        if (a === 'N/A') return 1;
        if (b === 'N/A') return -1;
        return parseInt(a, 10) - parseInt(b, 10);
      });
    },
  },
  methods: {
    async load() {
      this.isLoading = true;
      try {
        const [seriesRes, compRes] = await Promise.all([
          fetch(`/api/series/${this.seriesId}`),
          fetch(`/api/series/${this.seriesId}/composition`)
        ]);

        if (!seriesRes.ok) throw new Error('Ошибка загрузки данных сериала');
        if (!compRes.ok) throw new Error('Ошибка загрузки композиции');
        
        this.series = await seriesRes.json();
        this.torrentFiles = await compRes.json();

      } catch (error) {
        this.$emit('show-toast', error.message, 'danger');
      } finally {
        this.isLoading = false;
      }
    },
    async reprocessAllFiles() {
        if (!confirm('Вы уверены, что хотите заново применить правила ко всем файлам этого сериала? Существующие метаданные и имена файлов будут перезаписаны.')) {
            return;
        }
        this.isReprocessing = true;
        this.$emit('show-toast', 'Запущена переобработка файлов...', 'info');
        try {
            const response = await fetch(`/api/series/${this.seriesId}/reprocess`, { method: 'POST' });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Ошибка при запуске переобработки');
            }
            this.$emit('show-toast', data.message, 'success');
            setTimeout(() => {
                this.load();
            }, 2000);
        } catch (error) {
            this.$emit('show-toast', error.message, 'danger');
        } finally {
            this.isReprocessing = false;
        }
    },
    getCardColorClass(file) {
      if (!file.is_file_present) {
        return 'status-pending'; // Желтый, если файла нет на диске
      }
      switch (file.status) {
        case 'renamed':
          return 'status-success'; // Зеленый
        case 'pending_rename':
          return 'status-pending'; // Желтый
        case 'skipped':
        case 'rename_error':
        default:
          return 'status-no-match'; // Серый для всего остального
      }
    },
    getSeasonTitle(seasonNumber) {
      if (seasonNumber === 'N/A') return 'Сезон не определен';
      return `Сезон ${String(seasonNumber).padStart(2, '0')}`;
    },
    formatSXXEXX(metadata) {
      if (!metadata) return '';
      const season = String(metadata.season || 1).padStart(2, '0');
      const episode = metadata.episode;
      const start = metadata.start;
      const end = metadata.end;

      if (episode) return `s${season}e${String(episode).padStart(2, '0')}`;
      if (start && end) return `s${season}e${String(start).padStart(2, '0')}-e${String(end).padStart(2, '0')}`;
      if (start) return `s${season}e${String(start).padStart(2, '0')}`;
      return `s${season}`;
    }
  }
};