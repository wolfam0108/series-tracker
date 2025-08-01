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
                         class="test-result-card-compact"
                         :class="getCardColorClass(file)">
                        
                        <div class="card-line">
                            <strong class="card-title" style="font-size: 16px;">{{ series.name }} {{ formatSXXEXX(file.extracted_metadata) }}</strong>
                            <div v-if="file.extracted_metadata && file.extracted_metadata.resolution" class="quality-badge">
                                <span>{{ file.extracted_metadata.resolution }}</span>
                            </div>
                        </div>

                        <div class="path-info text-muted small">
                            <span class="path-label">Исходный файл:</span>
                            <span class="path-value" :title="file.original_path">{{ file.original_path }}</span>
                        </div>

                        <div class="path-info text-muted small">
                            <span class="path-label">Итоговый файл:</span>
                            <span class="path-value" :title="file.renamed_path_preview">{{ file.renamed_path_preview }}</span>
                        </div>

                        <div class="card-line small">
                            <span>Качество: <strong>{{ file.extracted_metadata.quality || 'N/A' }}</strong></span>
                            <span>Тег: <strong>{{ file.extracted_metadata.voiceover || 'N/A' }}</strong></span>
                            <span>Статус: <strong>{{ file.status }}</strong></span>
                            <span class="card-rule-name" :title="'QB Hash: ' + file.qb_hash">{{ file.id }} / {{ file.qb_hash.substring(0, 8) }}</span>
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
    groupedFiles() {
      if (!this.torrentFiles.length) return {};

      // 1. Группируем файлы по сезонам, как и раньше
      const groups = this.torrentFiles.reduce((acc, file) => {
        const metadata = file.extracted_metadata || {};
        const season = metadata.season ?? 'N/A';
        if (!acc[season]) acc[season] = [];
        acc[season].push(file);
        return acc;
      }, {});

      // 2. Сортируем файлы ВНУТРИ каждой группы (сезона)
      for (const season in groups) {
        groups[season].sort((a, b) => {
          const epA = a.extracted_metadata?.episode ?? a.extracted_metadata?.start ?? 0;
          const epB = b.extracted_metadata?.episode ?? b.extracted_metadata?.start ?? 0;
          return epA - epB; // Сортировка по возрастанию номера серии
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
      // Возвращаем классы, которые УЖЕ определены в lists.css для VK
      if (!file.is_file_present) return 'pending'; // Желтый (как у VK в ожидании)
      if (file.status === 'renamed') return 'success'; // Зеленый
      if (file.status === 'pending_rename') return 'pending'; // Желтый
      if (file.status === 'skipped') return 'no-match'; // Серый
      return '';
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