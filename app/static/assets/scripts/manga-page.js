const page_id = "page-image";
const load_icon_id = "load-icon";
const search_bar_id = "search-input";
const zone_id = "page-zone";
const content_id = "page-content";
const left_grad_id = "left-grad";
const right_grad_id = "right-grad";

var ignore_keys = false;
var imageHidden = false;
var navigating = false;
var progress_saved = false;

function playLeftGrad() {
    let grad = document.getElementById("left-grad");
    grad.classList.add("left-grad");
}

function playRightGrad() {
    let grad = document.getElementById("right-grad");
    grad.classList.add("right-grad");
}


//#region ui_events
let sides = 0.2;
let inZone = false;
let clicking = false;
let mouseX = 0

const mouse_data = {"inZone": false, "side": "", "debounce": true};

function update_mouse_data(zone, mouseX) {
    if(mouseX <= zone.offsetWidth * sides) {
        mouse_data.inZone = true;
        mouse_data.debounce = mouse_data.debounce || mouse_data.side !== "left";
        mouse_data.side = "left"; 
    } else if(mouseX >= zone.offsetWidth - (zone.offsetWidth * sides)) {
        mouse_data.inZone = true;
        mouse_data.side = "right"; 
        mouse_data.debounce = mouse_data.debounce || mouse_data.side !== "right";
    } else {
        mouse_data.inZone = false;
        mouse_data.side = ""; 
        mouse_data.debounce = true;
    }
}

function mouseEnter(event) {
    
}

function mouseLeave() {
    mouse_data.inZone = false;
    mouse_data.side = ""; 
    mouse_data.debounce = true;
}

function mouseMove(event) {
    const zone = event.currentTarget;
    const mouseX = event.offsetX;

    update_mouse_data(zone, mouseX);

    if (mouse_data.inZone) {
        zone.style.cursor = "pointer";
        if(mouse_data.debounce) {
            if(mouse_data.side === "left") {
                mouse_data.debounce = false;
                playLeftGrad();
            } else if(mouse_data.side === "right") {
                mouse_data.debounce = false;
                playRightGrad();
            }
        }
    } else {
        zone.style.cursor = "initial";
        mouse_data.debounce = true;
    }
}

function mouseDown(event) {
    clicking = event.button == 0 && mouse_data.inZone
}

function mouseUp(event) {
    if(clicking && event.button == 0) {
        clicking = false;
        if(mouse_data.inZone) {
            if(mouse_data.side === "left") {
                prevPage();
            } else if(mouse_data.side === "right") {
                nextPage();
            }
        }
    }
}

let startX = -1;
let dragging = false;
let dir = 0;
let dragDist = 40;
let minXBeforeDrag = 15;


let minYBeforeScroll = 10;
let startY = 0;
let scrolling = false;
let animPlayed = false;

function touchStart(event) {
    if (event.touches.length == 1) {
        startX = event.touches[0].clientX;
        startY = event.touches[0].clientY;
        dir = 0;
    }
}

function touchMove(event) {
    if (event.touches.length == 1) {

        if(scrolling) {
            return;
        }

        let yDelta = Math.abs(event.touches[0].clientY - startY);

        if(!dragging && yDelta >= minYBeforeScroll) {
            scrolling = true;
            return;
        } else {
            event.preventDefault();
        }

        let deltaX = event.touches[0].clientX - startX;
        let clampedX = Math.min(dragDist, Math.max(-dragDist, deltaX));

        if(!dragging && Math.abs(deltaX) >= minXBeforeDrag) {
            dragging = true;
            startX = event.touches[0].clientX;
            deltaX = event.touches[0].clientX - startX;
            clampedX = Math.min(dragDist, Math.max(-dragDist, deltaX));
        } 
        
        if(dragging) {
            let curDir = Math.sign(deltaX);
            if(curDir != dir) {
                dir = curDir;
                startX = event.touches[0].clientX;
                clampedX = Math.min(dragDist, Math.max(-dragDist, deltaX));
                animPlayed = false;
            } else if(!animPlayed && Math.abs(deltaX) >= dragDist) {
                if(curDir > 0) {
                    playLeftGrad();
                    animPlayed = true;
                } else if(curDir < 0) {
                    playRightGrad();
                    animPlayed = true;
                }
            }
            event.currentTarget.style.transform = `translate(${clampedX}px, 0px)`;
        }
    }
}

function touchEnd(event) {
    if(dragging) {
        let endX = event.changedTouches[0].clientX;
        if(Math.abs(endX - startX) > dragDist) {
            if (endX < startX) {
                nextPage();
            } else {
                prevPage();
            }
        }
    }
    dragging = false;
    scrolling = false;
    animPlayed = false;
    event.currentTarget.style.transform = `translate(0px, 0px)`;
}

