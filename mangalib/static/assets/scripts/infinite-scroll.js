/*
Pages that would like inifinte scroll should have a function defined somewhere called query_request_url

This will allow manga cards html to be generated

Example:
query_request_url = () => "{{ url_for('api.generate_manga_cards') }}";

Additonally, a spinning load indicator was implemented and expected to be something like:

<div class="scroll-load-spin">
    <i id="scroll-load-icon" class="fa fa-spinner w3-hide"></i>
</div>

and should go right after the first grid generation

var batch_size and var offset should be defined in the page itself
*/

var isLoading = false;


const grid_id = "manga-grid";
const scroll_id = "main-content";
const loading_icon_id = "scroll-load-icon";
const scroll_dector_height = 10;
const small_dealy = 1000;
const big_dealy = 100000;


var delay = small_dealy;

async function fetchTitles(content, request) {
    isLoading = true;


    var load_icon = document.getElementById(loading_icon_id);
    load_icon.classList.remove('w3-hide');
    load_icon.parentElement.classList.add("loading")
    // content.scrollTop = content.scrollTopMax;

    var args = `?count=${batch_size}&offset=${offset}`
    console.log(request + args)
    try {
        await fetch(request + args).then(response => response.text()).then(processFetch);
    } catch {
        clean_up(big_dealy);
    }
}

function clean_up(delay) {
    offset += batch_size

    setTimeout(() => {
        isLoading = false;
        if (!detect_end_of_scroll()) {
            var load_icon = document.getElementById(loading_icon_id);
            load_icon.classList.add('w3-hide');
            load_icon.parentElement.classList.remove("loading")
        }
    }, delay);
}

function processFetch(grid_html) {
    if(grid_html === "") {
        clean_up(big_dealy);
    } else {
        var grid = document.getElementById(grid_id);
        grid.innerHTML += grid_html
        clean_up(small_dealy);
    }
}

window.addEventListener('load', function() {
    var content = this.document.getElementById(scroll_id);
    content.addEventListener('scroll', detect_end_of_scroll)
});

function detect_end_of_scroll() {
    var content = document.getElementById(scroll_id);
    if(content.scrollTop >= content.scrollTopMax - scroll_dector_height && !isLoading) {
        fetchTitles(content, query_request_url(batch_size, offset));
        setTimeout(() => {}, 1000);
        return true;
    } else {
        return false;
    }
}

