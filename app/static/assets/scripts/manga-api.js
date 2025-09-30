async function updateMangaReadStatus(isRead) {
    let formData = new FormData();
    formData.append("is_read", isRead);

    if(!isRead && confirm("Do you want to reset your progress?")) {
        formData.append("reset", true);
    }

    try {
        await fetch(`${UPDATE_READ_STATUS_URL}?manga_id=${manga.id}`, {method: "POST", body: formData});
        document.location.reload();
    } catch {

    }
}

async function updateMangaFavStatus(isFav) {
    let formData = new FormData();
    formData.append("is_fav", isFav);

    try {
        await fetch(`${UPDATE_FAV_STATUS_URL}?manga_id=${manga.id}`, {method: "POST", body: formData});
        document.location.reload();
    } catch {

    }
}