function touchCancel(event) {
    dragging = false;
    scrolling = false;
    event.currentTarget.style.transform = `translate(0px, 0px)`;
}

//#endregion

function home() {
    navigating = true;
    document.location = `${INFO_URL}/${manga.id}`;
}

function nextPage() {
    navigating = true;
    if(page.number + 1 <= chapter.pages.length) {
        window.location = `${PAGE_URL}/${manga.id}/${chapter.number}/${page.number + 1}`
    } else if(chapter.number + 1 <= manga.chapters.length) {
        window.location = `${PAGE_URL}/${manga.id}/${chapter.number + 1}/${1}`
    } else {
        home();
    }
}

function prevPage() {
    navigating = true;
    if(page.number - 1 >= 1) {
        window.location = `${PAGE_URL}/${manga.id}/${chapter.number}/${page.number - 1}`
    } else if(chapter.number - 1 >= 1) {
        let new_chapter = chapter.number - 1;
        window.location = `${PAGE_URL}/${manga.id}/${new_chapter}/${manga.chapters[new_chapter - 1].pages.length}`
    } else {
        home();
    }
}

function hideImage(hide=true) {
    let page = document.getElementById(page_id);
    if(hide) {
        page.classList.add("w3-hide");
    } else {
        page.classList.remove("w3-hide");
    }
    imageHidden = hide;
}

// TODO Get rid or do this better, not sure how well this is actually working
// May be better to do in css, kind of hacky maybe lol
function adjustPageToFit() {
    let page = document.getElementById(page_id);
    let zone = document.getElementById(zone_id);
    let content = document.getElementById(content_id);
    let aspect = page.naturalHeight / page.naturalWidth;

    if (page.naturalWidth > page.naturalHeight) {
        zone.classList.remove("fill-height");
        content.classList.remove("fill-height");
        // Was casuing an issue with big images, not sure if needed
        // content.classList.add("center-image")
    }
    
    if (aspect >= 2.5) {
        zone.classList.remove("fill-height");
        content.classList.remove("fill-height");
    } else if(page.naturalHeight >= window.innerHeight) {
        // content.classList.remove("center-image")
        zone.classList.add("fill-height")
    }
    
    if(page.naturalHeight < window.innerHeight) {
        zone.classList.add("fill-height");
        content.classList.add("fill-height");
    }
}

function loadUIEvents() {
    document.getElementById(left_grad_id).onanimationend = (event) => event.currentTarget.classList.remove("left-grad")
    document.getElementById(right_grad_id).onanimationend = (event) => event.currentTarget.classList.remove("right-grad")

    let zone = document.getElementById(zone_id);
    zone.addEventListener('touchstart', touchStart)
    zone.addEventListener('touchmove', touchMove)
    zone.addEventListener('touchend', touchEnd)
    zone.addEventListener('touchcancel', touchCancel)


    zone.addEventListener('mouseenter', mouseEnter)
    zone.addEventListener('mouseleave', mouseLeave)
    zone.addEventListener('mousemove', mouseMove)
    zone.addEventListener('mousedown', mouseDown)
    zone.addEventListener('mouseup', mouseUp)

    let search_bar = document.getElementById(SEARCH_BAR_ID);
    search_bar.addEventListener("focus", () => ignore_keys = true);
    search_bar.addEventListener("blur", () => ignore_keys = false);

    adjustPageToFit();
    let load_icon = document.getElementById("load-icon");
    load_icon.classList.add("w3-hide");

    hideImage(false);
}

async function save_progress(force_save=false) {
    if(force_save || (!progress_saved && !navigating)){
        progress_saved = true;

        let formData = new FormData();
        formData.append("manga_id", manga.id);
        formData.append("chapter_number", chapter.number);
        formData.append("page_number", page.number);

        try {
            await fetch(SAVE_PROGRESS_URL, {method: "POST", body: formData});
        } catch {

        }
    }
}

addEventListener("load", () => {
    if(page.number >= chapter.pages.length) {
        save_progress(true);
    } else {
        setTimeout(save_progress, 1000);

        const content = document.getElementById("main-content");
        const listener = () => {
            content.removeEventListener("mouseleave", listener);
            save_progress();
        }
        content.addEventListener("mouseleave", listener)
    }
});

addEventListener('load', loadUIEvents);

document.addEventListener("keydown", function(event) {
    if(ignore_keys) {
        return;
    }

    switch(event.key) {
        case "ArrowRight":
        case "d":
            nextPage();
            break;
        case "ArrowLeft":
        case "a":
            prevPage();
            break;
        case "h":
            hideImage(!imageHidden);
            break;
    }
});