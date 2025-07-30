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
                // --- НАЧАЛО ИЗМЕНЕНИЙ: Полностью новая, более надёжная логика ---
                const OPTION_HEIGHT_ESTIMATE = 40; // Примерная высота одного пункта
                const PADDING = 20; // Минимальный отступ от края окна
                
                const fullListHeight = props.options.length * OPTION_HEIGHT_ESTIMATE;
                const triggerRect = selectRef.value.getBoundingClientRect();
                
                const spaceBelow = window.innerHeight - triggerRect.bottom;
                const spaceAbove = triggerRect.top;

                // Сбрасываем maxHeight перед вычислением
                listStyle.maxHeight = 'none';

                // --- Логика выбора направления и размера ---
                if (fullListHeight < spaceBelow - PADDING) {
                    // Случай 1: Список полностью помещается снизу
                    opensUp.value = false;
                    listStyle.top = `${triggerRect.bottom}px`;
                    listStyle.bottom = 'auto';
                } else if (fullListHeight < spaceAbove - PADDING) {
                    // Случай 2: Список полностью помещается сверху
                    opensUp.value = true;
                    listStyle.bottom = `${window.innerHeight - triggerRect.top}px`;
                    listStyle.top = 'auto';
                } else if (spaceAbove > spaceBelow) {
                    // Случай 3: Не помещается нигде, но сверху места больше.
                    // Ограничиваем высоту доступным пространством сверху.
                    opensUp.value = true;
                    listStyle.bottom = `${window.innerHeight - triggerRect.top}px`;
                    listStyle.top = `${PADDING}px`; // Прижимаем к верху экрана
                } else {
                    // Случай 4: Не помещается нигде, но снизу места больше или столько же.
                    // Ограничиваем высоту доступным пространством снизу.
                    opensUp.value = false;
                    listStyle.top = `${triggerRect.bottom}px`;
                    listStyle.bottom = `${PADDING}px`; // Прижимаем к низу экрана
                }

                // Общие стили для позиционирования
                listStyle.left = `${triggerRect.left}px`;
                listStyle.width = `${triggerRect.width}px`;
                // --- КОНЕЦ ИЗМЕНЕНИЙ ---
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