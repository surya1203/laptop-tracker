// Toasts: fade out on their own. An Undo toast shows how long is left.
document.querySelectorAll('[data-toast]').forEach((toast) => {
    const seconds = Number(toast.dataset.toastSeconds || 4);
    const bar = toast.querySelector('[data-toast-bar]');
    if (bar) {
        bar.style.transition = `transform ${seconds}s linear`;
        requestAnimationFrame(() => requestAnimationFrame(() => { bar.style.transform = 'scaleX(0)'; }));
    }
    setTimeout(() => toast.remove(), seconds * 1000);
});

// Results review: count ticked listings and enable "Track selected".
const review = document.getElementById('review-form');
if (review) {
    const boxes = [...document.querySelectorAll('[data-track]')];
    const count = document.getElementById('track-count');
    const submit = document.getElementById('track-submit');
    const all = document.getElementById('track-all');
    const sync = () => {
        const ticked = boxes.filter((box) => box.checked).length;
        count.textContent = ticked;
        submit.disabled = ticked === 0;
        all.textContent = ticked === boxes.length ? 'Untick all' : 'Tick all';
    };
    boxes.forEach((box) => box.addEventListener('change', sync));
    all.addEventListener('click', () => {
        const tick = boxes.some((box) => !box.checked);
        boxes.forEach((box) => { box.checked = tick; });
        sync();
    });
    sync();
}

// Hunt filter form: cascading dropdowns and the live "active filters" bar.
const form = document.getElementById('hunt-form');
if (form) {
    const catalog = JSON.parse(document.getElementById('catalog-data').textContent);
    const field = (name) => form.elements[name];

    // Look a brand up regardless of how it was typed.
    const lookup = (map, brand) => {
        const wanted = brand.trim().toLowerCase();
        const key = Object.keys(map).find((k) => k.toLowerCase() === wanted);
        return key ? map[key] : null;
    };
    const everything = (map) => Object.values(map).flat();
    const fill = (listId, values) => {
        document.getElementById(listId).replaceChildren(...values.map((v) => new Option('', v)));
    };

    // Brand -> series suggestions (all ticked brands, or every brand when none is ticked).
    const syncSeries = () => {
        const ticked = [...form.querySelectorAll('input[name="brands"]:checked')].map((box) => box.value);
        const series = ticked.flatMap((brand) => lookup(catalog.series, brand) || []);
        fill('dl-series', ticked.length ? series : everything(catalog.series));
    };

    // CPU brand -> CPU family choices. A family from another brand is cleared.
    const syncCpu = (changed) => {
        const brand = field('cpu_brand').value;
        const families = lookup(catalog.cpu_families, brand);
        fill('dl-cpu_family', families || (brand.trim() ? [] : everything(catalog.cpu_families)));
        const family = field('cpu_family');
        const known = everything(catalog.cpu_families).includes(family.value);
        if (changed && families && known && !families.includes(family.value)) family.value = '';
    };

    // GPU brand -> GPU model choices. Models of other brands are hidden and unticked.
    const syncGpu = (changed) => {
        const brand = field('gpu_brand').value.trim().toLowerCase();
        form.querySelectorAll('[data-gpu-group]').forEach((group) => {
            const show = !brand || group.dataset.gpuGroup.toLowerCase() === brand;
            group.classList.toggle('hidden', !show);
            if (changed && !show) group.querySelectorAll('input').forEach((box) => { box.checked = false; });
        });
    };

    // One removable chip per filter that is set.
    const bar = document.getElementById('active-filters');
    const empty = document.getElementById('no-filters');
    const chipText = (input) => {
        const { chipPrefix = '', chipSuffix = '' } = input.dataset;
        if (input.type === 'checkbox') return input.checked ? input.value : '';
        if (input.tagName === 'SELECT') return input.value ? chipPrefix + input.selectedOptions[0].dataset.chipText : '';
        return input.value.trim() ? chipPrefix + input.value.trim() + chipSuffix : '';
    };
    const syncChips = () => {
        const chips = [];
        form.querySelectorAll('[data-chip]').forEach((input) => {
            const text = chipText(input);
            if (!text) return;
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'chip hover:bg-slate-200 dark:hover:bg-slate-700';
            chip.title = 'Remove this filter';
            chip.append(text, ' ×');
            chip.addEventListener('click', () => {
                if (input.type === 'checkbox') input.checked = false; else input.value = '';
                input.dispatchEvent(new Event('input', { bubbles: true }));
            });
            chips.push(chip);
        });
        bar.replaceChildren(...chips);
        empty.classList.toggle('hidden', chips.length > 0);
    };

    form.addEventListener('input', (event) => {
        const name = event.target.name;
        if (name === 'brands') syncSeries();
        if (name === 'cpu_brand') syncCpu(true);
        if (name === 'gpu_brand') syncGpu(true);
        syncChips();
    });

    syncSeries();
    syncCpu(false);
    syncGpu(false);
    syncChips();
}
