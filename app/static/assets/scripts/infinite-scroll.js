var isLoading = false;

const grid_id = "manga-grid";
const scroll_id = "main-content";
const loading_icon_id = "scroll-load-icon";
const scroll_detector_height = 10;
const small_dealy = 1000;
const big_dealy = 10000;


var delay = small_dealy;
var sort = 'desc'
var stop_loading = false;

function clean_up(delay, success, processed) {
    var load_icon = document.getElementById(loading_icon_id);
    
    if(success) {
        offset += processed;

        setTimeout(() => {
            isLoading = false;

            if (!detect_end_of_scroll()) {
                load_icon.classList.add('w3-hide');
                load_icon.parentElement.classList.remove("loading")
            }
        }, delay);

    } else {
        load_icon.classList.add('w3-hide');
        load_icon.parentElement.classList.remove("loading");
        setTimeout(() => {
            isLoading = false;
        }, delay);
    }
}


window.addEventListener('load', function() {
    var content = this.document.getElementById(scroll_id);
    content.addEventListener('scroll', detect_end_of_scroll);
    detect_end_of_scroll();
});

function detect_end_of_scroll() {
    var content = document.getElementById(scroll_id);
    if(!stop_loading && content.scrollTop >= content.scrollTopMax - scroll_detector_height && !isLoading) {
        request_batch(batch_size, offset);
        return true;
    } else {
        return false;
    }
}

async function request_batch(batch_size, offset) {
    if(stop_loading || isLoading) {
        return;
    }
    
    isLoading = true;

    var load_icon = document.getElementById(loading_icon_id);
    load_icon.classList.remove('w3-hide');
    load_icon.parentElement.classList.add("loading");
    // content.scrollTop = content.scrollTopMax;
    try {
        let data = await fetchTitles(batch_size, offset);
        process_batch(data);
    } catch(e) {
        console.log(e);
        clean_up(big_dealy, false);
    }
}

async function fetchTitles(batch_size, offset) {
    try {
        var request = `${QUERY_REQUEST_URL}?count=${batch_size}&offset=${offset}&sort=${sort}`;
        const response = await fetch(request);
        if(response.status == 200) {
            const json = await response.json();
            return json;
        }
    } catch {
        console.log("Error Fetching Tiles")
    }
    throw "No Json"
}

function process_batch(manga_infos) {
    if(manga_infos.length > 0) {
        var grid = document.getElementById(grid_id);
        for(let i in manga_infos) {
            let info = manga_infos[i];
            item_html = createMangaGridItem(info.id, info.title);
            grid.innerHTML += item_html;
        }
        clean_up(small_dealy, true, manga_infos.length);
    } else {
        clean_up(big_dealy, false);
    }
}

function createMangaGridItem(manga_id, title) {
    if(HIDE_TITLES) {
        title = "Manga Title Here"
    }
    return `
    <div class="manga-card w3-card w3-round-large">
        <a href="${MANGA_URL}/${manga_id}">
            <div class="manga-card-thumbnail w3-hover-opacity">
                <img src="${IMAGE_URL}/${manga_id}/1" alt="Thumbnail" class="w3-round-large no-hover">
            </div>
        </a>
        <a href="${MANGA_URL}/${manga_id}">
            <div class="manga-card-title w3-tiny w3-text-white text-shadow">
                ${title}
            </div>
        </a>
    </div>
    `;
}

function createChapterGridItem(manga_id, chapter_number, title) {
    if(HIDE_TITLES) {
        title = "Manga Title Here"
    }
    return `
    <div class="manga-card w3-card w3-round-large">
        <a href="${MANGA_URL}/${manga_id}/${chapter_number}/1">
            <div class="manga-card-thumbnail w3-hover-opacity">
                <img src="${IMAGE_URL}/${manga_id}/${chapter_number}/1" alt="Thumbnail" class="w3-round-large no-hover">
            </div>
        </a>
        <a href="${MANGA_URL}/${manga_id}/${chapter_number}/1">
            <div class="manga-card-title w3-tiny w3-text-white text-shadow">
                ${title}
            </div>
        </a>
    </div>
    `;
}

function createPageGridItem(manga_id, chapter_number, page_number) {
    return `
    <div class="manga-card manga-card-page w3-card w3-round-large">
        <a href="${MANGA_URL}/${manga_id}/${chapter_number}/${page_number}">
            <div class="manga-card-thumbnail w3-hover-opacity">
                <img src="${IMAGE_URL}/${manga_id}/${chapter_number}/${page_number}"" alt="Thumbnail" class="w3-round-large no-hover">
            </div>
        </a>
    </div>
    `
}