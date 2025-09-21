let init_manga;
let init_chapter;
let init_page;

let next_page;
let prev_page;


function init(manga, chapter, page) {
    init_manga = manga;
    init_chapter = chapter;
    init_page = page;
}

function load_next_page() {

}

function load_prev_page() {

}

function load_image(manga, chapter, page) {
    const image = document.getElementById("page-image");
    image.setAttribute("src", getImageURL(manga, chapter, page));
}

function update_links(manga, chapter, page) {
    if (page.number + 1 <= chapter.pages.length) {
        next_page = {
            "manga": manga, 
            "chapter": chapter,
            "page": get_page_info(chapter, page.number + 1)
        }
    }
}

function load_page(manga, chapter, page) {
    load_image(manga, chapter, page);
    update_links(manga, chapter, page);
    {% if page.number + 1 <= chapter.pages|length %}
        
        {% elif manga.chapters|length > 1 %}
        next_page = "{{ url_for('manga') }}/{{ manga.id }}/{{ chapter.number + 1 }}/1"
        {% else %}
        next_page = "{{ url_for('manga') }}/{{ manga.id }}"
        {% endif %}

        {% if page.number - 1 > 0 %}
        prev_page = "{{ url_for('manga') }}/{{ manga.id }}/{{ chapter.number }}/{{ page.number - 1 }}"
        {% elif chapter.number - 1 > 0 %}
        prev_page = "{{ url_for('manga') }}/{{ manga.id }}/{{ chapter.number - 1 }}/{{ manga.chapters[chapter.number-2].pages|length }}"
        {% else %}
        prev_page = "{{ url_for('manga') }}/{{ manga.id }}"
        {% endif %}
}