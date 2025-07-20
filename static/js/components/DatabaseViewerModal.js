const DatabaseViewerModal = {
  template: `
    <div class="modal fade" ref="dbViewerModal" tabindex="-1" aria-labelledby="dbViewerModalLabel" aria-hidden="true">
        <div class="modal-dialog modal-fullscreen">
            <div class="modal-content modern-modal" style="display: flex; flex-direction: column;">
                <div class="modal-header modern-header">
                    <h5 class="modal-title" id="dbViewerModalLabel"><i class="bi bi-database me-2"></i>Просмотр Базы Данных</h5>
                    
                    <ul class="nav modern-nav-tabs" role="tablist">
                        <li v-for="table in tables" :key="table" class="nav-item" role="presentation">
                            <button class="nav-link modern-tab-link" 
                                    :class="{ active: activeTable === table }"
                                    @click="fetchTableData(table)"
                                    type="button" role="tab">{{ table }}</button>
                        </li>
                    </ul>

                    <button type="button" class="btn-close modern-close" @click="close" aria-label="Close"></button>
                </div>
                <div class="modal-body modern-body" style="overflow: auto; flex-grow: 1;">
                    <div v-if="isLoading" class="text-center p-5"><div class="spinner-border" role="status"></div></div>
                    <div v-else-if="!tableData.length" class="empty-state">
                        <h4>Таблица пуста</h4>
                        <p>В таблице '{{ activeTable }}' нет данных для отображения.</p>
                    </div>
                    <div v-else class="table-responsive">
                        <table class="table table-bordered table-striped table-hover table-sm">
                            <thead class="table-light" style="position: sticky; top: -24px;">
                                <tr>
                                    <th v-for="header in tableHeaders" :key="header">{{ header }}</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr v-for="(row, index) in tableData" :key="index">
                                    <td v-for="header in tableHeaders" :key="header" :title="row[header]">
                                        <div style="max-height: 100px; overflow-y: auto;">
                                            {{ row[header] }}
                                        </div>
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
                <div class="modal-footer modern-footer">
                    <button type="button" class="btn btn-secondary" @click="close">Закрыть</button>
                </div>
            </div>
        </div>
    </div>
  `,
  data() {
    return {
        modal: null,
        isLoading: false,
        tables: [],
        activeTable: null,
        tableData: [],
        tableHeaders: []
    };
  },
  methods: {
    async open() {
      if (!this.modal) this.modal = new bootstrap.Modal(this.$refs.dbViewerModal);
      this.modal.show();
      await this.fetchTables();
    },
    close() {
      this.modal.hide();
    },
    async fetchTables() {
        this.isLoading = true;
        try {
            const response = await fetch('/api/database/tables');
            if (!response.ok) throw new Error('Ошибка загрузки списка таблиц');
            this.tables = await response.json();
            if (this.tables.length > 0) {
                await this.fetchTableData(this.tables[0]);
            }
        } catch (error) {
            // Здесь можно использовать this.$emit('show-toast', ...) если компонент имеет доступ
            console.error(error);
        } finally {
            this.isLoading = false;
        }
    },
    async fetchTableData(tableName) {
        this.activeTable = tableName;
        this.isLoading = true;
        this.tableData = [];
        this.tableHeaders = [];
        try {
            const response = await fetch(`/api/database/table/${tableName}`);
            if (!response.ok) throw new Error(`Ошибка загрузки данных из таблицы ${tableName}`);
            const data = await response.json();
            this.tableData = data;
            if (data.length > 0) {
                this.tableHeaders = Object.keys(data[0]);
            }
        } catch (error) {
            console.error(error);
        } finally {
            this.isLoading = false;
        }
    }
  }
};