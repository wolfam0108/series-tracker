// Внутренний компонент для рекурсивной отрисовки узлов дерева
const TreeNode = {
  name: 'TreeNode',
  props: {
    node: Object,
    name: String,
    depth: Number
  },
  data() {
    return {
      isOpen: this.depth === 0 // Раскрываем только верхний уровень по умолчанию
    };
  },
  computed: {
    isFolder() {
      return this.node && Object.keys(this.node).length > 0;
    },
    indent() {
      return { paddingLeft: `${this.depth * 20}px` };
    }
  },
  methods: {
    toggle() {
      if (this.isFolder) {
        this.isOpen = !this.isOpen;
      }
    }
  },
  template: `
    <div :style="indent">
      <div @click="toggle" :class="{ 'folder': isFolder, 'file-node': !isFolder }">
        <span v-if="isFolder">{{ isOpen ? '▾' : '▸' }} 📁</span>
        <span v-else>📄</span>
        {{ name }}
      </div>
      <div v-if="isFolder && isOpen">
        <tree-node
          v-for="(childNode, childName) in node"
          :key="childName"
          :node="childNode"
          :name="childName"
          :depth="depth + 1"
        ></tree-node>
      </div>
    </div>
  `
};

// Главный компонент файлового дерева
const FileTree = {
  props: {
    files: {
      type: Array,
      required: true,
      default: () => []
    }
  },
  components: {
    'tree-node': TreeNode
  },
  computed: {
    fileTree() {
      const tree = {};
      this.files.forEach(path => {
        const parts = path.split('/');
        let currentLevel = tree;
        parts.forEach((part, index) => {
          if (!currentLevel[part]) {
            currentLevel[part] = {};
          }
          currentLevel = currentLevel[part];
        });
      });
      return tree;
    }
  },
  template: `
    <div class="file-tree-container">
      <tree-node 
        v-for="(node, name) in fileTree" 
        :key="name" 
        :node="node" 
        :name="name"
        :depth="0"
      ></tree-node>
    </div>
  `
};
