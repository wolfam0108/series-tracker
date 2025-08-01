const { ref, computed, onMounted, onBeforeUnmount, reactive } = Vue;

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
        
        const listStyle = reactive({
            top: 'auto',
            left: '0px',
            width: 'auto',
            bottom: 'auto',
            maxHeight: 'none'
        });

        const selectedOptionText = computed(() => {
            const selected = props.options.find(opt => opt.value === props.modelValue);
            return selected ? selected.text : 'Выберите опцию';
        });

        const toggleDropdown = () => {
            if (!isOpen.value && selectRef.value) {
                const OPTION_HEIGHT_ESTIMATE = 40;
                const PADDING = 20;

                const triggerRect = selectRef.value.getBoundingClientRect();
                const spaceBelow = window.innerHeight - triggerRect.bottom;
                const spaceAbove = triggerRect.top;

                // --- НОВАЯ, БОЛЕЕ НАДЁЖНАЯ ЛОГИКА ---
                const estimatedHeight = props.options.length * OPTION_HEIGHT_ESTIMATE + PADDING;

                // 1. Предпочитаем открывать вниз, если там точно достаточно места.
                if (estimatedHeight <= spaceBelow) {
                    opensUp.value = false;
                }
                // 2. Иначе, если сверху места объективно больше, чем снизу, открываем вверх.
                else if (spaceAbove > spaceBelow) {
                    opensUp.value = true;
                }
                // 3. Во всех остальных случаях (места мало везде, но снизу не меньше), открываем вниз.
                else {
                    opensUp.value = false;
                }
                // --- КОНЕЦ НОВОЙ ЛОГИКИ ---

                // Логика позиционирования и ограничения высоты
                if (opensUp.value) {
                    listStyle.bottom = `${window.innerHeight - triggerRect.top}px`;
                    listStyle.top = 'auto';
                    listStyle.maxHeight = `${spaceAbove - PADDING}px`;
                } else {
                    listStyle.top = `${triggerRect.bottom}px`;
                    listStyle.bottom = 'auto';
                    listStyle.maxHeight = `${spaceBelow - PADDING}px`;
                }

                listStyle.left = `${triggerRect.left}px`;
                listStyle.width = `${triggerRect.width}px`;
            }
            isOpen.value = !isOpen.value;
        };

        const selectOption = (option) => {
            emit('update:modelValue', option.value);
            isOpen.value = false;
        };

        const handleClickOutside = (event) => {
            if (isOpen.value && selectRef.value && !selectRef.value.contains(event.target)) {
                const listEl = document.querySelector('.options-list');
                if (listEl && !listEl.contains(event.target)) {
                    isOpen.value = false;
                }
            }
        };

        onMounted(() => { document.addEventListener('click', handleClickOutside, true); });
        onBeforeUnmount(() => { document.removeEventListener('click', handleClickOutside, true); });

        return { isOpen, opensUp, selectRef, selectedOptionText, toggleDropdown, selectOption, listStyle };
    },
    template: `
        <div 
            class="constructor-item item-select" 
            :class="{ open: isOpen }" 
            ref="selectRef" 
            @click="toggleDropdown"
        >
            <span class="selected-value">{{ selectedOptionText }}</span>
            <i class="bi bi-chevron-down chevron"></i>
            <div class="options-list" :class="{ 'opens-up': opensUp }" :style="listStyle">
                <div 
                    v-for="option in options" 
                    :key="option.value" 
                    class="option"
                    :class="{ selected: option.value === modelValue }"
                    @click.stop="selectOption(option)"
                >
                    {{ option.text }}
                </div>
            </div>
        </div>
    `
};