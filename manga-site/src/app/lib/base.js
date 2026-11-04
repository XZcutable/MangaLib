// The path the app is served at: "" normally, "/manga" behind a proxy at https://example.com/manga/.
// The server puts it in index.html's <base> tag. In the mobile app the tag stays "/".
export const BASE_PATH = new URL(document.baseURI).pathname.replace(/\/+$/, "")
