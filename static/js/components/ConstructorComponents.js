const { ref, computed, onMounted, onBeforeUnmount } = Vue;

const ConstructorGroup = {
    template: `<div class="modern-input-group"><div class="input-constructor-group" :class="$attrs.class"><slot></slot></div></div>`
};

const ConstructorItemSelect = {
    props: {
        options: { type: Array, required: true },
        modelValue: { type: [String, Number], default: '' }
    },
    emits: ['update:modelValue'],
    setup(props, { emit }) {
        const isOpen = ref(false);
        const opensUp = ref(false);
        const selectRef = ref(null);

        const selectedOptionText = computed(() => {
            const selected = props.options.find(opt => opt.value === props.modelValue);
            return selected ? selected.text : 'Выберите опцию';
        });

        const toggleDropdown = () => {
            if (!isOpen.value) {
                const triggerRect = selectRef.value.getBoundingClientRect();
                const spaceBelow = window.innerHeight - triggerRect.bottom;
                const spaceAbove = triggerRect.top;
                const listHeight = 200;
                opensUp.value = spaceBelow < listHeight && spaceAbove > spaceBelow;
            }
            isOpen.value = !isOpen.value;
        };

        const selectOption = (option) => {
            emit('update:modelValue', option.value);
            isOpen.value = false;
        };

        const handleClickOutside = (event) => {
            if (selectRef.value && !selectRef.value.contains(event.target)) {
                isOpen.value = false;
            }
        };

        onMounted(() => { document.addEventListener('click', handleClickOutside); });
        onBeforeUnmount(() => { document.removeEventListener('click', handleClickOutside); });

        return { isOpen, opensUp, selectRef, selectedOptionText, toggleDropdown, selectOption };
    },
    template: `
        <div class="constructor-item item-select" :class="{ open: isOpen }" ref="selectRef" @click="toggleDropdown">
            <span class="selected-value">{{ selectedOptionText }}</span>
            <i class="bi bi-chevron-down chevron"></i>
            <div class="options-list" :class="{ 'opens-up': opensUp }">
                <div v-for="option in options" :key="option.value" class="option" :class="{ selected: option.value === modelValue }" @click.stop="selectOption(option)">
                    {{ option.text }}
                </div>
            </div>
        </div>
    `
};