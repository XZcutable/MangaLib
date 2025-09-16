const page_id = "page-image";
const load_icon_id = "load-icon";
const search_bar_id = "search-input";
const zone_id = "page-zone";
const content_id = "page-content";
const left_grad_id = "left-grad";
const right_grad_id = "right-grad";

var ignore_keys = false;
var imageHidden = false;

// Should be defined in the document
var next_page = "";
var prev_page = "";


function playLeftGrad() {
    let grad = document.getElementById("left-grad");
    grad.classList.add("left-grad");
}

function playRightGrad() {
    let grad = document.getElementById("right-grad");
    grad.classList.add("right-grad");
}


//#region ui_events
let sides = 0.3;

let clicking = false;
let mouseX = 0

function mouseDown(event) {
    clicking = event.button == 0;
    mouseX = event.offsetX;
}

function mouseUp(event) {
    if(clicking && event.button == 0) {
        clicking = false;
        let clickedOnLeft = mouseX <= (event.currentTarget.offsetWidth / 2 * sides);
        let clickedOnRight = mouseX >= (event.currentTarget.offsetWidth / 2 * (2 - sides));

        mouseX = event.offsetX;

        let clickedOnLeft2 = mouseX <= (event.currentTarget.offsetWidth / 2 * sides);
        let clickedOnRight2 = mouseX >= (event.currentTarget.offsetWidth / 2 * (2 - sides));

        if(clickedOnLeft === clickedOnLeft2) {
            if(clickedOnLeft) {
                prevPage();
            }
        }

        if(clickedOnRight === clickedOnRight2) {
            if(clickedOnRight) {
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
    // event.preventDefault();

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
    // event.preventDefault();
    dragging = false;
    scrolling = false;
    event.currentTarget.style.transform = `translate(0px, 0px)`;
}

//#endregion

function nextPage() {
    if(next_page !== "") {
        window.location = next_page;
    }
}

function prevPage() {
    if(prev_page !== "") {
        window.location = prev_page;
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
        content.classList.add("center-image")
    }
    
    if (aspect >= 2.5) {
        zone.classList.remove("fill-height");
        content.classList.remove("fill-height");
    } else if(page.naturalHeight >= window.innerHeight) {
        content.classList.remove("center-image")
        zone.classList.add("fill-height")
    }
    
    if(page.naturalHeight < window.innerHeight) {
        zone.classList.add("fill-height");
        content.classList.add("fill-height");
    }
}

function onLoad() {
    document.getElementById(left_grad_id).onanimationend = (event) => event.currentTarget.classList.remove("left-grad")
    document.getElementById(right_grad_id).onanimationend = (event) => event.currentTarget.classList.remove("right-grad")

    let zone = document.getElementById(zone_id);
    zone.addEventListener('touchstart', touchStart)
    zone.addEventListener('touchmove', touchMove)
    zone.addEventListener('touchend', touchEnd)
    zone.addEventListener('touchcancel', touchCancel)

    zone.addEventListener('mousedown', mouseDown)
    zone.addEventListener('mouseup', mouseUp)

    let search_bad = document.getElementById(search_bar_id);
    search_bad.addEventListener("focus", () => ignore_keys = true);
    search_bad.addEventListener("blur", () => ignore_keys = false);

    adjustPageToFit();
    let load_icon = document.getElementById("load-icon");
    load_icon.classList.add("w3-hide");

    hideImage(false);
}

addEventListener('load', onLoad);

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
