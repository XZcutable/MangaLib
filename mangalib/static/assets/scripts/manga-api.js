async function updateMangaReadStatus(isRead) {
    let formData = new FormData();
    formData.append("is_read", isRead);

    try {
        await fetch(`${UPDATE_READ_STATUS_URL}?manga_id=${manga.id}`, {method: "POST", body: formData});
    } catch {

    }
}