function getDynamicPageValue(name) {
    // Dynamic pages receive their value through a magic anchor (e.g.
    // "#url=https%3A%2F%2F...")
    const hash = window.location.hash.substring(1);
    const prefix = name + "=";
    if (!hash.startsWith(prefix)) {
        return null;
    }
    try {
        return decodeURIComponent(hash.substring(prefix.length));
    } catch (error) {
        return null;
    }
}

document.addEventListener("DOMContentLoaded", function(){
    const value = getDynamicPageValue("url");
    const linkContainer = document.getElementById("my_link_container");
    const elink = document.getElementById("my_link");

    // The page can also be reached directly without a value; hide the
    // original-link block in that case.
    if (!value) {
        if (linkContainer) {
            linkContainer.style.display = "none";
        }
        return;
    }

    if (!elink) {
        return;
    }

    elink.href = value;
    elink.textContent = value;
});
